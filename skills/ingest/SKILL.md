---
name: ingest
description: >-
  Turn raw input into typed, linked notes in an existing OKF knowledge base. Saves a
  file, pasted text, a URL, or a folder unchanged in the inbox, then creates or updates
  notes for the source and for the people, orgs, projects, and ideas in it. Each note
  gets a type, title, description, and dates, and links back to the raw file. Runs
  okf.py index and check until no new hard failures remain, then logs the ingest. Use
  when the user says "ingest this", "add this transcript or doc to my knowledge base",
  "file these notes", or "process my inbox", or gives a meeting transcript, article,
  export, or notes file to file away. Works in any agent that can run shell commands.
license: MIT
compatibility: Requires uv. The CLI gets Python 3.11+ and PyYAML through uv.
---

# ingest: turn raw input into OKF notes

This skill files one raw input into a knowledge base. It saves the input unchanged in
the inbox, then writes or updates typed notes that link back to it. The `okf.py` CLI
checks the result.

The format rules live in these okf-pack docs, relative to the okf folder, `$OKF` below.
Read them before you write a note. Do not guess:

- `okf-pack/okf-rulebook.md`: frontmatter (section 3), links (section 5), citations
  (section 6), and `log.md` (section 9)
- `okf-pack/concept-authoring.md`: how to choose `type`, and how to record gaps and
  conflicts
- `okf-pack/okf-space.md`: the layout of an OKF space (section 1)

## Find the CLI and the root

```bash
OKF="${CLAUDE_PLUGIN_ROOT}"
[ -f "$OKF/scripts/okf.py" ] || OKF="${OKF_HOME:-$HOME/code/okf}"
uv run "$OKF/scripts/okf.py" --help
```

In Claude Code, the plugin writes its folder in place of `${CLAUDE_PLUGIN_ROOT}` when it
loads this skill. In other agents, `OKF_HOME` names your okf clone, `~/code/okf` by
default. Shell variables can be lost between commands, so set `OKF` and `KB` in the same
command that runs okf.py.

The knowledge base root, `KB` below, is the path the user gives, else the current
folder. If the current folder has no `okf.toml` and a parent folder has one, use that
parent.

Before you start, run `uv run "$OKF/scripts/okf.py" check "$KB" | tail -1`. The last
line shows the hard-failure count, and this ingest must not raise it.

## Ingest one input

### 1. Save the raw input

Find the inbox folder. Read `inbox` in `$KB/okf.toml` and take the folder part of its
first glob, for example `_inbox` for `_inbox/*`. If there is no `inbox` key, or the
folder part holds a `*`, use `raw`. With no `inbox` key, check does not report
unprocessed files. Offer to add `inbox = ["raw/*"]` to `okf.toml`.

Put the input in one file:

- A file: use it as it is. Keep its extension.
- Pasted text: write it to a temporary file exactly as given. Use `.md`.
- A URL: fetch the page as Markdown with any tool you have, such as a web fetch tool or
  `curl`. Save what the tool returns. Use `.md`. For a whole doc site, use the topic
  skill instead.
- A folder: ingest each file in it in turn.

Name the file `YYYY-MM-DD-<slug>.<ext>`, with today's date and a short kebab-case slug.
Then save it, unless the inbox already holds the same content:

```bash
INBOX="$KB/raw"           # the inbox folder from above
IN="/path/to/input"       # the input file
mkdir -p "$INBOX"
OUT="$INBOX/$(date +%F)-<slug>.<ext>"
HASH=$(shasum -a 256 "$IN" | cut -d' ' -f1)
find "$INBOX" -type f -exec shasum -a 256 {} + | grep "^$HASH " \
  || { [ -e "$OUT" ] && echo "name taken: $OUT" || cp "$IN" "$OUT"; }
```

- If grep prints a line, that file already holds this content. Stop and tell the user
  its path. If `shasum` is missing, use `sha256sum`.
- If it prints `name taken`, a different file already has the name. Add `-2` to the
  slug and run it again. The command never replaces a raw file.
- Never edit the raw file after you save it.

### 2. Search before you create

Read the raw file. List the subjects it names: people, orgs, projects, and ideas. Search
for each subject before you write:

```bash
grep -rEil '^(title|aliases):.*<name>' "$KB" --include='*.md'   # title or alias
grep -ril "<name>" "$KB" --include='*.md' | head -20             # any mention
grep -i "<name>" "$KB/catalog.jsonl"                             # if the file exists
```

- If a note covers the subject, update that note. Create a note only when none does.
  Give each person, org, and project its own note. If the input adds nothing new about
  a subject, leave its note as it is.
- Create one `Source` note for the input, with a summary and the points worth finding
  later, such as decisions, actions, claims, and numbers. Give it a filename that
  differs from the raw file. Check matches links by filename, so a shared name hides an
  unlinked raw file.
- If the input contradicts a note, do not overwrite the note. Record the conflict on
  both notes, as `concept-authoring.md` shows.
- Put notes where the knowledge base's `AGENTS.md` or `README.md` says. Else put each
  note next to notes of the same type. In an OKF space, use `wiki/sources/`,
  `wiki/entities/`, and `wiki/concepts/`.

### 3. Write the notes

Each note you create or update gets this frontmatter:

- `type`: if `okf.toml` has a `[types]` table, use one of its keys. Newer okf releases
  warn `unknown-type` for any other value. Else prefer a type that the knowledge base
  already uses (`uv run "$OKF/scripts/okf.py" types "$KB"` lists them, most used first),
  or a broad honest type from `concept-authoring.md`.
- `title`: the display name.
- `description`: one standalone sentence of 25 words or fewer. Name the subject. Do not
  start with "It" or "This".
- `created` and `updated`: ISO dates. A new note gets today's date for both. On an
  existing note, set `updated` to today and keep `created`. If `created` is missing,
  get it from git with `git log --diff-filter=A --format=%as -- <file> | tail -1`, or
  leave it out. Never guess a date.

Rules for the body:

- Link each note to the raw file under `# Citations`. Use a path relative to the note,
  such as `[1] [Atlas sync transcript](../raw/2026-10-06-atlas-weekly-sync.md)`. This
  link clears `unprocessed`.
- Link related notes in the prose, as rulebook section 5 shows.
- Write only what the raw file says. If a fact is missing, add a gap note, as
  `concept-authoring.md` shows. Never invent a fact, a date, or a name.
- Quote any YAML value that contains `: ` or ` #`, for example
  `title: "Atlas sync: launch moves to November 3"`.

### 4. Index and check

```bash
uv run "$OKF/scripts/okf.py" index "$KB"    # add --catalog if catalog.jsonl exists
uv run "$OKF/scripts/okf.py" check "$KB"
```

- Fix each new hard failure. The okf skill lists the fix for each code. A `dead-link`
  warning on a note you wrote means a bad path. Fix the path.
- Newer okf releases skip a hand-written `index.md` and say so in the summary line. If
  index reports a skipped file, add a bullet for each new note to that file by hand.

### 5. Log the ingest

Add one entry to the knowledge base's `log.md` (in an OKF space, `wiki/log.md`). If
there is no `log.md`, create one with a `# Update Log` heading. Put the entry under
today's `## YYYY-MM-DD` heading, and add that heading above the newest date if it is
missing. Start the entry with `**Ingest**`, then link the raw file and each note you
created or updated.

### Done when

Run check again after the log edit. Stop when check shows no more hard failures than at
the start, and `uv run "$OKF/scripts/okf.py" check "$KB" --all | grep ': unprocessed:'`
no longer lists the raw file. Then tell the user the raw file path, the notes you
created and updated, and each gap or conflict you recorded.

## Process the inbox

Use this mode when the user asks you to process the inbox.

1. List the files that wait for ingest:
   ```bash
   uv run "$OKF/scripts/okf.py" check "$KB" --all | grep ': unprocessed:'
   ```
2. Ingest each file in turn, oldest name first. Skip step 1: the file is already in the
   inbox. Do not rename it.
3. Run index and check after each file, so that one bad note does not hide in a batch.

Check lists only `.md` files. For each other file in the inbox, search for its name with
`grep -rlF "<filename>" "$KB" --include='*.md'`. If no note names it, ingest it too.
Skip dotfiles such as `raw/assets/.gitkeep`.

## Example

The user pastes a meeting transcript and says "ingest this". The knowledge base has an
`okf.toml` with `inbox = ["raw/*"]` and two notes, `entities/atlas.md` and
`entities/lena-ortiz.md`.

Input:

```text
Atlas weekly sync, 2026-10-05
Attendees: Lena Ortiz, Ravi Patel
Lena: The billing test failed on invoices with mixed currencies.
Ravi: I can fix the currency rounding by October 9.
Lena: Then the launch moves from October 20 to November 3.
```

Notes:

- Saved `raw/2026-10-06-atlas-weekly-sync.md`, unchanged.
- Created `sources/atlas-sync-2026-10-05.md` (`Source`) with the decision and action.
- Created `entities/ravi-patel.md` (`Entity`), because search found no note for him.
- Updated `entities/atlas.md` with a timeline line for the new launch date, a citation,
  and `updated: 2026-10-06`.
- Left `entities/lena-ortiz.md` as it is. The transcript adds no new fact about her.
- Added an `**Ingest**` entry under `## 2026-10-06` in `log.md`.

The `Source` note starts with this frontmatter:

```yaml
---
type: Source
title: "Atlas sync: launch moves to November 3"
description: Atlas weekly sync of 2026-10-05, where a failed billing test moved the launch to November 3.
created: 2026-10-06
updated: 2026-10-06
---
```

Commands and result:

```console
$ uv run "$OKF/scripts/okf.py" check "$KB"      # after the save, before the notes
okf check /kb: 2 notes, 1 sources, 0 meta, 2 index.md, 1 log.md
WARN: unprocessed 1
  raw/2026-10-06-atlas-weekly-sync.md: unprocessed: no note links to it
conformant
$ uv run "$OKF/scripts/okf.py" index "$KB"
okf index /kb: wrote 3, unchanged 0
$ uv run "$OKF/scripts/okf.py" check "$KB"
okf check /kb: 4 notes, 1 sources, 0 meta, 3 index.md, 1 log.md
conformant
```

The hard-failure count stayed at 0, and check no longer lists the transcript as
unprocessed.
