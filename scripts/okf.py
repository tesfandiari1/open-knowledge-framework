#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = ["pyyaml>=6"]
# ///
"""okf: keep a folder of Markdown files conformant with the Open Knowledge Format.

    uv run scripts/okf.py check [ROOT] [--all]

Hard failures (exit 1) are the OKF conformance rules, identical in v0.1 and v0.2:
every non-reserved .md has parseable frontmatter with a non-empty `type`, and every
index.md / log.md is well formed. Everything else is a warning. Files that match a
`sources` glob (default: raw/ folders) are immutable sources and skip all checks.
Files that match an `inbox` glob also skip checks, and each one that no note links to
is reported as unprocessed.
Files that match a `meta` glob (default: README, AGENTS, CLAUDE) skip conformance
but keep their link checks. Optional config: ROOT/okf.toml (see okf.toml.example).
"""
import argparse
import fnmatch
import os
import posixpath
import re
import sys
from collections import Counter, defaultdict
from urllib.parse import unquote

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
HARD = ("no-frontmatter", "bad-frontmatter", "no-type", "index-frontmatter", "log-heading", "log-order")

FM = re.compile(r"---[ \t]*\n(.*?)^---[ \t]*$", re.DOTALL | re.MULTILINE)
FENCE = re.compile(r"^(```|~~~).*?^\1", re.DOTALL | re.MULTILINE)
INLINE_CODE = re.compile(r"`[^`\n]*`")
MD_LINK = re.compile(r"\[[^\]]*\]\(<?([^)\s>]+)>?(?:\s+\"[^\"]*\")?\)")
WIKI_LINK = re.compile(r"\[\[([^\]|#^]+)")
ROUTE = re.compile(r"`(/?[\w.+@-]+(?:/[\w.+@-]+)*(?:\.md|/))`")
H2 = re.compile(r"^## +(.*)$", re.MULTILINE)
ISO = re.compile(r"\d{4}-\d{2}-\d{2}")
SCHEME = re.compile(r"^[a-z][a-z0-9+.-]*:", re.IGNORECASE)


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
          f"{stats['index']} index.md, {stats['log']} log.md")
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
    return 1 if hard else 0


def main(argv=None):
    ap = argparse.ArgumentParser(prog="okf", description=__doc__.split("\n\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("check", help="report conformance failures and warnings")
    c.add_argument("root", nargs="?", default=".")
    c.add_argument("--all", action="store_true", help="list every finding, not the first 20 per code")
    a = ap.parse_args(argv)
    root = os.path.abspath(a.root)
    stats, findings = check(root)
    return report(root, stats, findings, a.all)


if __name__ == "__main__":
    sys.exit(main())
