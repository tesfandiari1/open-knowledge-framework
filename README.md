# OKF Marketplace

A Claude Code skill marketplace. It ships the **okf** plugin, which turns scraped documentation into a searchable, multi-topic knowledge base you can query without leaving your session.

## Installation

Add the marketplace, then install the plugin:

```
/plugin marketplace add /Users/tristin/code/okf
/plugin install okf@okf-marketplace
```

Once the repo is on GitHub, others can add it with:

```
/plugin marketplace add <owner>/okf
```

## What the okf plugin does

Point it at a doc site and it builds a topic folder of clean, frontmattered Markdown with a light navigation wiki on top. Later you can query it, refresh it, and audit it.

| Skill | What it does | Say something like |
|---|---|---|
| `okf:topic` | Scrape one or more sites into a new topic | "Scrape the Bun docs into my knowledge base" |
| `okf:refresh` | Re-scrape an existing topic and report what changed | "Update the tauri docs" |
| `okf:query` | Answer a question from the collected docs | "What do the tauri docs say about IPC?" |
| `okf:lint` | Health-check a topic and list gaps | "Is the premiere-pro topic OKF-conformant?" |

Scraping runs on [Firecrawl](https://firecrawl.dev), so the `firecrawl` CLI must be installed and authenticated for `okf:topic` and `okf:refresh`.

## Repository layout

```
.claude-plugin/
  marketplace.json      Marketplace manifest
plugins/
  okf/
    .claude-plugin/
      plugin.json       Plugin manifest
    skills/
      topic/SKILL.md    Add a topic
      refresh/SKILL.md  Re-scrape a topic
      query/SKILL.md    Query the knowledge base
      lint/SKILL.md     Audit a topic
```

## Adding a skill

1. Create `plugins/okf/skills/<skill-name>/SKILL.md` with a kebab-case folder name.
2. Give the frontmatter a `name` matching the folder and a `description` that states what the skill does and when to use it, with trigger phrases users would actually say.
3. Keep SKILL.md focused. Move long reference material to a `references/` folder inside the skill.
4. Reinstall or update the plugin, then test that the skill triggers on obvious and paraphrased requests but not on unrelated ones.

## Adding a plugin

1. Create `plugins/<plugin-name>/` with a `.claude-plugin/plugin.json` and a `skills/` folder.
2. Register it in `.claude-plugin/marketplace.json` under `plugins` with `"source": "./plugins/<plugin-name>"`.

## License

MIT
