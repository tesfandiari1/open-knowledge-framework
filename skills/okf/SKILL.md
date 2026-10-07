---
name: okf
description: >-
  Check, index, and query any OKF knowledge base, that is, a folder of Markdown notes
  with YAML frontmatter. Use when the user wants to check, lint, or validate a knowledge
  base or notes folder, fix frontmatter or conformance failures, build or refresh index.md
  files, find or look up something in the notes, answer a question from the knowledge
  base with citations, or set up the okf pre-commit guard. Runs the okf.py CLI (check,
  index) and follows the okf-pack format rules. Works in any agent that can run shell
  commands.
license: MIT
compatibility: Requires uv. The CLI gets Python 3.11+ and PyYAML through uv.
---

# okf: check, index, and query a knowledge base

This skill keeps a folder of Markdown notes conformant with the Open Knowledge Format
(OKF) and answers questions from it. The `okf.py` CLI runs the checks and writes the
indexes. You fix what it reports, and you answer with citations.

The format rules live in the okf-pack docs. Read them when you need a rule. Do not guess:

- `okf-pack/okf-rulebook.md`: frontmatter, links, citations, `index.md`, `log.md`, and
  conformance (section 7)
- `okf-pack/concept-authoring.md`: how to choose `type` and write one good note
- `okf-pack/okf-space.md`: the space layout and the Ingest, Query, and Lint operations

These paths are relative to the okf folder, `$OKF` below.

## Find the CLI

```bash
OKF="${CLAUDE_PLUGIN_ROOT}"
[ -f "$OKF/scripts/okf.py" ] || OKF="${OKF_HOME:-$HOME/code/okf}"
uv run "$OKF/scripts/okf.py" --help
```

- In Claude Code, the plugin writes its folder in place of `${CLAUDE_PLUGIN_ROOT}` when
  it loads this skill. The shell does not have that variable.
- In other agents, `OKF_HOME` names your okf clone. The default is
  `~/code/okf`.
- Shell variables can be lost between commands. Set `OKF` and `KB` in the same command
  that runs okf.py.
- The CLI needs uv (https://docs.astral.sh/uv/). uv reads the script header and gets
  Python and PyYAML. If `uv` is missing, tell the user how to install it.

## Find the knowledge base root

1. Use the path the user gives.
2. If the user gives no path, use the current folder.
3. If the current folder has no `okf.toml` and a parent folder has one, use that parent.
   An `okf.toml` file marks a configured root.

In an OKF space made by `new_space.sh`, the root is the `wiki/` folder. The space folder
also holds `AGENTS.md`, the rulebook, and `raw/`, which are not notes.

The CLI also works without `okf.toml`. The commands below use `KB` for the root.

## Check

```bash
uv run "$OKF/scripts/okf.py" check "$KB"          # first 20 findings per code
uv run "$OKF/scripts/okf.py" check "$KB" --all    # every finding
```

The output is a count line, then `HARD:` and `WARN:` totals, then one line per finding:
`path: code: detail`. The last line is `conformant` or `not conformant: N hard failures`.
The command exits 1 when any hard failure exists.

- **HARD** findings break OKF conformance (rulebook section 7). A knowledge base with
  hard failures is not conformant. Fix every one.
- **WARN** findings are signals, not failures (rulebook section 2). Fix the mechanical
  ones. Report the rest to the user.

### Fix in this order

1. Fix the config first. If many findings sit in files that are not notes (scraped docs,
   exports, templates, transcripts), add a glob to `okf.toml` (see Config). One line can
   clear hundreds of findings. Tell the user which globs you added.
2. Fix parse failures: `bad-frontmatter`, then `no-frontmatter`.
3. Fix `no-type`.
4. Fix the reserved files: `index-frontmatter`, `log-heading`, `log-order`.
5. Run check again. Repeat until no hard failures remain.
6. Fix the mechanical warnings. Report the warnings that need judgment.

Make the smallest edit that clears each finding. Change frontmatter and headings, not
the note body. Run check after each batch of fixes.

Rules for every fix:

- Never edit a file that matches a `sources` or `inbox` glob. Sources are immutable.
- Never delete a link because its target is missing.
- Quote any YAML value that contains `: ` or ` #`, for example
  `title: "Auth: tokens and sessions"`. An unquoted `: ` breaks the parse. An unquoted
  ` #` silently cuts the value short.
- Never invent a `type`, a description, or a fact that the note does not support.

### Hard failures

- `bad-frontmatter`: the block between the `---` lines does not parse as a YAML mapping,
  or the closing `---` is missing. The usual cause is an unquoted value that contains
  `: `. Put the value in double quotes and escape any `"` inside it. Also look for
  an unclosed quote, a tab used as indentation, or a body that starts with a `---` rule
  and has no frontmatter above it.
- `no-frontmatter`: the file does not start with `---`. Add a block at the top with
  `type` and `description`. If the file is not a note, change `okf.toml` instead.
- `no-type`: add `type: <Type>`. Choose it per `concept-authoring.md`. Prefer a type that
  the knowledge base already uses: `grep -rh '^type:' "$KB" --include='*.md' | sort | uniq -c`.
- `index-frontmatter`: an `index.md` may carry only `okf_version`, and only at the root.
  Remove the other keys. If no key is left, remove the `---` lines too.
- `log-heading`: each `## ` heading in a `log.md` must start with an ISO date, for
  example `## 2026-05-22`. Convert other date formats. Change a heading that is not a
  date to `###` under its date. If the file is not an OKF log, add it to `exclude`.
- `log-order`: the date sections must run newest first. Move whole sections. Do not
  change their text.

### Warnings

- `no-description`: add a one-sentence `description` that names the subject. Write it
  from the note's own text. Indexes and search copy this field.
- `dead-link`, `missing-asset`: a missing target can be a note that nobody has written
  yet (rulebook section 2). If the target moved or the link has a typo, and you can find
  the real file, fix the link path. Else, keep the link and list it in your report.
- `dead-route`: a path in backticks in `AGENTS.md` or `CLAUDE.md` does not exist. Agents
  follow these routes. If the file moved, update the path. Else, report it.
- `duplicate-name`: two notes share a filename, so `[[wikilinks]]` to that name are
  ambiguous. Report it. Rename a file only when the user agrees, because a rename
  breaks links.
- `index-size`: an `index.md` is more than 4 KB. Index writes one list per folder and
  does not split it. If the folder is hard to navigate, suggest subfolders.
- `context-budget`: the agent instructions that load on every turn are more than 16 KB.
  Report the largest files from the detail. Suggest `paths:` scopes for `.claude/rules`
  files or fewer `@imports`. Do not cut instructions without the user.
- `unprocessed`: no note links to this inbox file yet. This is work to do, not an
  error. Offer to ingest it per `okf-space.md` section 4.1.
- `unreadable`: a broken symlink or a permission error. Report it.

## Index

The index command writes an `index.md` in each folder that holds notes. Each index
lists its subfolders and its notes, grouped by `type`, with each note's description.
Agents and people read these files to find a note without opening every file.

```bash
uv run "$OKF/scripts/okf.py" index "$KB"            # write or update each index.md
uv run "$OKF/scripts/okf.py" index "$KB" --check    # write nothing, exit 1 if an index is stale
uv run "$OKF/scripts/okf.py" index "$KB" --catalog  # also write catalog.jsonl at the root
```

- Run index after you add, move, rename, or delete a note, and after you change a
  `title`, `type`, or `description`.
- The generated list sits between `<!-- okf:index:start -->` and
  `<!-- okf:index:end -->`. Never edit inside the markers. To change an entry, edit the
  note's frontmatter and run index again.
- Text outside the markers stays as it is. Put a hand-written intro there. The root
  `okf_version` frontmatter also stays.
- If an `index.md` already has a hand-written list, index adds its block below that
  list, so each entry shows twice. Ask the user before you remove the old list.
- Index never writes in a `sources` or `inbox` folder.
- `--catalog` writes one JSON line per note with `path`, `type`, `title`, `description`,
  and `updated` when the note has it. Use it to search a large knowledge base. Add
  `--catalog` to `--check` to check this file too.
- A second run changes nothing. `--check` suits CI and the time before a commit.

## Query

Answer from the notes and cite the files you read. Read narrowly. A knowledge base can
hold thousands of files, so do not load sources wholesale.

1. Read the root `index.md`. Go down through the folder `index.md` files toward the
   subject. If there is no root `index.md`, go to step 2.
2. Search with your search tool or grep:
   ```bash
   grep -i "<keyword>" "$KB/catalog.jsonl"                  # if catalog.jsonl exists
   grep -ril "<keyword>" "$KB" --include='*.md' | head -20
   grep -rl '^type: <Type>' "$KB" --include='*.md'
   ```
3. Look at existing notes first. A note filed by an earlier query can already hold the
   answer.
4. Read only the files that matter. Follow their links. Stop when you can answer.
5. Answer in the form that fits: prose, a table, or code. End with a list of citations:
   the files you used, as paths relative to the root, for example
   `guides/deploy/rollback.md`.

- Every claim traces to a file you read. If no file supports a claim, say so. Never
  invent a citation.
- If nothing matches, try other keywords. The fact may not be in the knowledge base.
  Say so rather than guess.
- If the answer spans several folders or topics, search each one and cite each one.

### File the answer back

If the answer is reusable (a comparison, an analysis, a link between notes), offer to
save it as a note. Write it only when the user agrees.

1. Follow `okf-pack/concept-authoring.md` for `type` and the self-check. Use the template
   in rulebook section 11.
2. Put the note where the knowledge base's `AGENTS.md` says. In an OKF space, that is
   `wiki/concepts/`.
3. Give it `type`, `title`, and a one-sentence `description`. Quote any value that
   contains `: ` or ` #`.
4. Cite sources under a `# Citations` heading. Write each link relative to the new note's
   folder. From `wiki/concepts/x.md`, a source is `../../raw/<site>/<page>.md`.
5. Run index, then check. A `dead-link` warning on the new note means a bad citation
   path. Fix it. Check does not test links that go above the root, such as
   `../../raw/` from `wiki/`. Make sure those files exist.
6. If the folder has a `log.md`, add a `**Query**` entry under today's `## YYYY-MM-DD`
   heading. Keep the newest date first.

## Guard commits

The pre-commit hook blocks a commit only when hard failures rise above the stored count.
Old failures do not block. The hook stores the hard-failure count in `.okf-baseline`,
and that count only goes down. The hook checks the whole working tree, so a bad file
that is not staged can also block a commit.

Install it from the root of the knowledge base repo:

```bash
ln -s "${OKF_HOME:-$HOME/code/okf}/hooks/pre-commit" .git/hooks/pre-commit
```

- If `.git/hooks/pre-commit` exists, do not replace it. Show it to the user and ask.
- Link to a stable okf clone, not to a plugin cache folder. A plugin cache path
  contains the version, so the link breaks on update.
- The hook finds the CLI through `OKF_HOME` (default `~/code/okf`). If the okf clone is
  somewhere else, the user must export `OKF_HOME` in the shell profile.
- Commit `.okf-baseline`. The hook stages it each time it writes a new count.
- To skip the hook once, use `git commit --no-verify`.

The same ratchet works without the hook, for example in CI:

```bash
uv run "$OKF/scripts/okf.py" check "$KB" --baseline "$KB/.okf-baseline"
```

The first run stores the count. Later runs exit 1 only if hard failures rose above the
stored count, and they store the lower count when failures fall.

## Config

An `okf.toml` file at the root tells check and index which files are not notes. Every
key is optional. Copy `$OKF/okf.toml.example` to start.

- `exclude`: files to skip. Links into them still resolve.
- `sources`: immutable source material, such as scraped docs. Default: `raw/*` and
  `*/raw/*`.
- `inbox`: material that waits for ingest, such as meeting transcripts. Check reports
  each inbox file that no note links to.
- `meta`: agent and repo files that need no OKF frontmatter. Their links are still
  checked. Default: `README.md`, `AGENTS.md`, and `CLAUDE.md` at any depth.

Globs use fnmatch on paths relative to the root, and `*` also matches across folders. A
key you set replaces its default. If you set `sources`, keep `raw/*` and `*/raw/*` in
the list when you still need them. Dot-folders such as `.git` and `.obsidian` are
always skipped.
