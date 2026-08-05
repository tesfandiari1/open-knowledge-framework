#!/usr/bin/env bash
# Scrape every URL in a list to raw JSON, up to MAX_PARALLEL concurrent (must not
# exceed your Firecrawl plan's parallel-scrape limit; check `firecrawl --status`).
# Resumable: skips URLs whose raw JSON already exists.
#   scrape_urls.sh <url-list-file> <raw-dir>
set -uo pipefail

URL_FILE="${1:?url list file required}"
RAW_DIR="${2:?raw output dir required}"
MAX_PARALLEL="${MAX_PARALLEL:-5}"
# Accept Firecrawl-cached content up to this age (ms) instead of forcing a fresh
# fetch — much cheaper/faster on refresh. Default 2 days; override via env.
MAX_AGE="${FIRECRAWL_MAX_AGE:-172800000}"
mkdir -p "$RAW_DIR"

slug() {  # url -> safe filename stem (path with / -> __)
  echo "$1" | sed -E 's#^https?://[^/]+##; s#^/##; s#/#__#g; s#[^A-Za-z0-9._-]#_#g; s#^$#index#'
}

scrape_one() {
  local url="$1" out="$2"
  if [[ -s "$out" ]]; then echo "  = cached $(basename "$out")"; return 0; fi
  if firecrawl scrape "$url" --format markdown,links --only-main-content --max-age "$MAX_AGE" -o "$out" >/dev/null 2>&1 \
     && [[ -s "$out" ]]; then
    echo "  + ok    $(basename "$out")"
  else
    echo "  ! FAIL  $url"; rm -f "$out"
  fi
}

n=0
while IFS= read -r url; do
  [[ -z "$url" ]] && continue
  out="$RAW_DIR/$(slug "$url").json"
  scrape_one "$url" "$out" &
  n=$((n+1))
  if (( n % MAX_PARALLEL == 0 )); then wait; fi
done < "$URL_FILE"
wait
echo "Done. Raw files in $RAW_DIR:"
ls -1 "$RAW_DIR" | wc -l
