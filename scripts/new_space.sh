#!/usr/bin/env bash
# Stand up a private-knowledge OKF space (okf-pack/okf-space.md §1–2).
#   new_space.sh <dir>
# Creates <dir> with the three-layer layout: raw/ (your immutable sources),
# wiki/ (the LLM-owned OKF bundle, seeded), and the schema layer — AGENTS.md
# (the operating spec) plus the rulebook and authoring craft it defers to.
# The result is self-contained and vendor-neutral: any agent that reads
# AGENTS.md can run Ingest / Query / Lint over it.
set -euo pipefail

PLUGIN_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
dir="${1:?usage: new_space.sh <dir>}"
[ -e "$dir" ] && { echo "already exists: $dir" >&2; exit 1; }

mkdir -p "$dir/raw/assets" "$dir/wiki"
touch "$dir/raw/assets/.gitkeep"  # git keeps raw/ and raw/assets/, so AGENTS.md routes to them stay alive

# Schema layer: okf-space.md says "save this file at the root of your space as
# AGENTS.md", alongside the format rulebook and concept-authoring craft.
cp "$PLUGIN_ROOT/okf-pack/okf-space.md" "$dir/AGENTS.md"
cp "$PLUGIN_ROOT/okf-pack/okf-rulebook.md" "$dir/okf-rulebook.md"
cp "$PLUGIN_ROOT/okf-pack/concept-authoring.md" "$dir/concept-authoring.md"

# okf.py config. raw/ is the inbox, so check lists each raw file no note links to yet.
# The bundle is wiki/, so index writes no index.md at the space root.
# The schema docs carry no frontmatter by design, so they are meta. Setting meta
# replaces its default list, so the defaults are repeated here.
cat > "$dir/okf.toml" <<'EOF'
exclude = ["index.md"]
inbox = ["raw/*"]
meta = ["okf-rulebook.md", "concept-authoring.md",
        "README.md", "*/README.md", "AGENTS.md", "*/AGENTS.md", "CLAUDE.md", "*/CLAUDE.md"]
EOF

# Wiki seed (only the root index.md may carry okf_version)
cat > "$dir/wiki/index.md" <<'EOF'
---
okf_version: "0.1"
---
# Sources

# Entities

# Concepts
EOF

cat > "$dir/wiki/log.md" <<EOF
# Update Log

## $(date +%Y-%m-%d)
* **Creation**: Stood up this OKF space (raw/, wiki/, schema layer).
EOF

echo "Created OKF space: $dir"
echo "Next:"
echo "  1. cd $dir && git init   (recommended — the wiki is just Markdown)"
echo "  2. Record your conventions in AGENTS.md §3 (taxonomy, type vocabulary, tags)"
echo "  3. Drop your first source into raw/ and ask your agent to Ingest it (AGENTS.md §4.1)"
