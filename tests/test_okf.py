#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = ["pyyaml>=6"]
# ///
"""Fixture test for scripts/okf.py. Run: uv run tests/test_okf.py"""
import importlib.util
import os
import tempfile
from collections import Counter

spec = importlib.util.spec_from_file_location("okf", os.path.join(os.path.dirname(__file__), "..", "scripts", "okf.py"))
okf = importlib.util.module_from_spec(spec)
spec.loader.exec_module(okf)


def bundle(files):
    root = tempfile.mkdtemp()
    for rel, text in files.items():
        os.makedirs(os.path.dirname(os.path.join(root, rel)), exist_ok=True)
        with open(os.path.join(root, rel), "w") as f:
            f.write(text)
    return root


def codes(root):
    return Counter(code for code, _, _ in okf.check(root)[1])


# The plan's Phase 1 check: good, no type, bad YAML -> exactly 2 hard failures.
three = codes(bundle({
    "good.md": "---\ntype: Concept\ndescription: A good note.\n---\n# Good\n",
    "no-type.md": "---\ntitle: No type\n---\n",
    "bad-yaml.md": "---\ntype: Concept\ntitle: a: b\n---\n",
}))
assert sum(three[c] for c in okf.HARD) == 2, three
assert three["no-type"] == 1 and three["bad-frontmatter"] == 1, three

# Reserved files, both link styles, routes, sources, and excludes.
c = codes(bundle({
    "index.md": "---\nokf_version: \"0.1\"\n---\n# Notes\n* [Good](notes/good.md) - ok\n",
    "notes/index.md": "---\ntitle: x\n---\n* [Gone](gone.md) - dead\n",
    "notes/good.md": "---\ntype: Concept\ndescription: Links.\n---\n[[other]] [[missing]] [x](/notes/other.md)\n"
                     "[r](notes/other.md) [b](other.md) [[notes/other]] [[v0.1 plan]] ![p](pic.png)\n"
                     "`[[in-code]]`\n```\n[x](fenced.md)\n```\n[[2026-01-01-call]]\n",
    "notes/other.md": "---\ntype: Concept\n---\n[web](https://example.com) [a](#top)\n",
    "notes/log.md": "# Log\n\n## 2026-01-01\n* x\n\n## 2026-02-01\n* y\n\n## Notes\n",
    "AGENTS.md": "---\ntype: Reference\ndescription: Routing.\n---\nRead `notes/good.md` then `/TASKS.md` and `notes/`.\n",
    "raw/2026-01-01-call.md": "transcript, no frontmatter, referenced\n",
    "raw/2026-01-02-call.md": "transcript, never referenced\n",
    "archive/old.md": "no frontmatter, but excluded\n",
    "README.md": "# Meta file, no frontmatter, still link-checked: [x](nowhere.md)\n",
    "wiki/index.md": "---\nokf_version: \"0.2\"\n---\n# A nested bundle root\n",
    "okf.toml": 'exclude = ["archive/*"]\ninbox = ["raw/*"]\n',
}))
expected = {
    "index-frontmatter": 1,    # notes/index.md has frontmatter. The root okf_version is allowed.
    "dead-link": 4,            # [[missing]], [[v0.1 plan]], gone.md, nowhere.md. Code and fences are ignored.
    "missing-asset": 1,        # pic.png
    "dead-route": 1,           # `/TASKS.md`
    "log-order": 1,            # 2026-01-01 before 2026-02-01
    "log-heading": 1,          # "## Notes"
    "no-description": 1,       # notes/other.md
    "unprocessed": 1,          # raw/2026-01-02-call.md is in the inbox and nothing links to it
}
assert dict(c) == expected, dict(c)
print("ok")
