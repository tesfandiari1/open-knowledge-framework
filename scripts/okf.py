#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = ["pyyaml>=6"]
# ///
"""okf: keep a folder of Markdown files conformant with the Open Knowledge Format.

    uv run scripts/okf.py check [ROOT] [--all] [--baseline FILE]
    uv run scripts/okf.py index [ROOT] [--check] [--catalog]

Hard failures (exit 1) are the OKF conformance rules, identical in v0.1 and v0.2:
every non-reserved .md has parseable frontmatter with a non-empty `type`, and every
index.md / log.md is well formed. Everything else is a warning. Files that match a
`sources` glob (default: raw/ folders) are immutable sources and skip all checks.
Files that match an `inbox` glob also skip checks, and each one that no note links to
is reported as unprocessed.
Files that match a `meta` glob (default: README, AGENTS, CLAUDE) skip conformance
but keep their link checks. Optional config: ROOT/okf.toml (see okf.toml.example).

`index` writes a generated listing between okf:index markers in each folder's index.md.
It never touches sources, inbox, or excluded paths, and text outside the markers stays as is.
"""
import argparse
import fnmatch
import json
import os
import posixpath
import re
import sys
from collections import Counter, defaultdict
from urllib.parse import quote, unquote

import tomllib

try:
    import yaml
except ModuleNotFoundError:
    sys.exit("okf: PyYAML is missing. Run `uv run scripts/okf.py ...` or `pip install pyyaml`.")

DEFAULTS = {
    "exclude": [],
    "sources": ["raw/*", "*/raw/*"],
    "inbox": [],
    "meta": [f"{d}{n}.md" for d in ("", "*/") for n in ("README", "AGENTS", "CLAUDE")],
}
INDEX_MAX_BYTES = 4096  # ponytail: fixed cap, move to okf.toml when an adopter needs another value
ROUTING_FILES = {"agents.md", "claude.md"}
CONTEXT_MAX_BYTES = 16_000  # ponytail: about 4K tokens, a guess; tune once evals show a better cap
HARD = ("no-frontmatter", "bad-frontmatter", "no-type", "index-frontmatter", "log-heading", "log-order")

FM = re.compile(r"---[ \t]*\n(.*?)^---[ \t]*$", re.DOTALL | re.MULTILINE)
FENCE = re.compile(r"^(```|~~~).*?^\1", re.DOTALL | re.MULTILINE)
INLINE_CODE = re.compile(r"`[^`\n]*`")
MD_LINK = re.compile(r"\[[^\]]*\]\(<?([^)\s>]+)>?(?:\s+\"[^\"]*\")?\)")
WIKI_LINK = re.compile(r"\[\[([^\]|#^]+)")
ROUTE = re.compile(r"`(/?[\w.+-]+(?:/[\w.+@-]+)*(?:\.md|/))`")
H2 = re.compile(r"^## +(.*)$", re.MULTILINE)
ISO = re.compile(r"\d{4}-\d{2}-\d{2}")
SCHEME = re.compile(r"^[a-z][a-z0-9+.-]*:", re.IGNORECASE)
IMPORT = re.compile(r"(?<![\w`])@(~?[\w.+/-]+)")
H1 = re.compile(r"^# +(.*\S)", re.MULTILINE)
START, END = "<!-- okf:index:start -->", "<!-- okf:index:end -->"


def load_config(root):
    cfg = dict(DEFAULTS)
    path = os.path.join(root, "okf.toml")
    if os.path.exists(path):
        with open(path, "rb") as f:
            cfg.update(tomllib.load(f))
    return cfg


def walk(root):
    """Yield the relative posix path of every file outside dot-folders."""
    for dirpath, dirs, files in os.walk(root):
        rel_dir = os.path.relpath(dirpath, root).replace(os.sep, "/")
        rel_dir = "" if rel_dir == "." else rel_dir + "/"
        dirs[:] = [d for d in dirs if not d.startswith(".")]
        for f in files:
            yield rel_dir + f


def frontmatter(text):
    """Return (mapping, None) or (None, error code)."""
    if not text.startswith("---"):
        return None, "no-frontmatter"
    m = FM.match(text)
    if not m:
        return None, "bad-frontmatter"
    try:
        fm = yaml.safe_load(m.group(1)) or {}
    except yaml.YAMLError:
        return None, "bad-frontmatter"
    return (fm, None) if isinstance(fm, dict) else (None, "bad-frontmatter")


def always_loaded(root):
    """Map each file Claude Code loads on every turn to its size in bytes: the root CLAUDE.md,
    its @imports (up to 4 hops), and .claude/rules files with no `paths:` frontmatter."""
    sizes, todo = {}, [(os.path.join(root, "CLAUDE.md"), 0)]
    while todo:
        path, hops = todo.pop()
        if path in sizes or not os.path.isfile(path):
            continue
        with open(path, encoding="utf-8", errors="replace") as f:
            text = f.read()
        sizes[path] = len(text.encode())
        if hops < 4:
            body = INLINE_CODE.sub("", FENCE.sub("", text))
            todo += [(os.path.join(os.path.dirname(path), os.path.expanduser(m)), hops + 1) for m in IMPORT.findall(body)]
    for dirpath, _, files in os.walk(os.path.join(root, ".claude", "rules")):
        for name in files:
            path = os.path.join(dirpath, name)
            with open(path, encoding="utf-8", errors="replace") as f:
                text = f.read()
            fm, _ = frontmatter(text)
            if name.endswith(".md") and not (fm or {}).get("paths"):
                sizes[path] = len(text.encode())
    return sizes


def check(root, cfg=None):
    """Return (stats, findings). findings is a list of (code, rel_path, detail)."""
    cfg = cfg or load_config(root)
    files = sorted(walk(root))  # every file resolves links, even excluded ones
    lower = {f.lower() for f in files}
    dirs = {posixpath.dirname(f).lower() for f in files}
    dirs |= {"/".join(d.split("/")[:i]) for d in dirs for i in range(1, d.count("/") + 1)}
    names = Counter(posixpath.basename(f).lower() for f in files)
    suffixes = {"/".join(p[i:]) for f in lower for p in [f.split("/")] for i in range(len(p))}
    is_inbox = lambda rel: any(fnmatch.fnmatch(rel, g) for g in cfg["inbox"])
    is_source = lambda rel: is_inbox(rel) or any(fnmatch.fnmatch(rel, g) for g in cfg["sources"])
    excluded = lambda rel: any(fnmatch.fnmatch(rel, g) for g in cfg["exclude"])
    is_meta = lambda rel: any(fnmatch.fnmatch(rel, g) for g in cfg["meta"])

    findings, refs = [], set()
    stats = Counter()
    concept_stems = defaultdict(list)

    def alive(target, src):
        """Resolve one link target the way common viewers do. Record it. Return False if dead.

        Wikilinks match a bare name anywhere or a path suffix (Obsidian). Markdown links
        match relative to the file, then relative to the root (the OKF spec examples use
        root-relative paths), then by bare filename (Obsidian "shortest path" links).
        """
        if target.startswith("[["):
            t = target[2:].strip().lstrip("/").lower()
            refs.update({t, t + ".md", posixpath.basename(t), posixpath.basename(t) + ".md"})
            return t in suffixes or t + ".md" in suffixes
        if SCHEME.match(target) or target.startswith("#"):
            return True
        raw = unquote(target.split("#")[0].split("?")[0])
        base = "" if raw.startswith("/") else posixpath.dirname(src)
        for b in (base, ""):
            path = posixpath.normpath(posixpath.join(b, raw.lstrip("/")))
            t = path.lower()
            if t.startswith(".."):
                return True  # outside the bundle, not ours to judge
            refs.update({t, posixpath.basename(t)})
            if (t in lower or t + ".md" in lower or t in dirs or t == "."
                    or os.path.exists(os.path.join(root, path))):  # dot-folders are not walked
                return True
        return "/" not in raw.strip("/") and (raw.lower() in names or raw.lower() + ".md" in names)

    for rel in files:
        if not rel.endswith(".md") or excluded(rel):
            continue
        try:
            with open(os.path.join(root, rel), encoding="utf-8-sig", errors="replace") as f:
                text = f.read().replace("\r\n", "\n")
        except OSError as e:  # broken symlink, permissions
            findings.append(("unreadable", rel, e.strerror or str(e)))
            continue
        name = posixpath.basename(rel).lower()
        if is_source(rel):
            stats["sources"] += 1
            continue
        if name == "index.md":
            stats["index"] += 1
            fm, err = frontmatter(text)
            if err != "no-frontmatter" and not (fm is not None and set(fm) <= {"okf_version"}):
                findings.append(("index-frontmatter", rel, "index.md may carry only okf_version"))
            if len(text.encode()) > INDEX_MAX_BYTES:
                findings.append(("index-size", rel, f"{len(text.encode())} bytes > {INDEX_MAX_BYTES}"))
        elif name == "log.md":
            stats["log"] += 1
            heads = H2.findall(text)
            bad = [h for h in heads if not ISO.match(h)]
            if bad:
                findings.append(("log-heading", rel, f"not an ISO date: {bad[0][:60]}"))
            dates = [h[:10] for h in heads if ISO.match(h)]
            if dates != sorted(dates, reverse=True):
                findings.append(("log-order", rel, "date headings are not newest first"))
        elif is_meta(rel):
            stats["meta"] += 1
        else:
            stats["notes"] += 1
            concept_stems[name[:-3]].append(rel)
            fm, err = frontmatter(text)
            if err:
                findings.append((err, rel, ""))
            elif not str(fm.get("type") or "").strip():
                findings.append(("no-type", rel, ""))
            elif not str(fm.get("description") or "").strip():
                findings.append(("no-description", rel, ""))

        body = INLINE_CODE.sub("", FENCE.sub("", text))
        for t in MD_LINK.findall(body) + ["[[" + w.strip().rstrip("\\") + "]]" for w in WIKI_LINK.findall(body)]:
            if not alive(t.removesuffix("]]"), rel):
                ext = posixpath.splitext(t.removesuffix("]]").split("#")[0].rstrip("/"))[1].lower()
                asset = re.fullmatch(r"\.[a-z0-9]{1,5}", ext) and ext != ".md"
                findings.append(("missing-asset" if asset else "dead-link", rel, t))
        if name in ROUTING_FILES:
            for t in ROUTE.findall(text):
                if not alive(t, rel):
                    findings.append(("dead-route", rel, t))

    loaded = always_loaded(root)
    total = sum(loaded.values())
    stats["context_bytes"] = total
    if total > CONTEXT_MAX_BYTES:
        top = ", ".join(f"{os.path.relpath(p, root)} {n:,}" for p, n in sorted(loaded.items(), key=lambda x: -x[1])[:4])
        detail = (f"{total:,} bytes load on every agent turn (> {CONTEXT_MAX_BYTES:,}): {top}. "
                  "Scope rules with `paths:` or trim imports.")
        findings.append(("context-budget", "CLAUDE.md", detail))
    for stem, paths in concept_stems.items():
        if len(paths) > 1:
            findings.append(("duplicate-name", paths[0], f"{stem}.md x{len(paths)}: wikilinks are ambiguous"))
    for rel in files:
        if rel.endswith(".md") and is_inbox(rel) and not excluded(rel) and not rel.endswith(("/index.md", "/log.md")):
            low = rel.lower()
            if not ({low, posixpath.basename(low), posixpath.basename(low)[:-3]} & refs):
                findings.append(("unprocessed", rel, "no note links to it"))
    return stats, findings


def report(root, stats, findings, show_all):
    by_code = defaultdict(list)
    for code, rel, detail in findings:
        by_code[code].append((rel, detail))
    hard = sum(len(by_code[c]) for c in HARD)
    print(f"okf check {root}: {stats['notes']} notes, {stats['sources']} sources, {stats['meta']} meta, "
          f"{stats['index']} index.md, {stats['log']} log.md"
          + (f", {stats['context_bytes']:,} bytes always loaded" if stats["context_bytes"] else ""))
    for label, codes in (("HARD", HARD), ("WARN", sorted(set(by_code) - set(HARD)))):
        rows = [(c, len(by_code[c])) for c in codes if by_code[c]]
        if rows:
            print(f"{label}: " + ", ".join(f"{c} {n}" for c, n in rows))
    limit = None if show_all else 20
    for code in [c for c in HARD if by_code[c]] + sorted(set(by_code) - set(HARD)):
        items = by_code[code]
        for rel, detail in items[:limit]:
            print(f"  {rel}: {code}" + (f": {detail}" if detail else ""))
        if limit and len(items) > limit:
            print(f"  ... {len(items) - limit} more {code} (use --all)")
    print("conformant" if not hard else f"not conformant: {hard} hard failures")
    return hard


def ratchet(path, hard):
    """Fail only if hard failures rose above the count stored in `path`. Lower the count when it falls."""
    try:
        with open(path) as f:
            old = int(f.read().strip())
    except (FileNotFoundError, ValueError):
        old = None
    if old is not None and hard > old:
        print(f"okf: hard failures rose from {old} to {hard}. Fix the new ones, or commit with --no-verify.")
        return 1
    if hard != old:
        with open(path, "w") as f:
            f.write(f"{hard}\n")
        print(f"okf: baseline {'set to' if old is None else f'lowered from {old} to'} {hard} in {path}")
    return 0


def index(root, check_only=False, catalog=False):
    """Regenerate the okf:index block of every folder's index.md. Return the exit code."""
    cfg = load_config(root)
    skip = lambda rel: any(fnmatch.fnmatch(rel, g) for k in ("exclude", "sources", "inbox") for g in cfg[k])
    is_meta = lambda rel: any(fnmatch.fnmatch(rel, g) for g in cfg["meta"])
    one_line = lambda v: " ".join(str(v if v is not None else "").split())
    esc = lambda s: re.sub(r"([\\\[\]])", r"\\\1", s)

    def at(mark, text):  # a marker counts only on a line of its own, so inline mentions stay text
        m = re.search(rf"^{mark}\r?$", text, re.MULTILINE)
        return m.start() if m else -1

    def read(rel):
        try:
            with open(os.path.join(root, rel), encoding="utf-8", errors="surrogateescape", newline="") as f:
                return f.read()
        except FileNotFoundError:
            return None

    by_dir, tree = defaultdict(list), defaultdict(Counter)  # tree: folder -> type counts of every note beneath it
    had = set()  # folders with an index.md, so a stale block is emptied when its notes are gone
    for rel in sorted(walk(root)):
        name = posixpath.basename(rel)
        if name.lower() == "index.md" and not skip(rel):
            had.add(posixpath.dirname(rel))
        if not rel.endswith(".md") or name.lower() in ("index.md", "log.md") or skip(rel) or is_meta(rel):
            continue
        try:
            with open(os.path.join(root, rel), encoding="utf-8-sig", errors="replace") as f:
                text = f.read().replace("\r\n", "\n")
        except OSError:  # broken symlink, permissions: list it untyped
            text = ""
        fm, m = frontmatter(text)[0] or {}, FM.match(text)
        h1 = H1.search(FENCE.sub("", text[m.end():] if m else text))
        note = {"path": rel, "type": one_line(fm.get("type")),
                "title": one_line(fm.get("title")) or (h1.group(1).strip() if h1 else name[:-3]),
                "description": one_line(fm.get("description"))}
        if fm.get("updated"):
            note["updated"] = str(fm["updated"])
        d = posixpath.dirname(rel)
        by_dir[d].append(note)
        while True:
            tree[d][note["type"] or "Untyped"] += 1
            if not d:
                break
            d = posixpath.dirname(d)

    kids, keep = defaultdict(list), []
    for d in sorted(tree, key=lambda d: (-(d.count("/") + bool(d)), d)):  # deepest first
        if (by_dir[d] or kids[d]) and not skip(posixpath.join(d, "index.md")):
            keep.append(d)
            if d:
                kids[posixpath.dirname(d)].append(d)

    # ponytail: one index.md per folder, never split. `okf check` warns past INDEX_MAX_BYTES.
    # Split by type or by letter when big folders make that warning common.
    out = {}  # rel -> (old text, new text)
    for d in keep + sorted(had - set(keep)):
        sections = []
        if kids[d]:
            lines = []
            for k in sorted(kids[d], key=lambda k: (k.lower(), k)):
                n, name = sum(tree[k].values()), posixpath.basename(k)
                top = sorted(tree[k].items(), key=lambda x: (-x[1], x[0].lower(), x[0]))[:3]
                lines.append(f"* [{esc(name)}]({quote(name, safe='/')}/index.md) - {n} note{'s' * (n != 1)}: "
                             + ", ".join(f"{c} {t}" for t, c in top))
            sections.append(("Folders", lines))
        groups = defaultdict(list)
        for note in by_dir[d]:
            groups[note["type"]].append(note)
        for t in sorted(groups, key=lambda t: (not t, t.lower(), t)):  # untyped ("") last
            lines = [f"* [{esc(n['title'])}]({quote(posixpath.basename(n['path']), safe='/')})"
                     + (f" - {n['description']}" if n["description"] else "")
                     for n in sorted(groups[t], key=lambda n: (n["title"].lower(), n["path"]))]
            sections.append((t or "Untyped", lines))
        rel = posixpath.join(d, "index.md")
        if os.path.islink(os.path.join(root, rel)):
            continue  # never write through a symlink, it can point into sources
        old = read(rel)
        i, j = at(START, old or ""), at(END, old or "")
        if not sections and i < 0 and j < 0:
            continue  # nothing to list and no old block to empty
        nl = "\r\n" if "\r\n" in (old or "") else "\n"  # a CRLF file stays CRLF, so --check passes on CRLF checkouts
        block = START + "\n" + "\n\n".join(f"# {h}\n\n" + "\n".join(lines) for h, lines in sections) + "\n" + END
        block = block.replace("\n", nl)
        if old is None:
            new = block + "\n"
        elif 0 <= i < j:
            new = old[:i] + block + old[j + len(END):]
        elif i < 0 and j < 0:
            new = old + ("" if not old or old.endswith(nl * 2) else nl if old.endswith("\n") else nl * 2) + block + nl
        else:
            print(f"okf index: {rel} has an unmatched okf:index marker. Fix it, then run again.", file=sys.stderr)
            return 1
        out[rel] = (old, new)
    if catalog:
        rows = sorted((n for d in keep for n in by_dir[d]), key=lambda n: n["path"])
        out["catalog.jsonl"] = (read("catalog.jsonl"), "".join(json.dumps(n, ensure_ascii=False) + "\n" for n in rows))

    changed = sorted(rel for rel, (old, new) in out.items() if old != new)
    for rel in changed:
        if check_only:
            print(rel)
        else:
            with open(os.path.join(root, rel), "w", encoding="utf-8", errors="surrogateescape", newline="") as f:
                f.write(out[rel][1])
    print(f"okf index {root}: {'would change' if check_only else 'wrote'} {len(changed)}, "
          f"unchanged {len(out) - len(changed)}")
    return int(check_only and bool(changed))


def main(argv=None):
    ap = argparse.ArgumentParser(prog="okf", description=__doc__.split("\n\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("check", help="report conformance failures and warnings")
    c.add_argument("root", nargs="?", default=".")
    c.add_argument("--all", action="store_true", help="list every finding, not the first 20 per code")
    c.add_argument("--baseline", metavar="FILE",
                   help="exit 1 only if hard failures rise above the count in FILE, and lower it when they fall")
    i = sub.add_parser("index", help="write a generated listing into each folder's index.md")
    i.add_argument("root", nargs="?", default=".")
    i.add_argument("--check", action="store_true", help="write nothing, and exit 1 if any index.md would change")
    i.add_argument("--catalog", action="store_true", help="also write catalog.jsonl, one JSON line per note")
    a = ap.parse_args(argv)
    root = os.path.abspath(a.root)
    if not os.path.isdir(root):
        sys.exit(f"okf: {root} is not a folder")
    if a.cmd == "index":
        return index(root, a.check, a.catalog)
    stats, findings = check(root)
    hard = report(root, stats, findings, a.all)
    return ratchet(a.baseline, hard) if a.baseline else int(hard > 0)


if __name__ == "__main__":
    sys.exit(main())
