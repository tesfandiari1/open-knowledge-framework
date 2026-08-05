# OKF v0.1 Rulebook — Shared Reference

> **What this is.** The single, condensed source of truth for the Open Knowledge
> Format (OKF) v0.1. Every OKF operation and reference doc defers to this file
> instead of restating the spec, so the rules stay in one place. Section numbers in
> parentheses — e.g. (§4.1) — point to the authoritative OKF v0.1 specification.
>
> **Portability.** This is plain Markdown. Paste it into any LLM environment
> (Claude, ChatGPT/Codex, Cursor, OpenCode, Gemini, a local model) as part of a
> system prompt. No vendor lock-in, no tool-specific frontmatter, no SDK, no shell
> required. The examples here are deliberately generic — OKF's structure is
> domain-independent (§3).

---

## 1. The format in one breath

An OKF **bundle** is a directory tree of UTF-8 Markdown files (§3). Each
**concept** is one `.md` file. Its **Concept ID** is the file path minus the
`.md` suffix — `entities/ada-lovelace.md` → `entities/ada-lovelace` (§2). A
concept has YAML **frontmatter** (metadata) and a Markdown **body** (content).
Concepts link to each other with ordinary Markdown links (§5). Two filenames are
reserved at every level: `index.md` (a directory listing, §6) and `log.md` (a
change history, §7).

If you can `cat` the file, you can read OKF. If you can `git clone` the repo, you
can ship it. That is the whole contract.

### 1.1 How OKF serves an LLM-maintained wiki

This pack uses OKF as the on-disk format for a **persistent, compounding
knowledge wiki** that an LLM builds and maintains. The pattern has three layers;
OKF defines the middle one:

| Layer        | Who owns it      | What it is                                                        |
|--------------|------------------|-------------------------------------------------------------------|
| Raw sources  | the human curates| Immutable source documents (articles, transcripts, notes, data). Read, never modified. |
| **The wiki** | the LLM owns     | **An OKF bundle** — concept files, cross-links, `index.md`, `log.md`. The LLM writes and keeps it consistent. |
| The schema   | co-evolved       | The conventions and workflows that make the LLM a disciplined maintainer. **This pack is that layer.** |

Knowledge is **compiled once and kept current**, not re-derived on every query.
The three operations the wiki supports — **Ingest** (file a new source and
integrate it across pages), **Query** (answer from the wiki, optionally filing
the answer back), and **Lint** (health-check for contradictions, stale claims,
orphans, missing pages) — map onto the agents in this pack. The tedious part of a
wiki is the bookkeeping; OKF makes that bookkeeping mechanical so an LLM can do
all of it.

---

## 2. The Prime Directive: be permissive (§9)

OKF has a deliberately tiny set of hard requirements and a large set of *soft*
guidance. **Never reject or discard a document for a soft violation.** A consumer
MUST NOT refuse a bundle over:

- Missing optional frontmatter fields
- Unknown `type` values
- Unknown extra frontmatter keys
- Broken cross-links (they may be not-yet-written knowledge)
- Missing `index.md` files

Producers (the agents in this pack) improve documents toward the conventions
below; they do not gate-keep against them. The only things that make a bundle
**non-conformant** are in §7 of this rulebook.

---

## 3. Frontmatter field reference (§4.1)

Every concept document opens with a YAML block delimited by `---` on its own line
at the very top and a closing `---` on its own line. Fields below are listed in
the spec's recommended priority order.

| Field         | Status         | Type / Format                     | Purpose & rules |
|---------------|----------------|-----------------------------------|-----------------|
| `type`        | **REQUIRED**   | short string, non-empty           | The kind of concept — drives routing, filtering, presentation. Not registered centrally; pick descriptive, self-explanatory values (e.g. `Source`, `Entity`, `Concept`, `Topic`, `Comparison`, `Reference`, `Playbook`, `Metric`, `API Endpoint`, `Dataset`, `Table`). Consumers MUST tolerate unknown values. |
| `title`       | recommended    | string                            | Human-readable display name. If omitted, consumers may derive one from the filename. |
| `description` | recommended    | single sentence                   | One-line summary. Reused verbatim by `index.md` generators, search snippets, previews. Make it stand on its own. |
| `resource`    | recommended    | URI                               | Canonical URI of the underlying asset the concept describes. Omit for abstract concepts (a metric, a theme, a process) that have no physical resource. |
| `tags`        | recommended    | YAML list of short strings        | Cross-cutting categorization, e.g. `[history, computing, biography]`. |
| `timestamp`   | recommended    | ISO 8601 datetime                 | Last meaningful change, e.g. `2026-06-16T14:30:00Z`. |
| *(extensions)*| optional       | any producer-defined key/value    | Allowed and encouraged (e.g. `source_count`, `status`, `aliases`). Consumers SHOULD preserve unknown keys when round-tripping and MUST NOT reject documents for having them. |

**Authoring rules**

- `type` is the only field you may never leave blank. When unsure, choose a
  broad, honest value (`Reference`, `Concept`, `Source`) rather than guessing a
  precise one or inventing a taxonomy.
- Keep `description` to one sentence that reads well out of context — it is
  surfaced in index files and search results far from the document.
- **Quote any string value that could break YAML.** An unquoted (plain) scalar
  must not contain a colon-space (`: `) or ` #`, and must not *begin* with
  `` # @ ` [ ] { } , & * ! | > % ? : ``, a dash-space (`- `), or a quote. When in
  doubt, wrap the value in `"double quotes"` (escape any interior `"` as `\"`).
  This bites `title` and `description` most often: an unquoted `: ` — e.g.
  `description: … Source: 7 transcripts.` or `title: 04 — Intel: San Diego` — makes
  the parser read a nested mapping, so the **whole frontmatter block fails to
  parse** and tolerant consumers (Obsidian, etc.) silently render it as body text
  instead of properties. A fences-only check won't catch this; validate by
  actually parsing the YAML.
- Use ISO 8601 for `timestamp` (`YYYY-MM-DDThh:mm:ssZ`). A date-only
  `YYYY-MM-DD` is acceptable when that is all you know.
- `tags` are lowercase short strings by convention; this is guidance, not a rule.
- Extension keys are where wiki-specific metadata lives (e.g. `source_count` for
  Dataview-style queries) — use them freely; they never affect conformance.

---

## 4. Body reference (§4.2, §8)

The body is standard Markdown. **Favor structure over prose** — headings, lists,
tables, fenced code blocks — because structure helps both human reading and agent
retrieval. There are *no required* body sections.

These headings have **conventional** meaning. Use them when applicable; do not
force them when they don't fit.

| Heading        | Use it for                                                      |
|----------------|-----------------------------------------------------------------|
| `# Schema`     | Structured description of an asset's columns/fields (often a table). |
| `# Examples`   | Concrete usage examples, usually fenced code blocks.            |
| `# Citations`  | External sources backing claims in the body. See §8 / rulebook §6. |

Other headings (`# Overview`, `# Timeline`, `# Relationships`, `# Steps`,
`# Open questions`, …) are free-form and encouraged where they map to the
source's natural structure.

---

## 5. Cross-linking (§5)

Concepts relate to each other through ordinary Markdown links.

- **Absolute (bundle-relative) — PREFERRED.** Begins with `/`, resolved from the
  bundle root. Stable when a document moves within its subdirectory.
  `The [Analytical Engine](/concepts/analytical-engine.md) was the join of mechanism and computation.`
- **Relative.** Standard relative path. `See the [neighbor](./other.md).`

**Link semantics.** A link from A to B asserts *a relationship*. The *kind* of
relationship (parent/child, references, designed-by, depends-on, contradicts)
lives in the **surrounding prose, not in the link itself** (§5.3). Write the
sentence so the relationship is clear; don't try to encode it in link syntax.

**Broken links are legal** (§5.3). A link to a not-yet-written concept is a valid
forward reference — in a growing wiki it is a useful signal of a page that *should*
exist. Never delete a meaningful link just because its target is missing.

---

## 6. Citations (§8)

When the body makes a claim drawn from external material, list the source under a
`# Citations` heading at the **bottom** of the document, numbered:

```markdown
# Citations

[1] [Memex and the trails of association](https://example.org/memex)
[2] [Project interview transcript](/sources/2026-03-12-interview.md)
```

Citation links may be absolute URLs, bundle-relative paths, or paths into a
`sources/` or `references/` subdirectory that mirrors external material as
first-class OKF concepts. **Citations are only for externally-sourced claims** —
do not manufacture sources for things the document asserts on its own, and never
invent a citation to make a document look more complete.

---

## 7. Conformance — the only hard rules (§9)

A bundle is **conformant** with OKF v0.1 if and only if all three hold:

1. **Parseable frontmatter.** Every non-reserved `.md` file contains a parseable
   YAML frontmatter block (opening `---`, valid YAML, closing `---`).
2. **Non-empty `type`.** Every such frontmatter block has a `type` field with a
   non-empty value.
3. **Reserved files well-formed.** Every `index.md` and `log.md` that *is present*
   follows §6 / §7 structure (rulebook §8 / §9 below).

Everything else in this rulebook is soft guidance (see §2). Conformance is binary
and mechanical — it can be checked by a script.

---

## 8. `index.md` reference (§6, §11)

An `index.md` may appear in **any** directory, including the bundle root. It is
**content-oriented**: a catalog of what exists in that directory, supporting
**progressive disclosure** — letting a reader (or the LLM, on a query) see what
exists before opening anything.

Rules:

- **No frontmatter**, with one exception: the **bundle-root** `index.md` MAY carry
  a single frontmatter field, `okf_version: "0.1"`, declaring the targeted OKF
  version (§11). No other `index.md` has frontmatter.
- The body is one or more sections; each section heading groups entries.
- Each entry is a bullet: a Markdown link followed by ` - ` and a short
  description (pull the description from the linked concept's frontmatter).
- Links are relative to the index's own directory; subdirectories link to their
  folder (e.g. `entities/`).

```markdown
# Entities

* [Ada Lovelace](entities/ada-lovelace.md) - mathematician who wrote the first algorithm.
* [Charles Babbage](entities/charles-babbage.md) - designer of the Analytical Engine.

# Concepts

* [Analytical Engine](concepts/analytical-engine.md) - proposed general-purpose mechanical computer.
```

---

## 9. `log.md` reference (§7)

A `log.md` may appear at any level to record the **chronological** change history
of that scope. It is the timeline of the wiki's evolution.

- A flat list of **date-grouped** entries, **newest first**.
- Date headings MUST use ISO 8601 `YYYY-MM-DD`.
- Each entry is a bullet of prose; the leading **bold word** is a *convention*,
  not a requirement. Recommended action vocabulary, aligned to the wiki
  operations: `**Ingest**`, `**Query**`, `**Lint**`, `**Creation**`,
  `**Update**`, `**Deprecation**`.
- **Grep-ability.** Because the action word is a consistent bold prefix, the log
  stays searchable with plain tools (`grep Ingest log.md`, `grep "^## " log.md`)
  while remaining OKF-conformant — no non-standard heading format needed.

```markdown
# Update Log

## 2026-05-22
* **Ingest**: Filed [interview transcript](/sources/2026-03-12-interview.md); updated [Ada Lovelace](/entities/ada-lovelace.md) and [Analytical Engine](/concepts/analytical-engine.md).
* **Creation**: Added concept page for [Analytical Engine](/concepts/analytical-engine.md).

## 2026-05-15
* **Initialization**: Created foundational directory structure.
* **Lint**: Flagged orphan page [Difference Engine](/concepts/difference-engine.md) — no inbound links.
```

---

## 10. Reserved filenames (§3.1)

`index.md` and `log.md` are reserved at every level and **MUST NOT** be used as
concept documents. Every other `.md` file is a concept. There is no separate
file format for tag aggregation — tag views are synthesized at consumption time
by scanning the `tags` frontmatter field (§3.1).

---

## 11. Copy-paste concept template

Use this as the starting skeleton for a new concept document. Delete fields and
headings that don't apply; keep `type`.

```markdown
---
type:                      # REQUIRED — e.g. "Entity", "Concept", "Source", "Reference"
title:                     # recommended — human-readable display name
description:               # recommended — one sentence, reads well out of context
resource:                  # recommended — canonical URI; omit for abstract concepts
tags: []                   # recommended — [short, lowercase, strings]
timestamp:                 # recommended — ISO 8601, e.g. 2026-06-16T00:00:00Z
---

# Overview

<One or two sentences on what this concept is.>

# Schema            <!-- if it describes an asset with fields/columns -->

| Field | Type | Description |
|-------|------|-------------|
|       |      |             |

# Examples          <!-- if concrete usage helps -->

```text
<example>
```

# Citations         <!-- only if the body makes externally-sourced claims -->

[1] [Source title](https://...)
```

---

## 12. Minimal conformant bundle (vendor-neutral example)

A small research wiki built by ingesting sources about early computing:

```
my_wiki/
├── index.md          # root catalog; may carry okf_version: "0.1"
├── log.md            # chronological history of ingests / lints
├── sources/
│   ├── index.md
│   └── 2026-03-12-interview.md     # type: Source
├── entities/
│   ├── index.md
│   ├── ada-lovelace.md             # type: Entity
│   └── charles-babbage.md          # type: Entity
└── concepts/
    ├── index.md
    └── analytical-engine.md        # type: Concept
```

`concepts/analytical-engine.md`:

```markdown
---
type: Concept
title: Analytical Engine
description: Charles Babbage's proposed general-purpose mechanical computer.
tags: [history, computing]
timestamp: 2026-06-16T00:00:00Z
---

# Overview

A general-purpose mechanical computer designed by
[Charles Babbage](/entities/charles-babbage.md). The first algorithm intended
for it was written by [Ada Lovelace](/entities/ada-lovelace.md).

# Citations

[1] [Project interview transcript](/sources/2026-03-12-interview.md)
```

Each concept file has parseable frontmatter with a non-empty `type`; each
`index.md` is frontmatter-free (except the optional root `okf_version`); links
use the bundle-relative `/path.md` form. That is a conformant OKF v0.1 bundle.
