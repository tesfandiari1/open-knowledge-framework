# OKF — an Open Knowledge Framework for agentic knowledge bases

Most LLM-plus-documents setups are RAG: retrieve chunks, regenerate an answer, forget everything. Nothing accumulates. OKF is the opposite pattern. An agent incrementally builds and maintains a persistent, interlinked Markdown wiki over your private knowledge. Knowledge is compiled once and kept current, not re-derived on every question.

You curate sources and ask good questions. The agent does the bookkeeping: summarizing, cross-referencing, filing, consistency. The work that makes a knowledge base useful, and that humans abandon because it never ends.

## Lineage

This framework stands on two published ideas and adds the missing third piece:

| Piece | What it defines | Where it comes from |
|---|---|---|
| **The pattern** | An LLM-maintained wiki: raw sources the agent never edits, a wiki it owns, a schema that keeps it disciplined, and three operations (Ingest, Query, Lint) | [Karpathy's LLM-wiki notes](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f) |
| **The format** | The Open Knowledge Format: bundles of plain Markdown with YAML frontmatter, readable by humans without tooling and parseable by agents without SDKs. "A format, not a platform." | [Google's OKF spec](https://github.com/GoogleCloudPlatform/knowledge-catalog/blob/main/okf/SPEC.md) and [announcement](https://cloud.google.com/blog/products/data-analytics/how-the-open-knowledge-format-can-improve-data-sharing) |
| **The framework** | The operating discipline that makes the first two work in practice: a condensed rulebook, a space spec any agent can follow, concept-authoring craft, scaffolds, and a reference runtime | This repo |

The pattern says who does what. The format says what goes on disk. The framework says how to actually run it, day after day, without the wiki rotting.

## The three layers

Every OKF space has the same shape:

| Layer | Owner | On disk |
|---|---|---|
| Raw sources | **you** curate | `raw/` — immutable documents. The agent reads them, never edits them. |
| The wiki | the **agent** owns | `wiki/` — an OKF bundle: concept files, cross-links, `index.md`, `log.md`. |
| The schema | co-evolved | `AGENTS.md` plus the rulebook. The discipline that keeps the agent rigorous. |

And three operations run over it: **Ingest** (file new sources and integrate them), **Query** (answer from the compiled wiki with citations, filing good answers back), and **Lint** (health-check for contradictions, stale claims, orphans, drift).

## Quick start 1: a private knowledge space

For your own material: notes, transcripts, exports, research, anything you can save as text.

```bash
git clone <this-repo> okf && okf/scripts/new_space.sh ~/my-space
```

This stands up the full three-layer layout with the schema in place. It is self-contained and vendor-neutral: point any agent at `AGENTS.md` (Claude Code, Codex, Cursor, a local model) and it knows how to operate the space. Then:

1. Record your conventions in `AGENTS.md` §3 (taxonomy, `type` vocabulary, tags).
2. Drop a source into `raw/` and ask your agent to ingest it.
3. Ask questions. Ask for a lint now and then. Commit as you go.

## Quick start 2: a documentation knowledge base (Claude Code)

The batteries-included path for public doc sites, powered by the bundled plugin.

Prerequisites: [Claude Code](https://claude.com/claude-code), the [Firecrawl CLI](https://www.firecrawl.dev) authenticated (`firecrawl --status`), `jq`, `python3`.

```
/plugin marketplace add <your-github-user>/okf
/plugin install okf@okf-marketplace
```

Then just talk to it:

```
> Scrape the Bun docs into my knowledge base
> What do the bun docs say about test mocking?
```

| Skill | What it does |
|---|---|
| `okf:topic` | Scrape one or more sites into a new topic |
| `okf:refresh` | Re-scrape an existing topic and report the delta |
| `okf:query` | Answer from the collected docs, with citations |
| `okf:lint` | Audit a topic and apply mechanical fixes |

The knowledge base lives at `~/code/knowledge-base` by default (set `OKF_KB_ROOT` to move it). Scraping is resumable and cheap: raw docs are the product, and the agent does not rewrite pages into summaries unless you ask.

## Check any knowledge base

`scripts/okf.py` checks any folder of Markdown files, with any agent or viewer. It needs only [uv](https://docs.astral.sh/uv/):

```bash
uv run scripts/okf.py check ~/my-notes
```

Hard failures are the OKF conformance rules, which are the same in v0.1 and v0.2. Every note has parseable frontmatter with a non-empty `type`, and every `index.md` and `log.md` is well formed. The command exits 1 when any rule fails. Warnings cover the rest:
- missing descriptions
- dead `[[wikilinks]]` and Markdown links
- dead paths in `AGENTS.md` and `CLAUDE.md`
- missing images
- ambiguous duplicate names
- index files over 4 KB
- inbox files that no note links to yet
- agent instructions that load on every turn (`CLAUDE.md`, its `@imports`, and unscoped `.claude/rules`) over 16 KB, about 4,000 tokens

Output lists at most 20 findings per kind (`--all` lists every one). To tell the checker which folders hold sources, inbox material or files to skip, copy `okf.toml.example` to your root as `okf.toml`. Test: `uv run tests/test_okf.py`.

**Stop new damage without fixing the old first.** The pre-commit hook blocks a commit only when it adds hard failures. It stores the current count in `.okf-baseline`, and that count only goes down:

```bash
cd ~/my-notes && ln -s ~/code/okf/hooks/pre-commit .git/hooks/pre-commit   # set OKF_HOME if okf lives elsewhere
```

## What's in the repo

```
okf-pack/                  The framework's reference layer (start here)
  okf-rulebook.md          Condensed OKF format spec: frontmatter, links, conformance
  okf-space.md             Space spec: setup + Ingest/Query/Lint. Doubles as AGENTS.md
  concept-authoring.md     Judgment for writing one good concept on demand
  topic-AGENTS.template.md Per-topic schema seed for the doc-scraping path
scripts/                   Scaffolds + the Firecrawl ingestion pipeline
  okf.py                   Check any knowledge base for conformance and drift
  new_space.sh             Stand up a private knowledge space anywhere
  new_topic.sh             Scaffold a scraped-docs topic
skills/                    Claude Code runtime: topic, refresh, query, lint
.claude-plugin/            Plugin + marketplace manifests (this repo installs as a plugin)
```

## Design principles

- **Format, not platform.** Everything on disk is Markdown and YAML frontmatter. If you can `cat` it you can read it, and if you can `git clone` it you can ship it. No vendor lock-in at the knowledge layer.
- **Light by default.** Ingest is mechanical and nearly token-free. Synthesis into concept pages is opt-in, one concept at a time. A thousand-page scrape should not cost a thousand pages of rewriting.
- **Permissive conformance.** Only three things break a bundle: unparseable frontmatter, an empty `type`, a malformed reserved file. Everything else is a signal, not a rejection.
- **The wiki compounds.** Good answers get filed back as concepts. Cross-references, contradictions, and gaps are recorded where the next session will find them.

## Status

The rulebook condenses OKF **v0.1**. Upstream is now at [v0.2](https://github.com/GoogleCloudPlatform/knowledge-catalog/blob/main/okf/SPEC.md), which adds provenance (`sources`), trust tiers (`generated` / `verified`), lifecycle fields (`status`, `stale_after`), and attested computations. Tracking v0.2 is the next planned spec update.

## Extending

Add a skill under `skills/<name>/SKILL.md` (kebab-case folder, frontmatter `name` matching the folder, a description that says what it does and when to trigger). Add pipeline steps under `scripts/`. The reference docs in `okf-pack/` are the single source of truth: skills and scaffolds defer to them rather than restating rules.

## License

[MIT](LICENSE)
