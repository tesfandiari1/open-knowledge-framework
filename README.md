# OKF Marketplace

A Claude Code plugin marketplace for the **okf** plugin: turn any documentation site into a local, searchable knowledge base that Claude builds, queries, and maintains for you.

Point it at a doc site and one prompt later you have clean, frontmattered Markdown on disk, cataloged and ready to cite. Ask a question and Claude answers from the collected docs with exact source citations, not from memory.

## Prerequisites

- [Claude Code](https://claude.com/claude-code)
- [Firecrawl CLI](https://www.firecrawl.dev), installed and authenticated (`firecrawl --status` should succeed) — used by `okf:topic` and `okf:refresh`
- `jq` and `python3` on your PATH (PyYAML optional, for stricter lint checks)

## Installation

In Claude Code:

```
/plugin marketplace add <your-github-user>/okf
/plugin install okf@okf-marketplace
```

From a local clone instead:

```
/plugin marketplace add /path/to/okf
/plugin install okf@okf-marketplace
```

## Quick start

```
> Scrape the Bun docs into my knowledge base
```

Claude scaffolds a topic, maps the site, pauses so you can trim the URL list, scrapes, and indexes. Then:

```
> What do the bun docs say about test mocking?
```

Claude greps the topic, reads only the relevant pages, and answers with citations.

## The skills

| Skill | What it does | Say something like |
|---|---|---|
| `okf:topic` | Scrape one or more sites into a new topic | "Scrape the Bun docs into my knowledge base" |
| `okf:refresh` | Re-scrape an existing topic and report the delta | "Update the tauri docs" |
| `okf:query` | Answer from the collected docs, with citations | "What do the tauri docs say about IPC?" |
| `okf:lint` | Audit a topic and apply mechanical fixes | "Check the knowledge base for stale pages" |

## How it works

Your knowledge base is a plain data directory, created on first use at `~/code/knowledge-base`. Set `OKF_KB_ROOT` to put it somewhere else. Each topic is a self-contained [OKF](plugins/okf/okf-pack/) space:

```
<knowledge base>/
├── okf-pack/           # OKF format docs, seeded from the plugin
└── topics/
    └── <topic>/
        ├── AGENTS.md   # per-topic conventions
        ├── raw/        # immutable scraped docs + SOURCES.md scrape config
        └── wiki/       # light catalog: index.md + log.md (+ on-demand concepts)
```

Two design rules keep it cheap:

- **Raw docs are the product.** Scraping and indexing are mechanical and spend almost no tokens. Claude does not rewrite pages into summaries unless you ask.
- **Scraping is resumable.** Re-runs skip unchanged pages, so a refresh only spends Firecrawl credits on what changed.

The format itself (the [okf-pack](plugins/okf/okf-pack/) reference docs) is vendor-neutral Markdown — the knowledge base stays useful outside Claude Code.

## Repository layout

```
.claude-plugin/marketplace.json    Marketplace manifest
plugins/okf/
  .claude-plugin/plugin.json       Plugin manifest
  skills/                          topic, refresh, query, lint
  scripts/                         Firecrawl ingestion pipeline
  okf-pack/                        OKF format spec + authoring docs
```

## Extending

**Add a skill:** create `plugins/okf/skills/<name>/SKILL.md` (kebab-case folder). The frontmatter `name` must match the folder, and the `description` must say what the skill does and when to use it, with phrases users would actually say. Keep SKILL.md focused; put long reference material in the skill's `references/` folder or `okf-pack/`.

**Add a plugin:** create `plugins/<name>/` with its own `.claude-plugin/plugin.json` and `skills/`, then register it in `.claude-plugin/marketplace.json` with `"source": "./plugins/<name>"`.

## License

[MIT](LICENSE)
