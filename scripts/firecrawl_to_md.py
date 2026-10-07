#!/usr/bin/env python3
"""Transform Firecrawl scrape JSON into knowledgebase markdown with rich frontmatter.

Usage:
    firecrawl_to_md.py --raw-dir <dir> --out-dir <dir> --site <slug> \
        --base-url <url> --scraped-date <YYYY-MM-DD>

Reads every *.json in --raw-dir (each a Firecrawl scrape result with top-level
keys: markdown, metadata, links), and writes one .md per page under --out-dir,
mirroring the URL path. Pages whose path is also a parent of other pages are
written as <path>/index.md to avoid file/dir collisions.
"""
import argparse
import glob
import json
import os
import re
import sys
from urllib.parse import urlparse


def strip_leading_doc_index_blockquote(md: str) -> str:
    """Drop a leading blockquote that is a Mintlify "Documentation Index" / llms.txt
    pointer. Mintlify injects this inside the main content, so onlyMainContent keeps
    it; it is pure chrome and pollutes both the body and any description derived from
    the first paragraph. Only removed when it is the very first block AND clearly the
    llms.txt pointer — a real leading blockquote is left untouched."""
    lines = md.split("\n")
    i = 0
    while i < len(lines) and not lines[i].strip():
        i += 1
    if i >= len(lines) or not lines[i].lstrip().startswith(">"):
        return md
    j = i
    while j < len(lines) and (lines[j].lstrip().startswith(">") or not lines[j].strip()):
        j += 1
        if lines[j - 1].strip() and not lines[j - 1].lstrip().startswith(">"):
            break
    text = " ".join(lines[i:j])
    if "Documentation Index" in text or "llms.txt" in text:
        return "\n".join(lines[j:]).lstrip("\n")
    return md


def clean_markdown(md: str, cut_re=None) -> str:
    md = strip_leading_doc_index_blockquote(md)
    lines = md.split("\n")
    # Drop leading site chrome before the first content line matching cut_re
    if cut_re:
        for i, ln in enumerate(lines):
            if cut_re.search(ln):
                lines = lines[i:]
                break
    out = []
    for line in lines:
        # Drop "Skip to content" / "Skip to main content" jump links
        if re.match(r"^\s*\[Skip to (?:main )?content\]\(", line):
            continue
        # Drop standalone Mintlify anchor-link chrome: a whole line that is only a
        # link whose text is empty / a zero-width space, or the literal "Navigate to
        # header" — these are heading permalinks emitted on their own line.
        if re.match(r"^\s*\[(?:[\s​]*|Navigate to header)\]\((?:https?://|#)[^)]*\)\s*$", line):
            continue
        # Drop redundant "Section titled ..." anchor links emitted under headings
        if re.match(r'^\s*\[Section titled [“"].*?[”"]\]\(', line):
            continue
        # Drop doc-site chrome rows (Adobe etc.)
        if re.match(r"^\s*\[Edit (in GitHub|this page)\]\(", line):
            continue
        if re.match(r"^\s*(Copy as Markdown|Copy page)\s*$", line):
            continue
        # Drop docs.rs nav-link rows: lines made up only of [Source]/[§]/[Search]/
        # [Settings]/[Help] links (a [Source] [§] pair sits by every method/impl).
        if re.search(r"\[(?:Source|Search|Settings|Help|§)\]\(", line):
            residue = re.sub(r"\[(?:Source|Search|Settings|Help|§)\]\([^)]*\)", "", line).strip()
            if residue == "":
                continue
        # Collapse a Mintlify leading-anchor heading back to plain text:
        #   ## [​](https://...#prerequisites)  Prerequisites  ->  ## Prerequisites
        # (the link text is empty / a zero-width space, with the real title after it)
        m = re.match(r"^(#{1,6})\s+\[[\s​]*\]\((?:https?://|#)[^)]*\)\s*(.+)$", line)
        if m:
            out.append(f"{m.group(1)} {m.group(2).strip()}")
            continue
        # Collapse a heading wrapped in a self-anchor link back to plain text:
        #   ## [System Dependencies](https://...#...)  ->  ## System Dependencies
        m = re.match(r"^(#{1,6})\s+\[(.+?)\]\((?:https?://|#)[^)]*\)\s*$", line)
        if m:
            out.append(f"{m.group(1)} {m.group(2)}")
            continue
        # Strip a trailing [anchor](url) glued onto heading text (Adobe style):
        #   ## Premiere Pro v26.2.0[premiere-pro-v2620](https://...#...)  ->  ## Premiere Pro v26.2.0
        m = re.match(r"^(#{1,6}\s+.*?)\[[^\]]+\]\((?:https?://|#)[^)]*\)\s*$", line)
        if m:
            out.append(m.group(1).rstrip())
            continue
        out.append(line)
    text = "\n".join(out)
    # docs.rs glues "Copy item path" onto the rustdoc title heading
    text = re.sub(r"Copy item path", "", text)
    # Collapse 3+ blank lines to 2
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip() + "\n"


def first_paragraph(md: str) -> str:
    """First real prose paragraph, for use as a page-specific description."""
    for block in re.split(r"\n\s*\n", md):
        b = block.strip()
        if not b or b.startswith("#") or b.startswith("[") or b.startswith("|"):
            continue
        # Skip rustdoc availability boilerplate (docs.rs)
        if b.startswith("Available on crate feature") or b == "Expand description":
            continue
        b = re.sub(r"^Available on crate features?[^.]*\.\s*", "", b)
        b = b.replace("Expand description", "").strip()
        # Skip badge/link rows: blocks that are mostly markdown links
        link_text = "".join(re.findall(r"\[([^\]]+)\]\([^)]*\)", b))
        non_link = re.sub(r"\[[^\]]+\]\([^)]*\)", "", b)
        if len(link_text) > len(non_link):
            continue
        # strip markdown links -> text, and inline code/formatting markers
        b = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", b)
        b = re.sub(r"[`*_]", "", b)
        b = " ".join(b.split())
        # Require sentence-like prose: enough words and a sentence terminator
        if len(b) < 40 or len(b.split()) < 8 or not re.search(r"[.!?]", b):
            continue
        return (b[:197] + "...") if len(b) > 200 else b
    return ""


def yaml_escape(s: str) -> str:
    s = s.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{s}"'


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw-dir", required=True)
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--site", required=True)
    ap.add_argument("--base-url", required=True)
    ap.add_argument("--scraped-date", required=True)
    ap.add_argument("--strip-title-suffix", default="",
                    help="regex stripped from the end of each title (e.g. '\\s*\\|\\s*Tauri\\s*$')")
    ap.add_argument("--base-tags", default="",
                    help="comma-separated tags prepended to every doc's tag list")
    ap.add_argument("--strip-path-prefix", default="",
                    help="URL path prefix removed before mirroring (e.g. '/premiere-pro/uxp')")
    ap.add_argument("--cut-before", default="",
                    help="drop everything before the first line matching this regex "
                         "(strips leading site chrome/sidebars, e.g. docs.rs). No-op if unmatched.")
    ap.add_argument("--skip-404", action="store_true",
                    help="skip pages whose title/content indicate a 404")
    args = ap.parse_args()
    cut_re = re.compile(args.cut_before) if args.cut_before else None
    base_tags = [t.strip() for t in args.base_tags.split(",") if t.strip()]

    base_host = urlparse(args.base_url).netloc

    # First pass: collect (relpath, record) for every page
    records = []
    for jf in sorted(glob.glob(os.path.join(args.raw_dir, "*.json"))):
        with open(jf) as f:
            data = json.load(f)
        meta = data.get("metadata") or {}
        md = data.get("markdown") or ""
        if not md.strip():
            print(f"  ! skip (empty markdown): {jf}", file=sys.stderr)
            continue
        title_meta = (meta.get("ogTitle") or meta.get("title") or "")
        if args.skip_404 and (re.search(r"\b404\b|Page not found", title_meta)
                              or re.search(r"Error 404: Page not found", md)):
            print(f"  ! skip (404): {jf}", file=sys.stderr)
            continue
        src = meta.get("sourceURL") or meta.get("url") or ""
        path = urlparse(src).path
        if args.strip_path_prefix and path.startswith(args.strip_path_prefix):
            path = path[len(args.strip_path_prefix):]
        path = path.strip("/")
        # drop a trailing .html so docs.rs items become clean .md names
        path = path.removesuffix(".html")
        rel = path if path else "index"
        records.append({"rel": rel, "meta": meta, "md": md, "src": src})

    # Determine which rel-paths are also parents of others -> need index.md
    all_rels = {r["rel"] for r in records}
    parents = set()
    for rel in all_rels:
        parts = rel.split("/")
        for i in range(1, len(parts)):
            parents.add("/".join(parts[:i]))

    written = 0
    for r in records:
        rel = r["rel"]
        meta = r["meta"]
        md = clean_markdown(r["md"], cut_re)

        out_rel = f"{rel}/index.md" if rel in parents else f"{rel}.md"
        out_path = os.path.join(args.out_dir, out_rel)
        os.makedirs(os.path.dirname(out_path), exist_ok=True)

        title = (meta.get("ogTitle") or meta.get("title") or rel).strip()
        if args.strip_title_suffix:
            title = re.sub(args.strip_title_suffix, "", title)
        # Prefer Firecrawl's clean page metadata (human-written meta description) and
        # fall back to the first-paragraph heuristic only when it is absent. The
        # metadata is already fetched and is reliably cleaner than anything we can
        # reconstruct from the body.
        meta_desc = (meta.get("description") or meta.get("ogDescription") or "").strip()
        desc = meta_desc or first_paragraph(md)
        first = rel.split("/")[0]
        if rel == "index":
            section = "root"
        elif "." in first:           # docs.rs items: struct.NSWindow -> "struct"
            section = first.split(".")[0]
        else:
            section = first

        # tags: configured base tags + path segments
        segs = [s for s in rel.split("/") if s and s != "index"]
        tags = base_tags + segs[:2]
        tags = list(dict.fromkeys(tags))  # dedupe, preserve order

        fm = ["---"]
        fm.append(f"title: {yaml_escape(title)}")
        if desc:
            fm.append(f"description: {yaml_escape(desc)}")
        fm.append(f"source_url: {yaml_escape(r['src'])}")
        fm.append(f"site: {yaml_escape(args.site)}")
        fm.append(f"site_host: {yaml_escape(base_host)}")
        fm.append(f"section: {yaml_escape(section)}")
        fm.append("tags: [" + ", ".join(yaml_escape(t) for t in tags) + "]")
        fm.append(f"language: {yaml_escape(meta.get('language') or 'en')}")
        fm.append(f"scraped_date: {args.scraped_date}")
        fm.append("---")
        fm.append("")

        with open(out_path, "w") as f:
            f.write("\n".join(fm))
            f.write(md)
        written += 1
        print(f"  + {out_rel}")

    print(f"\nWrote {written} markdown files to {args.out_dir}")


if __name__ == "__main__":
    main()
