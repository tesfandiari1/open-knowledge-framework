---
name: refresh
description: |
  Re-scrape an existing OKF knowledge-base topic and regenerate its indexes, reporting what changed. Use when the user wants to update, re-pull, or refresh docs already collected for a topic, e.g. "update the tauri docs", "re-scrape premiere-pro", "refresh my knowledge base for a topic", "pull the latest docs for a topic". For a brand-new topic that does not exist yet, use okf:topic instead.
license: MIT
allowed-tools: Bash, Read, Write, Edit
---

# okf:refresh — update an existing topic

Re-pull a topic's sources and bring its indexes and light wiki back in sync,
then report the page-count delta. Same pipeline as okf:topic, minus scaffolding.

## Critical context

- **Plugin root:** `OKF="${CLAUDE_PLUGIN_ROOT}"`; if that variable is unset, use the
  plugin directory this skill loaded from (two levels up from this SKILL.md).
- **KB root:** `KB="${OKF_KB_ROOT:-$HOME/code/knowledge-base}"`. If `$KB` is missing, ask.
- The topic must already exist (`topics/<slug>/`). If not, this is okf:topic's job.
- **Light wiki** still applies — refresh re-indexes; it does not rewrite pages into
  concepts. Existing `wiki/concepts/` pages are left untouched (they may now cite
  pages that changed — flag that, don't auto-edit).
- **Refresh fetches every URL again.** A plain `scrape_topic.sh` run only rebuilds
  Markdown from the local JSON cache, so refresh sets `OKF_RESCRAPE=1`.
- **Cached re-pulls.** `scrape_urls.sh` passes Firecrawl `--max-age` (`FIRECRAWL_MAX_AGE`,
  default 2 days in ms), so unchanged pages return from Firecrawl's cache — cheaper and
  faster. Set `FIRECRAWL_MAX_AGE=0` to force a fresh fetch from origin.
- **Cleaning is automatic** (same transform as okf:topic): frontmatter `description` comes
  from the page's `metadata.description` and docs-platform chrome is stripped. A plain
  `scrape_topic.sh` re-run after a pipeline change upgrades existing pages with no new
  credits spent.

## Workflow

### Step 1 — Resolve and confirm
```bash
OKF="${CLAUDE_PLUGIN_ROOT}"   # plugin root; if unset, use this skill's plugin directory
KB="${OKF_KB_ROOT:-$HOME/code/knowledge-base}"
slug=<topic>
[ -d "$KB/topics/$slug" ] || { echo "no such topic: $slug (use okf:topic)"; exit 1; }
```

### Step 2 — Snapshot page hashes (for the delta)
```bash
(cd "$KB/topics/$slug/raw" && find . -mindepth 2 -name '*.md' ! -name CONTENTS.md | sort | while read -r f; do
  echo "$(sed '/^scraped_date:/d' "$f" | shasum | cut -c1-12) $f"
done) > "$KB/.firecrawl/okf-refresh-$slug-before.txt"
```
The hash skips the `scraped_date` line, because that line changes on every run.
(`.firecrawl/` is the KB's gitignored cache — scoped per-KB and per-slug, so no
`/tmp` collisions and nothing to clean from git.)

### Step 3 — (optional) force fresh URL discovery
Only if the user wants to pick up newly added pages on the source site:
```bash
rm -f "$KB/topics/$slug/raw/"*.urls.txt   # next run re-runs `firecrawl map`
```
Skip this to just re-pull the already-curated URL set. If you re-map, **re-curate**
the regenerated `.urls.txt` before continuing (drop translations/blog/auto-gen dumps).

### Step 4 — Re-scrape + re-index
```bash
OKF_RESCRAPE=1 "$OKF/scripts/scrape_topic.sh" "$slug"
```
**Background it for more than ~20 URLs** (it can exceed a foreground command's time
limit): run detached with output to `"$KB/.firecrawl/scrape-$slug.log"` (or your Bash
tool's background mode) and `tail` the log until "Wrote N markdown files" or
"URL(s) failed" appears.

This fetches every URL again, re-transforms to Markdown, and regenerates each site's
`raw/<site>/CONTENTS.md`. If it printed that a newly-mapped `.urls.txt` was written
and stopped, curate that file and re-run. If it exits 1, each `! FAIL` line shows the
error. Fix the cause, then re-run.

### Step 5 — Compute the delta
```bash
(cd "$KB/topics/$slug/raw" && find . -mindepth 2 -name '*.md' ! -name CONTENTS.md | sort | while read -r f; do
  echo "$(sed '/^scraped_date:/d' "$f" | shasum | cut -c1-12) $f"
done) > "$KB/.firecrawl/okf-refresh-$slug-after.txt"
diff "$KB/.firecrawl/okf-refresh-$slug-before.txt" \
     "$KB/.firecrawl/okf-refresh-$slug-after.txt" || true
```
A page only on a `>` line was added. A page only on a `<` line was removed. A page on
both was changed. The after file has one line per page, so `wc -l` on it gives the
total. Optional: if the KB is a git repo, `git -C "$KB" status --short
"topics/$slug/raw"` shows the same pages.

### Step 6 — Refresh wiki + log
Update `topics/$slug/wiki/index.md` if the set of sites changed (links to each
`../raw/<site>/CONTENTS.md`). Add an `**Ingest**` entry that names the delta at the
top of `wiki/log.md`, directly under `# Update Log`. Put it under today's
`## YYYY-MM-DD` heading, and reuse that heading if it is already there, e.g.
`* **Ingest**: Refreshed tauri-v2: +3 pages, 1 updated.`
If any `wiki/concepts/` page cites a page that changed, list those for the user.

### Step 7 — Check
```bash
uv run -q "$OKF/scripts/okf.py" check "$KB"
```
Fix every HARD finding before you report, then run check again to confirm.

### Step 8 — Report
State per-site deltas (added / updated / removed), total pages now, and any concept
pages that may need review. If the KB is a git repo, suggest a commit.

## Troubleshooting

- **`no such topic`** — list `topics/` in the KB; the user may mean a different slug,
  or this should be okf:topic.
- **Nothing changed** — expected when the source is stable; report "no changes".
- **Many pages removed** — the source may have restructured URLs; check the
  `.urls.txt` against a fresh `firecrawl map` before trusting the delta.
- **Conformance worries after refresh** — run okf:okf.
