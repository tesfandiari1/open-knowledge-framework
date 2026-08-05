# {{TOPIC}} — Topic Space (AGENTS.md)

> Schema layer for the **{{TOPIC}}** topic. This is one OKF space among many under
> `../`. Read this file every session you work in
> this topic. It defers all format rules to the shared pack and records only what
> is specific to {{TOPIC}}.
>
> **Shared pack (read by reference, do not duplicate):**
> - Format rules: [`../../okf-pack/okf-rulebook.md`](../../okf-pack/okf-rulebook.md)
> - Full operating spec: [`../../okf-pack/okf-space.md`](../../okf-pack/okf-space.md)
> - Concept-writing craft: [`../../okf-pack/concept-authoring.md`](../../okf-pack/concept-authoring.md)

## Layers

| Layer | Path | Owner | Notes |
|-------|------|-------|-------|
| Raw sources | `raw/` | firecrawl + you | Immutable scraped docs. **Read, never edit.** Re-generable from `raw/SOURCES.md`. |
| The wiki | `wiki/` | the LLM | A **light** OKF bundle — navigation + on-demand synthesis. See "Wiki mode" below. |

## Wiki mode: LIGHT by default

This space optimizes for **cheap, large scrapes**, not full re-writes. The raw
firecrawl markdown is the product; the wiki is a thin layer on top of it.

**Default (≈ zero LLM tokens) — do this on every ingest:**
1. Scrape into `raw/` per `raw/SOURCES.md` (the okf plugin's `scrape_topic.sh {{TOPIC}}`).
   Resumable and idempotent: it re-pulls only new or changed URLs (unchanged ones are
   skipped), and regenerates each site's mechanical `raw/<site>/CONTENTS.md`.
2. Regenerate `wiki/index.md` so its `# Sources` section catalogs the raw sites — one
   bullet per site: `* [<site>](../raw/<site>/CONTENTS.md) - <one-line description>`.
   Also list any concept pages that exist under `# Concepts`.
3. Append an `**Ingest**` entry to `wiki/log.md`.

That's it. **Do NOT** read and rewrite every scraped page into concept documents
by default — a topic may be hundreds of pages / hundreds of thousands of words, and a
full per-page rewrite burns tokens for little gain when the raw docs are already
clean, frontmattered Markdown.

**On demand (opt-in, costs tokens) — only when the user explicitly asks:**
- Synthesize an **overview / map** page for a sub-area (`type: Topic`).
- File a **Query answer**, **Comparison**, or **Analysis** as a concept
  (`wiki/concepts/`), citing the raw pages it draws from.

Synthesize one concept at a time (the `okf:query` file-back path), never the whole
topic unasked. When you do create concept pages, they MUST be OKF-conformant
(parseable frontmatter, non-empty `type`; rulebook §7) and link to their raw sources
under a `# Citations` heading. See `../../okf-pack/concept-authoring.md` for the craft.

## Conventions (edit as the space grows)

- **`type` vocabulary:** raw docs are source material, not part of the OKF bundle, so
  §7 conformance does not apply to them — they stay as-is (firecrawl frontmatter, no
  `type`). Synthesized `wiki/` pages use `Topic`, `Concept`, `Comparison`, `Analysis`,
  `Reference`.
- **Links:** bundle-relative (`/concepts/x.md`) inside `wiki/`; raw sources are
  cited by relative path into `../raw/...`.
- **Tags:** lowercase; reuse the `base_tags` from `raw/SOURCES.md`.

## Operations

See [`../../okf-pack/okf-space.md`](../../okf-pack/okf-space.md) §4 for the full
Ingest / Query / Lint model. In this space, **Ingest defaults to the light path
above**; Query and full synthesis are opt-in.
