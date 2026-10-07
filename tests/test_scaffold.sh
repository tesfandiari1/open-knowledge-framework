#!/bin/sh
# Scaffold and hook test: sh tests/test_scaffold.sh
# A new space is conformant with no dead routes or links, and its indexes are clean.
# When an unstaged file adds a hard failure, the pre-commit hook names that file.
# The topic pipeline scrapes, re-scrapes and reports failures (a fake firecrawl, no network).
set -eu
OKF_HOME=$(cd "$(dirname "$0")/.." && pwd)
export OKF_HOME
tmp=$(mktemp -d "${TMPDIR:-/tmp}/okf-test.XXXXXX")
trap 'rm -rf "$tmp"' EXIT
okf() { uv run -q "$OKF_HOME/scripts/okf.py" "$@"; }
fail() { printf 'FAIL: %s\n' "$*"; exit 1; }

sp="$tmp/space"
"$OKF_HOME/scripts/new_space.sh" "$sp" >/dev/null
out=$(okf check "$sp" --all) || fail "check exited non-zero: $out"
printf '%s\n' "$out"
printf '%s\n' "$out" | grep -qx conformant || fail "space is not conformant"
printf '%s\n' "$out" | grep -qE 'dead-(route|link)' && fail "space has dead routes or links"
okf index "$sp" || fail "index exited non-zero"
okf index --check "$sp" || fail "index --check found changes"
grep -q '^# Sources' "$sp/wiki/index.md" && fail "wiki/index.md kept empty seed headings"
printf '# Draft\n' > "$sp/raw/draft.md"
okf check "$sp" | grep -q 'raw/draft.md: unprocessed' || fail "raw/ is not an inbox"
echo "ok: scaffold"

repo="$tmp/repo"
"$OKF_HOME/scripts/new_space.sh" "$repo" >/dev/null
cd "$repo"
git init -q
git config user.name okf-test
git config user.email okf-test@example.invalid
git config commit.gpgsign false
git config core.hooksPath .git/hooks  # override any global hooksPath
ln -s "$OKF_HOME/hooks/pre-commit" .git/hooks/pre-commit
printf '%s\n' '---' 'type: Concept' 'description: A test note.' '---' '# Note' > "wiki/my note.md"
git add -A
git commit -qm init || fail "first commit was blocked"
[ "$(cat .okf-baseline)" = 0 ] || fail "baseline is not 0"
printf '# Note\n' > "wiki/my note.md"  # unstaged: the frontmatter is gone
printf -- '---\ntitle: no type\n---\n' > old.md  # an old failure, staged
git add old.md && git commit -qm old --no-verify && echo 1 > .okf-baseline && git add .okf-baseline
printf -- '---\ntitle: still no type\n---\n' > old.md
git add old.md
if out=$(git commit -qm rise 2>&1); then fail "hook let a rise through: $out"; fi
printf '%s\n' "$out"
printf '%s\n' "$out" | grep -qF "wiki/my note.md: no-frontmatter" || fail "hook hid the unstaged file behind a staged one"
printf '%s\n' "$out" | grep -qF "git commit --no-verify" || fail "hook dropped the --no-verify hint"
echo "ok: hook"

bin="$tmp/bin" kb="$tmp/kb"
mkdir -p "$bin"
cat > "$bin/firecrawl" <<'EOF'
#!/bin/sh
echo "$*" >> "$FC_LOG"
url=$2; while [ $# -gt 1 ]; do [ "$1" = -o ] && out=$2; shift; done
case "${FC_FAIL:-}$url" in 1*|*bad*) echo "Error: no credits" >&2; exit 1;; esac
printf '{"markdown":"# A\\n\\nBody.","metadata":{"title":"A","sourceURL":"%s","description":"Say \\"hi\\""}}' "$url" > "$out"
EOF
chmod +x "$bin/firecrawl"
FC_LOG="$tmp/fc.log" OKF_KB_ROOT="$kb"
export FC_LOG OKF_KB_ROOT
scrape() { PATH="$bin:$PATH" "$OKF_HOME/scripts/scrape_topic.sh" t; }
"$OKF_HOME/scripts/new_topic.sh" t >/dev/null
src="$kb/topics/t/raw/SOURCES.md"
awk -v row="$(printf 'd\thttps://ex.org/docs\tt')" '/^```$/ { print row } { print }' "$src" > "$tmp/src" && mv "$tmp/src" "$src"
echo 'A note below the block.' >> "$src"
echo https://ex.org/docs/a > "$kb/topics/t/raw/d.urls.txt"
scrape >/dev/null || fail "scrape_topic failed"
grep -qF -- '- [A](docs/a.md) — Say "hi"' "$kb/topics/t/raw/d/CONTENTS.md" || fail "CONTENTS.md kept YAML escapes"
grep -qF '../SOURCES.md' "$kb/topics/t/raw/d/CONTENTS.md" || fail "CONTENTS.md points at a missing file"
n=$(wc -l < "$FC_LOG")
scrape >/dev/null
[ "$(wc -l < "$FC_LOG")" -eq "$n" ] || fail "a plain re-run fetched again"
(OKF_RESCRAPE=1 scrape) >/dev/null  # a subshell: sh keeps VAR=x set after a function call
[ "$(wc -l < "$FC_LOG")" -gt "$n" ] || fail "OKF_RESCRAPE=1 did not fetch again"
(FC_FAIL=1 OKF_RESCRAPE=1 scrape) >/dev/null 2>&1 && fail "a failed re-scrape exited 0"
[ -s "$kb/.firecrawl/raw-t-d/docs__a.json" ] || fail "a failed re-scrape deleted the cached JSON"
printf 'https://ex.org/docs/b\nhttps://ex.org/bad\n' >> "$kb/topics/t/raw/d.urls.txt"
out=$(scrape 2>&1) && fail "a failed URL exited 0"
[ -s "$kb/topics/t/raw/d/docs/b.md" ] || fail "a failed URL stopped the other pages from converting"
printf '%s\n' "$out" | grep -qF 'FAIL  https://ex.org/bad: Error: no credits' || fail "FAIL line hid the error: $out"
out=$(PATH=/usr/bin:/bin bash "$OKF_HOME/scripts/scrape_urls.sh" "$kb/topics/t/raw/d.urls.txt" "$tmp/x" 2>&1) && fail "missing firecrawl exited 0"
printf '%s\n' "$out" | grep -qF 'firecrawl CLI not found' || fail "missing firecrawl gave no clear error: $out"
echo "ok: topic"
