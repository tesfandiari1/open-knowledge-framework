---
name: okf
description: >-
  Answer what the user's notes, docs, or knowledge base say about a topic, such as
  "what do my notes or docs say about X", with cited files. Also check, lint, or index an
  OKF knowledge base (Markdown with YAML frontmatter): fix frontmatter failures, refresh
  index.md files, count note types, or set up the okf pre-commit guard.
license: MIT
compatibility: Requires uv. The CLI gets Python 3.11+ and PyYAML through uv.
---

# okf: check, index, and query a knowledge base

This skill keeps a folder of Markdown notes conformant with the Open Knowledge Format
(OKF) and answers questions from it. The `okf.py` CLI runs the checks and writes the
indexes. You fix what it reports, and you answer with citations.

To add new material (a file, pasted text, a URL, or a folder), use the ingest skill
(`skills/ingest`, `okf:ingest` in Claude Code). It saves the raw input and writes the
notes that link to it.

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
2. Else use the current folder, if it holds the notes the user means. If it has no
   `okf.toml` and a parent folder has one, use that parent. An `okf.toml` file marks a
   configured root.
3. Else use `$OKF_KB_ROOT`, if it is set.
4. Else use `~/code/knowledge-base`, if it has `okf.toml`. okf:topic writes there.

In an OKF space made by `new_space.sh`, the root is the space folder. Its `okf.toml`
marks the rulebook docs as meta and `raw/` as the inbox.

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
7. If the knowledge base has a `log.md` (`wiki/log.md` in an OKF space), add a
   `**Lint**` entry that lists what you fixed. Put it first under today's
   `## YYYY-MM-DD` heading. Keep the newest date at the top.

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
  the knowledge base already uses. `okf.py types` lists them (see Types).
- `index-frontmatter`: an `index.md` may carry only `okf_version`. Remove the other keys.
  Keep `okf_version`, because it marks a bundle root, and `/links` resolve from there. If
  no key is left, remove the `---` lines too.
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
- `unknown-type`: the note's `type` is not a key of the `[types]` table in `okf.toml`.
  If the detail says `alias of X`, change the type to `X`. Else, choose an approved type
  that fits, or ask the user to add the type to `[types]`.
- `index-size`: an `index.md` is more than 8 KB. Index shrinks its own block to fit (see
  Index), so the cause is text outside the markers, a hand-written index that index
  skips, or a long list of subfolders. Report it. Suggest a shorter intro or fewer
  subfolders.
- `context-budget`: the agent instructions that load on every turn are more than 16 KB.
  Report the largest files from the detail. Suggest `paths:` scopes for `.claude/rules`
  files or fewer `@imports`. Do not cut instructions without the user.
- `unprocessed`: no note links to this inbox file yet. This is work to do, not an
  error. Offer to ingest it with the ingest skill.
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
- Without `--adopt`, text outside the markers stays as it is. Put a hand-written intro there. The root
  `okf_version` frontmatter also stays.
- An `index.md` with no markers that already lists notes or subfolders of its folder is
  hand-written. Index
  leaves it as it is, and the summary line says `skipped N hand-written (use --adopt)`.
  An `index.md` with only prose gets the block added below the prose.
- Index never writes in a `sources` or `inbox` folder.
- `--catalog` writes one JSON line per note with `path`, `type`, `title`, `description`,
  and `updated`. The `updated` value comes from `updated`, else `timestamp`, else
  `generated.at`, and is empty when the note has none. Use it to search a large
  knowledge base. Add `--catalog` to `--check` to check this file too.
- Index keeps each `index.md` at 8 KB or less when it can. In a large folder it drops
  the descriptions. If that is not enough, it lists each type as one line, such as
  `* 1000 notes. Search catalog.jsonl (okf index --catalog) or grep.` When you see that
  line, grep `catalog.jsonl` (run index with `--catalog` if the file is missing) or grep
  the folder. Do not open the notes one by one.
- A second run changes nothing. `--check` suits CI and the time before a commit.

### Adopt a hand-written index

`--adopt` takes over each hand-written `index.md`. It removes each bullet whose links
all point to entries of that folder's own block (its notes and subfolders), unless text
hangs off the bullet (a wrapped line, an indented paragraph, or child bullets). It
removes the headings left empty, and keeps all other text, links, and code. Then it adds the block. Later runs update the block
only.

Ask the user before you adopt. A removed bullet takes its hand-written text with it,
such as a description.

1. List the files that `--adopt` would change. Show the list to the user:
   ```bash
   uv run "$OKF/scripts/okf.py" index "$KB" --check --adopt
   ```
2. If the knowledge base is a git repo, ask the user to commit first, so `git diff`
   shows each removed line and `git restore` can undo the change.
3. When the user agrees, run `uv run "$OKF/scripts/okf.py" index "$KB" --adopt`.
4. Show the user the removed lines that held more than a link. Put back the text the
   user wants to keep, outside the markers.

## Query

Answer from the notes and cite the files you read. Read narrowly. A knowledge base can
hold thousands of files, so do not load sources wholesale.

1. Read the root `index.md`. Go down through the folder `index.md` files toward the
   subject. If there is no root `index.md`, or an index lists a type only as a note
   count, go to step 2.
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
   the files you used. Write each one as its full path from the root, for example
   `guides/deploy/rollback.md`. Do not shorten paths under a shared prefix.

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
   path. Fix it. Check does not test links that go above the root, such as a link
   into `raw/` when you check only `wiki/`. Make sure those files exist.
6. If the folder has a `log.md`, add a `**Query**` entry under today's `## YYYY-MM-DD`
   heading. Keep the newest date first.

## Guard commits

The pre-commit hook blocks a commit only when hard failures rise above the stored count.
Old failures do not block. The hook stores the hard-failure count in `.okf-baseline`,
and that count only goes down. The hook checks the whole working tree, so a bad file
that is not staged can also block a commit.

The hook needs an okf clone. Install it from the root of the knowledge base repo:

1. Make sure the clone has the hook:
   ```bash
   test -e "${OKF_HOME:-$HOME/code/okf}/hooks/pre-commit" && echo found
   ```
   If it is not found, do not create the link. Tell the user to clone okf to
   `~/code/okf`, or to set `OKF_HOME` to their clone.
2. If `.git/hooks/pre-commit` exists, do not replace it. Show it to the user and ask.
3. Link the hook, then make sure the link works:
   ```bash
   ln -s "${OKF_HOME:-$HOME/code/okf}/hooks/pre-commit" .git/hooks/pre-commit
   test -e .git/hooks/pre-commit && echo linked
   ```

- Never link into the plugin cache. Its path changes on every plugin update. Git skips
  a dangling hook and shows no message, so the guard stops with no warning.
- The hook finds the CLI through `OKF_HOME` (default `~/code/okf`). If the okf clone is
  somewhere else, the user must export `OKF_HOME` in the shell profile. If the hook
  cannot find `okf.py`, it blocks the commit with
  `okf pre-commit: okf.py not found in <folder>`.
- Commit `.okf-baseline`. The hook stages it each time it writes a new count.
- When the hook blocks a commit, it lists the hard failures in changed files (staged,
  unstaged, and untracked). If none of them has one, it lists the first 20 in the repo.
  Fix the files it names.
- To skip the hook once, use `git commit --no-verify`.

The same ratchet works without the hook, for example in CI:

```bash
uv run "$OKF/scripts/okf.py" check "$KB" --baseline "$KB/.okf-baseline"
```

The first run stores the count. Later runs exit 1 only if hard failures rose above the
stored count, and they store the lower count when failures fall.

## Types

The types command counts the notes of each `type`, most used first. Use it to choose a
type for a new note, and to propose a `[types]` table (see Config).

```bash
uv run "$OKF/scripts/okf.py" types "$KB"
```

Each line shows a count and a type. When `okf.toml` has a `[types]` table, each line
also says `approved`, `alias of X`, or `unknown`. The last line says what share of the
typed notes the top 20 types cover. Ask the user before you add or change `[types]`,
because check then warns `unknown-type` for every note outside it.

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
- `[types]`: the approved note types. Each key is a type, and its list holds aliases,
  for example `Playbook = ["play", "runbook"]`. Another case of a key counts as an alias
  of it, because index lists each exact value under its own heading. With this table,
  check warns `unknown-type` for any other type. It is never a hard failure. An empty
  table flags every typed note. Put the table last in the file, because TOML puts every
  key after `[types]` inside the table.

Globs use fnmatch on paths relative to the root, and `*` also matches across folders. A
key you set replaces its default. If you set `sources`, keep `raw/*` and `*/raw/*` in
the list when you still need them. Dot-folders such as `.git` and `.obsidian` are
always skipped.
