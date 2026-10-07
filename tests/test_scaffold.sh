#!/bin/sh
# Scaffold and hook test: sh tests/test_scaffold.sh
# A new space is conformant with no dead routes or links, and its indexes are clean.
# When an unstaged file adds a hard failure, the pre-commit hook names that file.
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
