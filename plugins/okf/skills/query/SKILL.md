---
name: query
description: |
  Answer a question from the OKF knowledge base and optionally file the answer back as a reusable wiki concept. Use when the user asks what the collected docs say, wants to look something up across a topic, or asks to synthesize or compare from a topic, e.g. "what do the tauri docs say about IPC", "find something in my knowledge base", "compare two approaches from the premiere-pro docs", "summarize the objc2 NSWindow API". This is the on-demand, token-spending counterpart to the light-by-default okf:topic.
allowed-tools:
  - Bash
  - Read
  - Write
  - Edit
---

# okf:query — answer from the knowledge base

Answer from the compiled topic, citing the exact source pages — and, when the
answer is worth keeping, file it back as a concept so the wiki compounds instead of
vanishing into chat history. This is the OKF **Query** operation.

## Critical context

- **KB root:** `KB="${OKF_KB_ROOT:-$HOME/code/knowledge-base}"`. If missing, ask.
- **Read narrowly.** A topic can be hundreds of pages — do NOT load `raw/` wholesale.
  Use the indexes and grep to find the few pages that matter, then read those.
- **Cite, don't fabricate.** Every claim traces to a `raw/` page you actually read.
  No source for a claim → say so; never invent a citation.
- Filing back is **optional and asked-for** — it spends tokens and writes to the wiki.

## Workflow

### Step 1 — Pick the topic
```bash
KB="${OKF_KB_ROOT:-$HOME/code/knowledge-base}"
ls "$KB/topics"        # if the user didn't name one, infer or ask
```

### Step 2 — Locate candidate pages (progressive disclosure)
1. Read `topics/<slug>/wiki/index.md` (the catalog) and any existing
   `wiki/concepts/` pages — a prior query may already answer this. (A light-by-default
   topic usually has no concept pages yet; that's expected — proceed to the raw docs.)
2. Skim the per-site `raw/<site>/CONTENTS.md` to spot relevant sections.
3. Narrow with grep over the raw frontmatter/body:
```bash
grep -ril "<keyword>" "$KB/topics/<slug>/raw" | head -20
grep -rl 'tags:.*<tag>' "$KB/topics/<slug>/raw"
```

### Step 3 — Drill in
Read only the specific pages that matter. Follow links between them. Stop when you
have enough to answer — not when you've read everything.

### Step 4 — Synthesize
Answer in whatever form fits (prose, table, code). Favor structure. End with a
`# Citations`-style list of the exact pages used, as repo-relative paths, e.g.
`topics/tauri/raw/tauri-v2/develop/calling-rust.md`.

### Step 5 — File back (only if the user wants it)
If the answer is reusable (a comparison, an analysis, a discovered connection),
write it as an OKF-conformant concept:
- Path: `topics/<slug>/wiki/concepts/<kebab-title>.md`.
- Frontmatter: `type:` is REQUIRED (e.g. `Comparison`, `Analysis`, `Topic`,
  `Reference`); add `title`, `description` (one sentence), `tags`, `timestamp`.
  **Quote any value containing `: ` or `#`** so YAML parses (okf-pack rulebook §3).
- Body: structured Markdown; cite the raw pages under a `# Citations` heading. Get the
  relative path right: a concept at `wiki/concepts/<name>.md` reaches `raw/` via
  **`../../raw/<site>/<page>.md`** (up out of `concepts/`, then out of `wiki/`). Link
  other wiki concepts bundle-relatively (`/concepts/...`). Verify each citation resolves
  before finishing.
- Add a bullet for it under `# Concepts` in `topics/<slug>/wiki/index.md`.
- Append a `**Query**` entry to `wiki/log.md` (today's date) noting what was asked
  and what was filed.

The concept template and format rules live in `$KB/okf-pack/okf-rulebook.md` (§11
template, §3 frontmatter, §5 links, §8 citations). For the authoring judgment —
choosing `type`, a pre-file self-check, and gap/conflict notes — see
`$KB/okf-pack/concept-authoring.md`. Consult both before writing.

## Example

User: "What do the tauri docs say about IPC between Rust and the frontend?"
1. topic `tauri`; read `wiki/index.md`.
2. `grep -ril "ipc\|invoke\|command" topics/tauri/raw/tauri-v2` → a few develop/ pages.
3. Read `develop/calling-rust.md`, `develop/calling-frontend.md`.
4. Answer with a table of the patterns + citations to those two pages.
5. User says "save that" → write `wiki/concepts/tauri-ipc-overview.md` (`type: Topic`),
   index it, log a `**Query**` entry.

## Troubleshooting

- **Nothing matches** — broaden keywords; check the topic is scraped (okf:refresh) or
  that you're in the right topic. The fact may simply not be in the collected docs —
  say so rather than guessing.
- **Answer spans topics** — query each relevant topic and synthesize; cite per topic.
- **YAML won't parse after filing** — an unquoted `: ` or `#` in `title`/`description`
  is the usual cause; wrap the value in double quotes.
