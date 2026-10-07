#!/usr/bin/env bash
# Scrape every URL in a list to raw JSON, up to MAX_PARALLEL concurrent (must not
# exceed your Firecrawl plan's parallel-scrape limit; check `firecrawl --status`).
# Resumable: skips URLs whose raw JSON already exists. OKF_RESCRAPE=1 fetches them again.
# Exits 1 if any URL failed.
#   scrape_urls.sh <url-list-file> <raw-dir>
set -uo pipefail

URL_FILE="${1:?url list file required}"
RAW_DIR="${2:?raw output dir required}"
MAX_PARALLEL="${MAX_PARALLEL:-5}"
# Accept Firecrawl-cached content up to this age (ms) instead of forcing a fresh
# fetch — much cheaper/faster on refresh. Default 2 days; override via env.
MAX_AGE="${FIRECRAWL_MAX_AGE:-172800000}"
command -v firecrawl >/dev/null || { echo "firecrawl CLI not found. Install it, then run firecrawl login." >&2; exit 1; }
mkdir -p "$RAW_DIR"

slug() {  # url -> safe filename stem (path with / -> __)
  echo "$1" | sed -E 's#^https?://[^/]+##; s#^/##; s#/#__#g; s#[^A-Za-z0-9._-]#_#g; s#^$#index#'
}

scrape_one() {
  local url="$1" out="$2" log
  if [[ -s "$out" && -z "${OKF_RESCRAPE:-}" ]]; then echo "  = cached $(basename "$out")"; return 0; fi
  # Write to a temp file, so a failed re-scrape keeps the old cached JSON.
  if log=$(firecrawl scrape "$url" --format markdown,links --only-main-content --max-age "$MAX_AGE" -o "$out.tmp" 2>&1) \
     && [[ -s "$out.tmp" ]]; then
    mv "$out.tmp" "$out"; echo "  + ok    $(basename "$out")"
  else
    echo "  ! FAIL  $url: $(printf '%s\n' "$log" | tail -n 1)"; rm -f "$out.tmp"; return 1
  fi
}

fails=0; pids=()
reap() {  # wait for the running batch and count its failures
  local p
  for p in ${pids[@]+"${pids[@]}"}; do wait "$p" || fails=$((fails+1)); done
  pids=()
}
while IFS= read -r url; do
  [[ -z "$url" ]] && continue
  scrape_one "$url" "$RAW_DIR/$(slug "$url").json" &
  pids+=($!)
  if (( ${#pids[@]} >= MAX_PARALLEL )); then reap; fi
done < "$URL_FILE"
reap
echo "Done. Raw files in $RAW_DIR:"
ls -1 "$RAW_DIR" | wc -l
if (( fails )); then echo "$fails URL(s) failed. Fix the cause shown above, then re-run." >&2; exit 1; fi
