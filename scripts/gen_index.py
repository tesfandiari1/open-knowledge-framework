#!/usr/bin/env python3
"""Generate a CONTENTS.md manifest for a knowledgebase site folder, grouped by section.

Note: the manifest is named CONTENTS.md (not INDEX.md) because case-insensitive
filesystems (macOS) would treat INDEX.md and a scraped index.md homepage as the
same file, clobbering the homepage.

Usage: gen_index.py <site-dir> "<Human Title>"
"""
import glob
import os
import re
import sys
from collections import defaultdict


def read_fm(path):
    txt = open(path).read()
    if not txt.startswith("---\n"):
        return {}
    fm = txt.split("---\n", 2)[1]
    d = {}
    for line in fm.splitlines():
        m = re.match(r"^(\w+):\s*(.*)$", line)
        if m:
            v = m.group(2).strip()
            if len(v) > 1 and v[0] == v[-1] == '"':  # undo firecrawl_to_md.yaml_escape
                v = re.sub(r"\\(.)", r"\1", v[1:-1])
            d[m.group(1)] = v
    return d


def main():
    site_dir = sys.argv[1].rstrip("/")
    title = sys.argv[2] if len(sys.argv) > 2 else os.path.basename(site_dir)
    groups = defaultdict(list)
    date = ""
    host = ""
    for f in sorted(glob.glob(os.path.join(site_dir, "**", "*.md"), recursive=True)):
        if os.path.basename(f) == "CONTENTS.md":
            continue
        d = read_fm(f)
        rel = os.path.relpath(f, site_dir)
        groups[d.get("section", "root")].append((rel, d.get("title", rel), d.get("description", "")))
        date = date or d.get("scraped_date", "")
        host = host or d.get("site_host", "")
    n = sum(len(v) for v in groups.values())
    out = [f"# {title} — Index", "",
           f"{n} documents scraped from {host} on {date}.", "",
           "Each doc carries YAML frontmatter (`title`, `description`, `source_url`, "
           "`section`, `tags`, …). See ../SOURCES.md for how this folder is scraped.", ""]
    for sec in sorted(groups):
        out.append(f"## {sec}")
        out.append("")
        for rel, t, desc in sorted(groups[sec]):
            desc = (desc[:110] + "…") if len(desc) > 110 else desc
            out.append(f"- [{t}]({rel})" + (f" — {desc}" if desc else ""))
        out.append("")
    open(os.path.join(site_dir, "CONTENTS.md"), "w").write("\n".join(out))
    print(f"Wrote {site_dir}/CONTENTS.md — {n} entries, {len(groups)} sections")


if __name__ == "__main__":
    main()
