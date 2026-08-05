#!/usr/bin/env bash
# Scrape every site declared in topics/<slug>/raw/SOURCES.md into raw/, then
# regenerate each site's CONTENTS.md manifest.
#   scrape_topic.sh <topic-slug>
#
# Pipeline per site (reuses scrape_urls.sh + firecrawl_to_md.py + gen_index.py):
#   firecrawl map  -> raw/<site>.urls.txt   (pauses for hand-edit if newly created)
#   scrape_urls.sh -> .firecrawl/raw-<slug>-<site>/*.json
#   firecrawl_to_md.py -> raw/<site>/*.md
#   gen_index.py   -> raw/<site>/CONTENTS.md
set -euo pipefail

SCRIPTS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
KB="${OKF_KB_ROOT:-$HOME/code/knowledge-base}"
slug="${1:?usage: scrape_topic.sh <topic-slug>}"
topic="$KB/topics/$slug"
mkdir -p "$KB/.firecrawl"
sources="$topic/raw/SOURCES.md"
[ -f "$sources" ] || { echo "no SOURCES.md at $sources" >&2; exit 1; }
date="$(date +%Y-%m-%d)"

# Extract the fenced ```sources block; drop full-line comments and blank lines.
# (Only whole-line `#` comments — never strip inline `#`, which can appear in a
# regex or URL fragment inside extra_flags.)
rows="$(awk '/^```sources/{f=1;next} /^```/{f=0} f' "$sources" \
        | sed -e '/^[[:space:]]*#/d' -e '/^[[:space:]]*$/d')"
[ -n "$rows" ] || { echo "no site rows in $sources (fill the \`\`\`sources block)" >&2; exit 1; }

while IFS=$'\t' read -r site map_url base_tags extra; do
  [ -z "${site:-}" ] && continue
  site="$(echo "$site" | xargs)"; map_url="$(echo "$map_url" | xargs)"
  base_tags="$(echo "$base_tags" | xargs)"
  if [ -z "$map_url" ]; then
    echo "row '$site' has no map_url — columns must be TAB-separated." >&2; exit 1
  fi
  origin="$(echo "$map_url" | sed -E 's#^(https?://[^/]+).*#\1#')"
  urls="$topic/raw/$site.urls.txt"
  rawjson="$KB/.firecrawl/raw-$slug-$site"
  echo "=== $slug / $site  ($map_url) ==="

  if [ ! -s "$urls" ]; then
    map_json="$KB/.firecrawl/$slug-$site-map.json"
    firecrawl map "$map_url" --limit 1000 --json -o "$map_json"
    jq -r '.data.links[].url' "$map_json" | sort -u > "$urls"
    echo ">> Wrote $urls ($(wc -l < "$urls") URLs)."
    echo ">> Hand-edit it now (drop translations/blog/auto-gen dumps), then re-run."
    echo ">> Skipping scrape of '$site' this pass."
    continue
  fi

  bash "$SCRIPTS_DIR/scrape_urls.sh" "$urls" "$rawjson"
  # Tokenize extra_flags honoring the shell-style quoting authored in SOURCES.md,
  # so a quoted regex reaches Python as one bare argument (no literal quote chars,
  # backslashes preserved). eval runs trusted local config; treat SOURCES.md as code.
  eval "extra_args=(${extra:-})"
  python3 "$SCRIPTS_DIR/firecrawl_to_md.py" \
    --raw-dir "$rawjson" --out-dir "$topic/raw/$site" \
    --site "$site" --base-url "$origin" --base-tags "$base_tags" \
    --scraped-date "$date" "${extra_args[@]+"${extra_args[@]}"}"
  python3 "$SCRIPTS_DIR/gen_index.py" "$topic/raw/$site" "$site"
done <<< "$rows"

echo
echo "Done. Now regenerate $topic/wiki/index.md and append an Ingest entry to"
echo "$topic/wiki/log.md (light-wiki path — see $topic/AGENTS.md)."
