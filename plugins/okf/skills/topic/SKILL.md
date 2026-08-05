---
name: topic
description: |
  Add documentation for a topic to the OKF knowledge base: scaffold a topic folder, scrape one or more sites with Firecrawl into clean frontmattered Markdown, and refresh the light navigation wiki. Use when the user gives URLs or a doc site and wants them collected for reference, e.g. "scrape the Bun docs into my knowledge base", "add Svelte 5 docs as a topic", "gather these pages for later", or "create a new topic from a URL". Pairs with the firecrawl skill (the scraping engine) and the okf:refresh / okf:query / okf:lint skills.
allowed-tools:
  - Bash
  - Read
  - Write
  - Edit
---

# okf:topic — scrape docs into a new knowledge-base topic

Turn a few URLs (or a doc site) into a self-contained topic in the OKF knowledge
base: an immutable `raw/` scrape plus a light `wiki/` index. This skill drives the
KB's own pipeline scripts; it does not reinvent scraping.

## Critical context

- **Knowledge base root:** `${OKF_KB_ROOT:-$HOME/code/knowledge-base}`. Resolve it
  once at the start: `KB="${OKF_KB_ROOT:-$HOME/code/knowledge-base}"`. If `$KB` does
  not exist, stop and ask the user where the KB lives.
- **Light wiki by default.** The scraped Markdown is the product. Do **not** read
  and rewrite scraped pages into OKF concept documents — a topic can be hundreds of
  pages and that burns tokens for little gain. The wiki layer is just a mechanical
  catalog. Full concept synthesis is the job of `okf:query`, on demand.
- **Firecrawl costs credits.** Curate the URL list before scraping; never scrape a
  whole auto-generated API reference (thousands of pages) without subsetting.
- **Output is auto-cleaned.** `firecrawl_to_md.py` sets frontmatter `description` from
  the page's own `metadata.description` (heuristic fallback only when absent) and strips
  docs-platform chrome (e.g. Mintlify llms.txt blockquotes, skip-links, anchor permalinks).
  Do not hand-edit scraped Markdown; if a new site leaks chrome, add a rule in
  `scripts/firecrawl_to_md.py`, never per-topic.
- Each topic is one OKF space: `topics/<slug>/{AGENTS.md, raw/, wiki/}`. See
  `$KB/README.md` for the full model.

## Workflow

### Step 1 — Resolve KB and topic slug
```bash
KB="${OKF_KB_ROOT:-$HOME/code/knowledge-base}"
[ -d "$KB" ] || { echo "KB not found at $KB — ask the user"; }
```
Pick a short kebab-case `slug` for the topic (e.g. `bun`, `svelte-5`). If
`topics/<slug>/` already exists, this is a refresh — use **okf:refresh** instead.

### Step 2 — Scaffold the topic
```bash
"$KB/scripts/new_topic.sh" <slug>
```
Creates `topics/<slug>/` with `raw/SOURCES.md`, a seeded `wiki/`, and `AGENTS.md`.

### Step 3 — Discover & curate URLs (per site)
**Optional pre-seed.** If you skip this step, Step 5's `scrape_topic.sh` runs
`firecrawl map` for you and pauses so you can curate the generated `<site>.urls.txt`
before scraping. Do Step 3 by hand only to pre-seed or curate the URL list up front
(recommended for large sites). Don't map twice — pick one path.

For each site the user wants, use the **firecrawl** skill to map it, then **curate**:
```bash
firecrawl map "<site-url>" --limit 1000 --json -o "$KB/.firecrawl/<slug>-<site>-map.json"
jq -r '.data.links[].url' "$KB/.firecrawl/<slug>-<site>-map.json" | sort -u \
  > "$KB/topics/<slug>/raw/<site>.urls.txt"
```
Then **edit `<site>.urls.txt`**: drop translations, blog/changelog noise, fragment
dupes, and large auto-generated API dumps. Show the user the count and a sample;
confirm before scraping. For a handful of known URLs, write them straight into the
`.urls.txt` file and skip `map`.

### Step 4 — Declare the source in SOURCES.md
Add one **TAB-separated** row per site inside the ```` ```sources ```` block of
`topics/<slug>/raw/SOURCES.md`. Columns: `site_slug⇥map_url⇥base_tags⇥extra_flags`.
- `base_tags`: comma-separated, lowercase (e.g. `bun,runtime`).
- `extra_flags`: optional firecrawl_to_md.py flags, quoted normally —
  `--strip-title-suffix "\s*[-|]\s*Bun\s*$"`, `--strip-path-prefix /docs`, `--skip-404`.
  Quote regexes; the pipeline tokenizes them correctly. **Use real tabs between
  columns**, not spaces (spaces in a row are rejected). Tip: check one scraped title
  first — sites suffix with either `-` or `|` (e.g. `Page - Acme Docs`), so match both
  with `[-|]` and include the full trailing brand (`Acme Docs`, not just `Acme`).

### Step 5 — Scrape
```bash
"$KB/scripts/scrape_topic.sh" <slug>
```
**Background it for more than ~20 URLs.** At ~2–3s/page and 5 concurrent, a large
topic easily exceeds a foreground command's time limit. Run it detached and poll the
log — e.g. `... > "$KB/.firecrawl/scrape-<slug>.log" 2>&1 &` (or your Bash tool's
background mode), then `tail` the log until it prints the "Wrote N markdown files" line.

Resumable and idempotent. If a `.urls.txt` was newly created by the script's own
`map`, it writes the list and stops for curation — curate, then re-run. This scrapes
each URL to JSON (cached in `.firecrawl/raw-<slug>-<site>/`), transforms it to
frontmattered, auto-cleaned Markdown under `raw/<site>/`, and regenerates each site's
`CONTENTS.md`. Because the JSON is cached, re-running after a transform change re-derives
all Markdown for **free** (no re-scrape).

### Step 6 — Refresh the light wiki (mechanical, ~free)
Update `topics/<slug>/wiki/index.md` so its `# Sources` section links each scraped
site's `../raw/<site>/CONTENTS.md` with a one-line description, then append an
`**Ingest**` entry (today's date) to `topics/<slug>/wiki/log.md`. Keep `# Concepts`
empty unless the user asked for synthesis. (Mirror the existing topics' wiki seeds.)

### Step 7 — Report
Tell the user: topic path, sites + page counts, and how to reference it
(`topics/<slug>/raw/` verbatim, or `wiki/index.md` to navigate). If anything was
dropped during curation, say what and why (don't silently truncate).

## Example

User: "Scrape the Bun docs into my knowledge base."
1. `KB=...`; slug = `bun`.
2. `new_topic.sh bun`.
3. `firecrawl map https://bun.sh/docs …` → `raw/bun-docs.urls.txt`; drop `/blog`, locales; ~90 URLs left; confirm with user.
4. SOURCES row: `bun-docs⇥https://bun.sh/docs⇥bun,runtime⇥--strip-title-suffix "\s*\|\s*Bun\s*$"`.
5. `scrape_topic.sh bun` → `raw/bun-docs/*.md` + `CONTENTS.md`.
6. Refresh `wiki/index.md` + log Ingest.
7. Report: "topics/bun — 88 pages from bun.sh; reference topics/bun/raw/."

## Troubleshooting

- **`KB not found`** — set `OKF_KB_ROOT` or pass the right path; the KB is the
  `knowledge-base` repo.
- **`firecrawl` not authenticated** — `firecrawl --status`; see the firecrawl skill.
- **`row '<x>' has no map_url — columns must be TAB-separated`** — the SOURCES row
  used spaces; re-enter with literal tabs.
- **Huge map (thousands of URLs)** — do NOT scrape all. Subset the `.urls.txt` to
  the high-value pages first (credit + token budget).
- **Topic already exists** — use **okf:refresh** to re-scrape, not this skill.
