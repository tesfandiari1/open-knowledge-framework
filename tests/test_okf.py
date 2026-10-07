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

# A space is checked at its root, but its bundle is wiki/, so a /link resolves from the nearest okf_version root.
# Other folders above the note are not roots: a/x.md does not make /x.md alive from a/b/.
c = okf.check(bundle({
    "wiki/index.md": '---\nokf_version: "0.1"\n---\n',
    "wiki/log.md": "# Log\n\n## 2026-01-01\n* [s](/sources/s.md)\n",
    "wiki/sources/s.md": "---\ntype: Source\ndescription: S.\n---\n[e](/entities/e.md) [gone](/entities/gone.md)\n",
    "wiki/entities/e.md": "---\ntype: Entity\ndescription: E.\n---\n",
    "a/x.md": "---\ntype: Entity\ndescription: X.\n---\n",
    "a/b/t.md": "---\ntype: Source\ndescription: S.\n---\n[x](/x.md)\n",
}))[1]
assert c == [("dead-link", "a/b/t.md", "/x.md"), ("dead-link", "wiki/sources/s.md", "/entities/gone.md")], c

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
assert rows[3] == {"path": "loose.md", "type": "", "title": "loose", "description": "", "updated": ""}, rows[3]
assert run("--catalog", "--check")[0] == 0
Path(root, "dated.md").write_text("---\ntype: Concept\ntimestamp: '2026-05-28T22:53:05+00:00'\n"
                                  "generated: { by: agent, at: 2026-06-30T14:00:00Z }\n---\n")
Path(root, "new.md").write_text("---\ntype: Concept\ngenerated: { by: agent, at: 2026-06-30T14:00:00Z }\n---\n")
run("--catalog")
rows = {r["path"]: r["updated"] for r in map(json.loads, read("catalog.jsonl").splitlines())}
assert (rows["dated.md"], rows["new.md"]) == ("2026-05-28T22:53:05+00:00", "2026-06-30T14:00:00+00:00"), rows

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

# C4: escaped brackets in a generated title are text, so check sees one live link, not a dead "v2".
root = bundle({"t.md": "---\ntype: Concept\ntitle: '[Draft](v2) plan [x]'\ndescription: T.\n---\n"})
run()
assert "* [\\[Draft\\](v2) plan \\[x\\]](t.md) - T.\n" in read("index.md"), read("index.md")
assert not [f for f in okf.check(root)[1] if f[1] == "index.md"], okf.check(root)[1]  # t.md's own YAML still links v2
out = io.StringIO()
with contextlib.redirect_stdout(out):
    Path(root, ".okf-baseline").write_text("0\n")
    assert okf.ratchet(os.path.join(root, ".okf-baseline"), 1) == 1
assert "--no-verify" not in out.getvalue(), out.getvalue()

# C1: a hand-written index is skipped by default and does not count as a change for --check.
hand = "# Notes\n\n* [A](a.md) - Hand-written.\n"
root = bundle({"index.md": hand, "a.md": "---\ntype: Concept\ndescription: A.\n---\n"})
assert run() == (0, f"okf index {root}: wrote 0, unchanged 0, skipped 1 hand-written (use --adopt)\n")
assert run("--check") == (0, f"okf index {root}: would change 0, unchanged 0, skipped 1 hand-written (use --adopt)\n")
assert read("index.md") == hand

# C1: --adopt on a Google-style index keeps frontmatter, prose, external and unmatched links, and drops
# bullets the block lists plus the headings they leave empty. A rerun is idempotent.
root = bundle({
    "index.md": '---\nokf_version: "0.2"\n---\n# Acme\n\nIntro prose stays.\n\n# Subdirectories\n\n'
                "* [tables](tables/index.md) - Tables.\n* [attesters](attesters/index.md) - Code, no notes.\n\n"
                "# Metric\n\n* [Revenue](revenue.md) - Hand text.\n* [[margin]]\n\n\n\n"
                "# Elsewhere\n\n* [Spec](https://example.com/spec) - External.\n",
    "revenue.md": "---\ntype: Metric\ntitle: Revenue\ndescription: Money in.\n---\n",
    "margin.md": "---\ntype: Metric\ntitle: Margin\ndescription: Money kept.\n---\n",
    "tables/index.md": "# BigQuery Table\n\n* [Orders](orders.md) - Orders.\n",
    "tables/orders.md": "---\ntype: BigQuery Table\ntitle: Orders\ndescription: Orders.\n---\n",
    "attesters/index.md": "# Attesters\n\n* [sql_equality.py](sql_equality.py)\n",
    "attesters/sql_equality.py": "pass\n",
})
assert run()[1].endswith("skipped 2 hand-written (use --adopt)\n")
assert run("--adopt") == (0, f"okf index {root}: wrote 2, unchanged 0\n")
assert read("index.md") == (
    '---\nokf_version: "0.2"\n---\n# Acme\n\nIntro prose stays.\n\n# Subdirectories\n\n'
    "* [attesters](attesters/index.md) - Code, no notes.\n\n# Elsewhere\n\n* [Spec](https://example.com/spec) - External.\n"
    "\n<!-- okf:index:start -->\n# Folders\n\n* [tables](tables/index.md) - 1 note: 1 BigQuery Table\n\n"
    "# Metric\n\n* [Margin](margin.md) - Money kept.\n* [Revenue](revenue.md) - Money in.\n<!-- okf:index:end -->\n"
), read("index.md")
assert read("tables/index.md") == ("<!-- okf:index:start -->\n# BigQuery Table\n\n* [Orders](orders.md) - Orders.\n"
                                   "<!-- okf:index:end -->\n"), read("tables/index.md")
assert read("attesters/index.md") == "# Attesters\n\n* [sql_equality.py](sql_equality.py)\n", "no notes, untouched"
assert run("--adopt") == (0, f"okf index {root}: wrote 0, unchanged 2\n") and run()[1].endswith("unchanged 2\n")
assert codes(root) == Counter(), codes(root)

# C2: past INDEX_MAX_BYTES entries drop descriptions, then each type becomes one line. Folders stay in full.
root = bundle({**{f"big/n{i:02}.md": f"---\ntype: Concept\ndescription: {'d' * 150}\n---\n" for i in range(60)},
               **{f"huge/{'t' * 40}{i:03}.md": "---\ntype: Concept\ndescription: D.\n---\n" for i in range(200)},
               "huge/sub/s.md": "---\ntype: Playbook\n---\n", "huge/x.md": "---\ntype: Recipe\n---\n"})
run()
big, huge = read("big/index.md"), read("huge/index.md")
assert len(big.encode()) <= okf.INDEX_MAX_BYTES and "* [n00](n00.md)\n" in big and " - d" not in big, big
assert huge == ("<!-- okf:index:start -->\n# Folders\n\n* [sub](sub/index.md) - 1 note: 1 Playbook\n\n"
                "# Concept\n\n* 200 notes. Search catalog.jsonl (okf index --catalog) or grep.\n\n"
                "# Recipe\n\n* 1 note. Search catalog.jsonl (okf index --catalog) or grep.\n<!-- okf:index:end -->\n"), huge
assert run() == (0, f"okf index {root}: wrote 0, unchanged 4\n")

# C3: [types] in okf.toml turns unknown types and aliases into warnings, and `types` counts each value.
# Another case of an approved type is an alias, because index would list it under its own heading.
notes = {"a.md": "Concept", "b.md": "Concept", "c.md": "concept", "d.md": "Runbook", "e.md": "Recipe"}
root = bundle({p: f"---\ntype: {t}\ndescription: X.\n---\n" for p, t in notes.items()})
assert codes(root) == Counter()


def types_out():
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        assert okf.main(["types", root]) == 0
    return buf.getvalue()


assert types_out() == ("     2  Concept\n     1  concept\n     1  Recipe\n     1  Runbook\n"
                       "top 20 types cover 100% of typed notes\n"), types_out()
Path(root, "okf.toml").write_text('[types]\nConcept = []\nPlaybook = ["play", "runbook"]\n')
found = okf.check(root)[1]
assert sorted(f for f in found if f[0] == "unknown-type") == [("unknown-type", "c.md", "alias of Concept"),
    ("unknown-type", "d.md", "alias of Playbook"), ("unknown-type", "e.md", "not in okf.toml [types]")], found
assert not [f for f in found if f[0] in okf.HARD], found
assert types_out() == ("     2  Concept  approved\n     1  concept  alias of Concept\n     1  Recipe  unknown\n"
                       "     1  Runbook  alias of Playbook\ntop 20 types cover 100% of typed notes\n"), types_out()
root = bundle({f"n{i}.md": f"---\ntype: T{i:02}\n---\n" for i in range(21)} | {"m.md": "---\ntype: T00\n---\n"})
assert types_out().endswith("top 20 types cover 95% of typed notes\n"), types_out()  # 21 of 22

# Review fixes: --adopt keeps a bullet that also holds an unmatched link and leaves bullets in code fences.
# <angle links> with spaces are links. A bad date or a malformed [types] does not crash.
note = "---\ntype: Concept\ndescription: N.\n---\n"
root = bundle({"index.md": "# Notes\n\n* [A](a.md) - PDF: [a.pdf](a.pdf)\n* [B](<b c.md>)\n* [D](d.md) and [[a]]\n\n"
                           "```md\n* [A](a.md)\n```\n", "a.md": note, "b c.md": note, "d.md": note})
assert okf.MD_LINK.findall('[x](<a b.md>) [y](c.md "t")') == ["a b.md", "c.md"]
run("--adopt")
assert read("index.md").startswith("# Notes\n\n* [A](a.md) - PDF: [a.pdf](a.pdf)\n\n```md\n* [A](a.md)\n```\n\n"
                                   "<!-- okf:index:start -->"), read("index.md")
root = bundle({"index.md": "# Links\n\n```md\n* [A](a.md)\n```\n", "a.md": note})
assert run() == (0, f"okf index {root}: wrote 1, unchanged 0\n"), "a fenced bullet is not a hand-written listing"
root = bundle({"d.md": "---\ntype: Concept\nupdated: 2026-13-45\n---\n"})
assert codes(root) == Counter({"bad-frontmatter": 1}) and run()[0] == 0 and types_out().startswith("top 20")
for toml in ('types = ["Concept"]\n', '[types]\nConcept = "con"\n'):
    Path(root, "okf.toml").write_text(toml)
    try:
        okf.load_config(root)
    except SystemExit as e:
        assert "[types]" in str(e), e
    else:
        raise AssertionError(f"{toml!r} must fail with a clear message")

# Second review: --adopt drops only what this folder's own block lists, and keeps a bullet with lines under it.
# A /link resolves from the bundle root. A bullet to a file the block never lists does not mark the index
# hand-written. Numbered items count. Long hand text does not shrink the block. Bad list keys fail clearly.
root = bundle({
    "wiki/index.md": '---\nokf_version: "0.1"\n---\n# Notes\n\n* [A](/a.md)\n1. [B](b.md)\n* [Deep](sub/x.md)\n'
                     "* [C](c.md) - wraps\n  onto a second line\n\n```py\nx = 1\n\n\n\ny = 2\n```\n",
    "wiki/a.md": note, "wiki/b.md": note, "wiki/c.md": note, "wiki/sub/x.md": note,
})
assert run()[1].endswith("skipped 1 hand-written (use --adopt)\n")
run("--adopt")
assert read("wiki/index.md").startswith('---\nokf_version: "0.1"\n---\n# Notes\n\n* [Deep](sub/x.md)\n'
                                        "* [C](c.md) - wraps\n  onto a second line\n\n```py\nx = 1\n\n\n\ny = 2\n```\n"
                                        ), read("wiki/index.md")
root = bundle({"index.md": "# Topic\n\n* [Site](raw/site/CONTENTS.md)\n" + "Hand text.\n" * 900, "a.md": note,
               "raw/site/CONTENTS.md": "x\n"})
assert run() == (0, f"okf index {root}: wrote 1, unchanged 0\n") and "* [a](a.md) - N.\n" in read("index.md")
for toml in ('inbox = "raw/*"\n', '[types]\nConcept = []\ninbox = ["_inbox/*"]\n'):
    Path(root, "okf.toml").write_text(toml)
    try:
        okf.load_config(root)
    except SystemExit as e:
        assert "inbox" in str(e), e
    else:
        raise AssertionError(f"{toml!r} must fail with a clear message")

# Third review: each hand-written w/index.md -> its text outside the markers after --adopt. Only a bullet
# with nothing attached goes. Code (inline, fenced, indented, unclosed) stays. A heading over a subsection stays.
A = "* [A](a.md)\n"
cases = {
    "# W\n\n" + A + "* Write `[A](a.md)` to link.\n* Or `[[a]]`.\n": "# W\n\n* Write `[A](a.md)` to link.\n* Or `[[a]]`.\n",
    "# W\n\n" + A + "\n~~~md\n```\n" + A + "```\n~~~\n": "# W\n\n\n~~~md\n```\n" + A + "```\n~~~\n",
    "# W\n\n" + A + "* Example:\n  ```md\n  " + A + "  ```\n": "# W\n\n* Example:\n  ```md\n  " + A + "  ```\n",
    "# Home\n\n" + A + "\n## Elsewhere\n\n* [S](https://e.x)\n": "# Home\n\n\n## Elsewhere\n\n* [S](https://e.x)\n",
    "# W\n\n" + A + "\n  A paragraph about A.\n": "# W\n\n" + A + "\n  A paragraph about A.\n",
    "# W\n\n* [A](a.md) - a long line\nwrapped with no indent.\n": "# W\n\n* [A](a.md) - a long line\nwrapped with no indent.\n",
    "# W\n\n* Group\n    " + A + "\t\t* child of A\n": "# W\n\n* Group\n    " + A + "\t\t* child of A\n",
    "# W\n\n* [[projects]] - a note elsewhere\n" + A: "# W\n\n* [[projects]] - a note elsewhere\n",
    "# W\n\n```\n" + A: "# W\n\n```\n" + A,
}
for hand, want in cases.items():
    root = bundle({"w/index.md": hand, "w/a.md": note, "w/projects/p.md": note, "notes/projects.md": note})
    run("--adopt")
    got = read("w/index.md").split("<!-- okf:index:start -->")[0]
    assert got.rstrip("\n") == want.rstrip("\n"), (hand, got)
    assert run("--check")[0] == 0
root = bundle({"index.md": "# Home\n\n* [A](/a.md)\n", "a.md": note})  # a /link at the root once hung index
assert run()[1].endswith("skipped 1 hand-written (use --adopt)\n") and run("--adopt")[0] == 0
root = bundle({"index.md": "# W\n\n* [A](a.md) - wraps\n  onto two lines\n", "a.md": note})
assert run()[1].endswith("skipped 1 hand-written (use --adopt)\n"), "a kept bullet still marks the file hand-written"
print("ok")
