#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = ["pyyaml>=6"]
# ///
"""Fixture test for scripts/okf.py. Run: uv run tests/test_okf.py"""
import contextlib
import importlib.util
import io
import json
import os
import subprocess
import tempfile
from collections import Counter
from pathlib import Path

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

# Context budget: CLAUDE.md, its @imports, and unscoped rules count. Scoped rules do not.
c = codes(bundle({
    "CLAUDE.md": "Rules. @docs/big.md and `@ignored.md` and mail me@example.com\n",
    "docs/big.md": "---\ntype: Reference\ndescription: Big.\n---\n" + "x" * 9000,
    ".claude/rules/general.md": "y" * 8000,
    ".claude/rules/scoped.md": "---\npaths: [\"docs/*\"]\n---\n" + "z" * 50000,
}))
assert c == Counter({"context-budget": 1}), c
assert okf.always_loaded(bundle({"CLAUDE.md": "small"})) and not codes(bundle({"CLAUDE.md": "small"}))

# Ratchet: set the baseline, fail when hard failures rise, lower it when they fall.
root = bundle({"a.md": "---\ntype: Concept\n---\n"})
base = os.path.join(root, ".okf-baseline")
quiet = lambda: contextlib.redirect_stdout(io.StringIO())
with quiet():
    assert okf.main(["check", root, "--baseline", base]) == 0 and Path(base).read_text() == "0\n"
    Path(os.path.join(root, "b.md")).write_text("no frontmatter\n")
    assert okf.main(["check", root, "--baseline", base]) == 1 and Path(base).read_text() == "0\n"
    Path(base).write_text("5\n")
    assert okf.main(["check", root, "--baseline", base]) == 0 and Path(base).read_text() == "1\n"

# The real pre-commit hook in a throwaway git repo.
repo = bundle({"good.md": "---\ntype: Concept\n---\n"})
env = {**os.environ, "OKF_HOME": os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))}
git = lambda *a: subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t", *a],
                                cwd=repo, env=env, capture_output=True, text=True, check=False)
git("init", "-q")
os.symlink(os.path.join(env["OKF_HOME"], "hooks", "pre-commit"), os.path.join(repo, ".git", "hooks", "pre-commit"))
git("add", "good.md")
assert git("commit", "-qm", "first").returncode == 0
assert git("show", "HEAD:.okf-baseline").stdout == "0\n", "baseline committed with the first commit"
Path(os.path.join(repo, "bad.md")).write_text("no frontmatter\n")
git("add", "bad.md")
r = git("commit", "-qm", "bad")
assert r.returncode == 1 and "bad.md: no-frontmatter" in r.stdout + r.stderr, r.stdout + r.stderr
assert git("commit", "-qm", "bad", "--no-verify").returncode == 0
Path(os.path.join(repo, "bad.md")).write_text("---\ntype: Concept\n---\n")
git("add", "bad.md")
assert git("commit", "-qm", "fixed").returncode == 0

# index: layout, sort order, untouched bytes, sources left alone, idempotent, --check.
intro = '---\nokf_version: "0.2"\n---\n# Team notes\n\nHand-written intro.\n'
scraped = "A scraped page that happens to be named index.md\n"
root = bundle({
    "index.md": intro,
    "zeta.md": "---\ntype: Concept\ntitle: Zeta\ndescription: Two\n  lines.\n---\n",
    "alpha.md": "---\ntype: Concept\ndescription: Title from the heading.\n---\n```\n# not a title\n```\n# Alpha [beta]\n",
    "my note.md": "---\ntype: playbook\n---\nNo title, no description.\n",
    "ref.md": "---\ntype: Reference\ndescription: R.\n---\n",
    "loose.md": "No frontmatter.\n",
    "broken.md": "---\ntype: [\n---\n# Broken\n",
    "README.md": "# Meta, not listed\n",
    "log.md": "# Log\n",
    "sub/x.md": "---\ntype: Playbook\ndescription: X.\n---\n",
    "sub/deep/y.md": "---\ntype: Concept\n---\n",
    "raw/index.md": scraped,
    "raw/page.md": "scraped\n",
    "meta-only/README.md": "# Only meta\n",
})


def run(*a):
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        code = okf.main(["index", root, *a])
    return code, buf.getvalue()
read = lambda rel: Path(root, rel).read_text()
block = """<!-- okf:index:start -->
# Folders

* [sub](sub/index.md) - 2 notes: 1 Concept, 1 Playbook

# Concept

* [Alpha \\[beta\\]](alpha.md) - Title from the heading.
* [Zeta](zeta.md) - Two lines.

# playbook

* [my note](my%20note.md)

# Reference

* [ref](ref.md) - R.

# Untyped

* [Broken](broken.md)
* [loose](loose.md)
<!-- okf:index:end -->
"""
assert run() == (0, f"okf index {root}: wrote 3, unchanged 0\n")
assert read("index.md") == intro + "\n" + block, read("index.md")
assert read("sub/index.md") == ("<!-- okf:index:start -->\n# Folders\n\n* [deep](deep/index.md) - 1 note: 1 Concept\n\n"
                                "# Playbook\n\n* [x](x.md) - X.\n<!-- okf:index:end -->\n"), read("sub/index.md")
assert read("sub/deep/index.md") == "<!-- okf:index:start -->\n# Concept\n\n* [y](y.md)\n<!-- okf:index:end -->\n"
assert read("raw/index.md") == scraped and not os.path.exists(os.path.join(root, "meta-only", "index.md"))
assert run() == (0, f"okf index {root}: wrote 0, unchanged 3\n")
assert run("--check") == (0, f"okf index {root}: would change 0, unchanged 3\n")
assert not [f for f in okf.check(root)[1] if f[1].endswith("index.md")], okf.check(root)[1]
Path(root, "index.md").write_text(read("index.md") + "\nFooter.\n")
Path(root, "new.md").write_text("---\ntype: Concept\ndescription: New.\n---\n")
before = read("index.md")
assert run("--check") == (1, f"index.md\nokf index {root}: would change 1, unchanged 2\n")
assert read("index.md") == before, "--check writes nothing"
run()
assert read("index.md") == intro + "\n" + block.replace("* [Zeta]", "* [new](new.md) - New.\n* [Zeta]") + "\nFooter.\n"
Path(root, "sub/index.md").write_text("<!-- okf:index:start -->\nhand edit, no end marker\n")
with contextlib.redirect_stderr(io.StringIO()):
    assert run()[0] == 1 and read("sub/index.md") == "<!-- okf:index:start -->\nhand edit, no end marker\n"

# index --catalog: one JSON line per indexed note, sorted by path.
Path(root, "sub/index.md").unlink()
Path(root, "dated.md").write_text("---\ntype: Concept\ntitle: Dated\nupdated: 2026-01-02\n---\n")
assert run("--catalog")[0] == 0
rows = [json.loads(line) for line in read("catalog.jsonl").splitlines()]
assert [r["path"] for r in rows] == ["alpha.md", "broken.md", "dated.md", "loose.md", "my note.md", "new.md",
                                     "ref.md", "sub/deep/y.md", "sub/x.md", "zeta.md"], rows
assert rows[2] == {"path": "dated.md", "type": "Concept", "title": "Dated", "description": "", "updated": "2026-01-02"}
assert rows[3] == {"path": "loose.md", "type": "", "title": "loose", "description": ""}, rows[3]
assert run("--catalog", "--check")[0] == 0

# index review fixes: inline marker mentions stay text, a trailing backslash keeps the link, a symlink into
# raw/ is never written, a folder whose notes are gone gets an empty block, a CRLF checkout passes --check.
doc = "# Doc\n\nThe tool writes between `<!-- okf:index:start -->` and `<!-- okf:index:end -->`.\n"
root = bundle({
    "index.md": doc,
    "m.md": "---\ntype: Concept\ntitle: 'C:\\dir\\'\ndescription: 'see <!-- okf:index:end --> here'\n---\n",
    "gone/old.md": "---\ntype: Concept\n---\n",
    "topic/raw/index.md": scraped,
    "topic/n.md": "---\ntype: Concept\n---\n",
})
os.symlink("raw/index.md", os.path.join(root, "topic", "index.md"))
assert run()[0] == 0 and run() == (0, f"okf index {root}: wrote 0, unchanged 2\n")
assert read("index.md").startswith(doc + "\n<!-- okf:index:start -->\n"), read("index.md")
assert "* [C:\\\\dir\\\\](m.md) - see <!-- okf:index:end --> here\n" in read("index.md"), read("index.md")
assert read("topic/raw/index.md") == scraped
assert not [f for f in okf.check(root)[1] if f[1].endswith("index.md")], okf.check(root)[1]
Path(root, "gone/old.md").unlink()
run()
assert read("gone/index.md") == "<!-- okf:index:start -->\n\n<!-- okf:index:end -->\n", read("gone/index.md")
Path(root, "index.md").write_bytes(Path(root, "index.md").read_bytes().replace(b"\n", b"\r\n"))
assert run("--check")[0] == 0
try:
    okf.main(["index", os.path.join(root, "nope"), "--catalog"])
except SystemExit as e:
    assert "is not a folder" in str(e), e
else:
    raise AssertionError("a missing root must fail")
print("ok")
