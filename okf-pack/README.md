# OKF Pack

The shared **reference layer** for the Open Knowledge Format (OKF v0.1) — the
plain-Markdown rules and craft that turn a pile of source documents into a
persistent, interlinked Markdown wiki an LLM builds and keeps current.

The reference docs are **LLM-agnostic** (no harness-specific frontmatter, no SDK).
The *operations* are run by the Claude Code **okf plugin's skills**
(`topic`, `refresh`, `query`, `lint`); the docs here are what those skills — or any
LLM you paste them into — defer to for format and judgment.

---

## The idea in one paragraph

Most LLM-plus-documents setups are RAG: upload files, retrieve chunks at query time,
regenerate an answer from scratch every time — nothing accumulates. OKF instantiates
a different pattern: the LLM **incrementally builds and maintains a persistent wiki**
that sits between you and your raw sources. You curate sources and ask good
questions; the LLM does the bookkeeping — summarizing, cross-referencing, filing,
consistency. Knowledge is **compiled once and kept current**, not re-derived per
query. OKF v0.1 is the on-disk format; this pack is the discipline that keeps the LLM
a rigorous maintainer rather than a generic chatbot.

---

## Light by default

A topic can be hundreds of scraped pages. OKF does **not** rewrite every page into
hand-crafted concept documents — the raw, frontmattered Markdown is the product, and
the `wiki/` is a thin catalog over it. Full synthesis into concept pages is
**on demand, one concept at a time** (the `query` "file back" step), never a batch
pass. This is why the pack is three small reference docs and not a multi-agent
pipeline.

---

## What's in the pack

| File | Role |
|------|------|
| [`okf-rulebook.md`](okf-rulebook.md) | The condensed OKF v0.1 **format** spec — frontmatter, body, links, citations, conformance (§7), the concept template (§11). Single source of truth for *format*. **Read this first.** |
| [`okf-space.md`](okf-space.md) | **Setup & operating spec** — how to stand up an OKF space (`raw/` + `wiki/`) and run the Ingest / Query / Lint operations over time. Doubles as a drop-in `AGENTS.md`/`CLAUDE.md`. |
| [`concept-authoring.md`](concept-authoring.md) | The **judgment** for writing one good concept on demand — choosing `type`, a pre-file self-check, gap/conflict notes. Used by the `query` file-back step. |
| [`topic-AGENTS.template.md`](topic-AGENTS.template.md) | Per-topic `AGENTS.md` seed (`{{TOPIC}}` substituted by the plugin's `scripts/new_topic.sh`). |

---

## How operations run

The three OKF operations are skills in the okf plugin backed by a small script
pipeline; there is no agent pipeline.

| Operation | Skill | What happens |
|-----------|-------|--------------|
| **Ingest** | `okf:topic` (new) / `okf:refresh` (existing) | Scrape sources with Firecrawl → clean, frontmattered Markdown in `raw/` (`scripts/firecrawl_to_md.py`); regenerate each site's `CONTENTS.md` (`scripts/gen_index.py`); refresh the light `wiki/` catalog. |
| **Query** | `okf:okf` | Answer from the compiled corpus with citations; optionally file the answer back as a conformant concept (per `concept-authoring.md` + the rulebook). |
| **Lint** | `okf:okf` | Run `scripts/okf.py check` for conformance (rulebook §7) and drift, fix what it reports, and rebuild indexes with `scripts/okf.py index`. |

Heavy unattended bulk synthesis is **not** part of the system. If it is ever needed,
it would graduate as an explicit, opt-in Claude Code `/workflow` whose agents read
these same reference docs — which is exactly why the docs are the single source of
truth.

---

## Conformance posture

Faithful to OKF's permissive model (rulebook §2): **never reject a document for a
soft violation**. Only three things break conformance — unparseable frontmatter, an
empty/missing `type`, or a malformed reserved file (rulebook §7). Everything else
(missing optional fields, unknown types, broken links, absent `index.md`) is improved
when possible and tolerated always.

---

## Portability

`okf-rulebook.md` and `concept-authoring.md` are plain, vendor-neutral Markdown —
paste them into any LLM environment (Claude, ChatGPT/Codex, Cursor, a local model)
and the format + craft travel unchanged. The Claude Code skills are the convenient
runtime wrapper around them in this repo; the format does not depend on them.

---

## Start here

1. Read [`okf-rulebook.md`](okf-rulebook.md).
2. Standing up a space? Follow [`okf-space.md`](okf-space.md) (`raw/` + `wiki/`,
   conventions, the Ingest/Query/Lint operations).
3. With the okf plugin installed, just use the skills: `okf:topic` to scrape a new
   topic, `okf:okf` to ask the corpus or audit it.
