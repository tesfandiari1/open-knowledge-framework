# OKF Space — Setup & Operating Spec

> **What this is.** The one document that ties the whole pack together: how to
> **stand up an OKF space** from an empty folder and how to **operate** it over time.
> It is the *schema layer* of the LLM-maintained-wiki pattern — the config that
> turns an LLM from a generic chatbot into a disciplined wiki maintainer.
>
> **How to use it.** Save this file at the root of your space as `AGENTS.md`
> (Codex/OpenCode), `CLAUDE.md` (Claude Code), or paste it as a system prompt
> alongside `okf-rulebook.md` in any LLM environment. It is plain, portable
> Markdown — no YAML frontmatter, no SDK, no vendor lock-in.
>
> **Single source of truth (DRY).** This spec defers all *format* rules to
> `okf-rulebook.md` and all concept-writing *judgment* to `concept-authoring.md`. It
> owns only the **setup, the operating workflows, and your space-specific
> conventions**.

---

## 0. What an OKF space is

Most LLM-plus-documents setups are RAG: upload files, retrieve chunks at query
time, regenerate an answer from scratch every time. Nothing accumulates. An **OKF
space** is the opposite: the LLM **incrementally builds and maintains a persistent,
interlinked wiki** that sits between you and your raw sources. Knowledge is
**compiled once and kept current**, not re-derived per question. The cross-links are
already there; the contradictions are already flagged; the synthesis already
reflects everything you've read.

You curate sources and ask good questions. The LLM does the bookkeeping —
summarizing, cross-referencing, filing, consistency — the work that makes a
knowledge base useful and that humans abandon because it never ends. The LLM
doesn't get bored and can touch 15 files in one pass, so the wiki stays maintained.
(This is Vannevar Bush's *Memex* — a private, curated store with associative trails
— with the one part he couldn't solve, *who does the maintenance*, finally handled.)

### The three layers

| Layer        | Owner            | In an OKF space |
|--------------|------------------|-----------------|
| Raw sources  | **you** curate   | `raw/` — immutable source documents. The LLM reads them, never edits them. |
| **The wiki** | the **LLM** owns | `wiki/` — an **OKF bundle** (concepts + cross-links + `index.md` + `log.md`), per `okf-rulebook.md`. |
| The schema   | co-evolved       | **This file** + the rulebook + `concept-authoring.md`. The discipline that keeps the LLM rigorous. |

The `raw/` ↔ `wiki/` split *is* the immutability boundary: sources are ground
truth; the wiki is derived and regenerable.

---

## 1. Layout — what to create

```
okf-space/
├── AGENTS.md  (or CLAUDE.md)   # THIS spec — the schema layer, read every session
├── okf-rulebook.md            # OKF v0.1 format reference (from the pack)
├── concept-authoring.md       # on-demand concept-writing craft (from the pack)
├── raw/                       # immutable source documents — YOU add these
│   └── assets/                # optional: downloaded images/files
└── wiki/                      # the OKF bundle — the LLM owns this entirely
    ├── index.md               # root catalog (may carry okf_version: "0.1")
    ├── log.md                 # chronological history (newest first)
    ├── sources/               # each ingested source mirrored as a `Source` concept
    ├── entities/              # people, orgs, places, products …
    ├── concepts/              # ideas, terms, methods …
    └── topics/                # broader subject areas (create what fits your domain)
```

The directory structure is **domain-independent** (rulebook §1, spec §3) — the
subdirectories above are a sensible default, not a requirement. Pick groupings that
fit what you're capturing (a book wiki might use `characters/`, `themes/`,
`chapters/`; a research wiki might use `papers/`, `findings/`, `open-questions/`).
Record whatever you choose in §3 below.

---

## 2. Setup (0 → 1)

1. **Create the folders.** `raw/` and `wiki/` at minimum; drop in `okf-rulebook.md` +
   `concept-authoring.md` + this spec.
2. **Initialize git** (recommended). The wiki is just Markdown — git gives you
   history, diffs, branching, and collaboration for free. Commit after each ingest.
3. **Seed the wiki root.** Create `wiki/index.md` with the one permitted root
   frontmatter key and empty sections to be filled as concepts arrive:
   ```markdown
   ---
   okf_version: "0.1"
   ---
   # Sources
   # Entities
   # Concepts
   ```
4. **Record your conventions** in §3 of this file (subdirectory taxonomy, `type`
   vocabulary, tags, any extension frontmatter keys). This is the part you and the
   LLM co-evolve.
5. **Add your first source** to `raw/` and run **Ingest** (§4.1). From here on, the
   space grows one operation at a time.

---

## 3. Conventions (your space's schema — edit this section)

> Defer all format mechanics to `okf-rulebook.md`. Record only the choices specific
> to *this* space here, so every future session follows them.

- **Subdirectory taxonomy:** _e.g. `sources/`, `entities/`, `concepts/`, `topics/`._
  _(edit to match your domain)_
- **`type` vocabulary:** the concept types you actually use — _e.g. `Source`,
  `Entity`, `Concept`, `Topic`, `Comparison`, `Reference`._ Keep it small and
  honest; consumers tolerate unknown types (rulebook §3).
- **Tag conventions:** _e.g. lowercase, singular, drawn from a short controlled
  list you grow over time._
- **Extension frontmatter keys:** optional producer-defined keys for richer queries
  — _e.g. `source_count`, `status: draft|reviewed`, `aliases: [...]`._ These never
  affect conformance (rulebook §3) and power frontmatter-query views.
- **Filing rules / edge cases:** _record anything you've decided once and want kept
  consistent — disambiguation patterns, when to split vs. merge concepts, etc._

---

## 4. Operations

The space supports three operations — **Ingest**, **Query**, **Lint**. Each
is a Claude Code okf-plugin skill backed by the plugin's `scripts/`; the flows below describe what
each does (and work for any LLM following the rulebook).

### 4.1 Ingest — add sources (light by default)

Bring sources into the space as clean, frontmattered Markdown and catalog them — the
raw scrape is the product; the `wiki/` is a thin index over it. No per-page rewrite.

**Flow** (`okf:topic` for a new topic, `okf:refresh` for an existing one):
1. Declare each source in `raw/SOURCES.md`; scrape into `raw/` (resumable and
   idempotent — only new or changed URLs are pulled). Note the **ingest date**.
2. The scrape transforms each page to frontmattered Markdown and regenerates every
   site's mechanical `raw/<site>/CONTENTS.md`.
3. Refresh the light `wiki/index.md` so its `# Sources` section catalogs the sites,
   and append an `**Ingest**` entry to `wiki/log.md`.
4. **Report & commit.** Summarize the page-count delta; `git commit`.

**Do NOT** rewrite scraped pages into concept documents by default — a topic may be
hundreds of pages. Concept synthesis is on demand, one page at a time (§4.2).

### 4.2 Query — ask the wiki

Answer questions *from the compiled wiki*, and **feed good answers back in** so
explorations compound instead of vanishing into chat history.

**Flow:**
1. **Read `wiki/index.md` first** (progressive disclosure, rulebook §8) to locate
   relevant pages; at small scale this beats embeddings. Use a search tool if you've
   added one (§6).
2. **Drill into the linked concepts**, following cross-links to related pages.
3. **Synthesize an answer with citations** to the concepts (and their sources) you
   used. The answer can take whatever form fits — a prose reply, a comparison table,
   a generated page.
4. **File worthwhile answers back as new concepts.** A comparison you asked for, an
   analysis, a discovered connection — write it as a conformant concept under
   `wiki/concepts/` (per `concept-authoring.md` + rulebook §11), index it, and append
   a `**Query**` log entry noting what was asked and what was filed.

### 4.3 Lint — health-check the wiki

Periodically audit the wiki's health and surface work to do (the `okf:lint` skill).

**Look for:**
- **Contradictions** between pages (flag both; never silently overwrite).
- **Stale claims** superseded by newer sources (mark with a timestamped note).
- **Orphan pages** with no inbound links.
- **Missing pages** — concepts mentioned across the wiki that lack their own page.
- **Missing cross-references** between clearly related pages.
- **Conformance drift** — check `wiki/` against rulebook §7 (parseable frontmatter,
  non-empty `type`, well-formed reserved files).
- **Data gaps** — facts the wiki implies but can't support, which suggest a new
  source to curate or (if you enable it) a web search to propose.

**Output:** a lint report + a list of suggested new questions to investigate and
sources to find. Apply the mechanical fixes (links, index/log regeneration); leave
contradictions and gaps for you to adjudicate. Append a `**Lint**` log entry.

---

## 5. Indexing & logging

Two reserved files make the space navigable as it grows (rulebook §8, §9):

- **`index.md` — content-oriented.** A catalog of what exists, grouped by section,
  each entry linking a concept with its one-line `description`. Read first on every
  Query. Raw-source manifests are regenerated by the plugin's `scripts/gen_index.py` on every
  Ingest, so they always reflect current contents.
- **`log.md` — chronological.** Append-only, newest-first, `## YYYY-MM-DD` date
  headings. Each entry leads with a bold action word — `**Ingest**`, `**Query**`,
  `**Lint**`, `**Creation**`, `**Update**`, `**Deprecation**`. The consistent prefix
  keeps the log grep-able (`grep "Ingest" log.md`, `grep "^## " log.md | head`)
  while staying fully OKF-conformant — no custom format needed.

---

## 6. Optional tooling (modular — add only what you need)

Everything here is optional. Start with nothing but Markdown and add as the space
grows.

- **Search.** At small scale (~100 sources, hundreds of pages) `index.md` is enough
  — no embeddings, no RAG infra. As it grows, add a local Markdown search engine
  (e.g. **qmd** — on-device BM25 + vector + LLM re-ranking, usable as a CLI the LLM
  shells out to or as an MCP tool). Or vibe-code a simple search script with the LLM
  when the need arises.
- **Version control.** `git` for history/diffs/branching (strongly recommended).
- **Graph & query views.** A graph view (e.g. Obsidian's) is the fastest way to spot
  hub pages and orphans. Frontmatter-query plugins (e.g. Dataview) turn your
  extension keys (§3) into dynamic tables — another reason to keep frontmatter rich.
- **Images.** If sources carry images, download them locally (e.g. to `raw/assets/`)
  and reference them; have the LLM read the text first, then view specific images
  for added context.

---

## 7. Conformance & posture

- **Permissive by default** (rulebook §2). Never reject a document for a *soft*
  violation — missing optional fields, unknown `type`, broken links, absent
  `index.md`. Improve when you can; tolerate always.
- **The only hard rules are §9** (rulebook §7): parseable frontmatter, non-empty
  `type`, well-formed reserved files. Run `okf:lint` (which checks §7) before treating
  the bundle as conformant (e.g. before publishing or exchanging it).
- **Never fabricate.** Enrichment adds structure, links, and metadata — not facts.
  Externally-sourced claims get citations; unsupported ones get gap notes.

---

## 8. Using and evolving this spec

- **Drop-in:** keep this file at the space root as `AGENTS.md`/`CLAUDE.md` (read
  automatically each session) or paste it with `okf-rulebook.md` as a system prompt.
- **Co-evolve it:** when you discover a workflow tweak, a naming rule, or an edge
  case worth keeping, write it into §3 or §4. The space gets sharper every time you
  encode a lesson here instead of re-explaining it.
- **The division of labor never changes:** you curate sources, direct the analysis,
  ask good questions, and decide what it means. The LLM does everything else.

---

## 9. Quick-start checklist

- [ ] `raw/` and `wiki/` created; pack files (`okf-rulebook.md` + `concept-authoring.md` + this spec) in place
- [ ] `git init`; first commit
- [ ] `wiki/index.md` seeded with `okf_version: "0.1"` and empty sections
- [ ] Conventions recorded in §3 (subdirs, `type` vocabulary, tags, extension keys)
- [ ] First source added to `raw/`; **Ingest** run (§4.1); result validated (§7) and committed
- [ ] Cadence chosen: supervised one-at-a-time vs. batch — noted in §3
- [ ] (Later) search tool added when `index.md` alone stops scaling (§6)
