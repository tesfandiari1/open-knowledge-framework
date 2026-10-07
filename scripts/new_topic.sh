#!/usr/bin/env bash
# Scaffold a new topic OKF space under $KB/topics/<slug>.
#   new_topic.sh <topic-slug>
# The knowledge base lives at $OKF_KB_ROOT (default ~/code/knowledge-base) and is
# created on first use: topics/, a .gitignore for the scrape cache, and a copy of
# okf-pack/ so each topic's AGENTS.md can link the format docs relatively.
# Creates: raw/ (+ SOURCES.md template), wiki/ (seeded index.md + log.md),
# and AGENTS.md derived from okf-pack/topic-AGENTS.template.md.
set -euo pipefail

PLUGIN_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
KB="${OKF_KB_ROOT:-$HOME/code/knowledge-base}"
slug="${1:?usage: new_topic.sh <topic-slug>}"
dir="$KB/topics/$slug"
[ -e "$dir" ] && { echo "topic already exists: $dir" >&2; exit 1; }

# Bootstrap the KB root on first use.
mkdir -p "$KB/topics" "$KB/.firecrawl"
if [ ! -f "$KB/.gitignore" ] || ! grep -q '^\.firecrawl/$' "$KB/.gitignore"; then
  echo ".firecrawl/" >> "$KB/.gitignore"
fi
# Seed the shared reference layer so wiki pages and AGENTS.md can link it
# relatively and the KB stays usable outside Claude Code. Never overwritten.
[ -d "$KB/okf-pack" ] || cp -R "$PLUGIN_ROOT/okf-pack" "$KB/okf-pack"
# okf.py config: the pack docs carry no frontmatter by design, so they are meta.
# Setting meta replaces its default list, so the defaults are repeated. Never overwritten.
[ -e "$KB/okf.toml" ] || cat > "$KB/okf.toml" <<'EOF'
meta = ["okf-pack/*",
        "README.md", "*/README.md", "AGENTS.md", "*/AGENTS.md", "CLAUDE.md", "*/CLAUDE.md"]
EOF

mkdir -p "$dir/raw" "$dir/wiki/concepts"
touch "$dir/wiki/concepts/.gitkeep"  # git keeps the folder, so the AGENTS.md route to it stays alive

# AGENTS.md from the plugin's template, so an older seeded okf-pack/ copy cannot add dead routes.
# Its links still point at the KB's okf-pack/ copy.
sed "s/{{TOPIC}}/$slug/g" "$PLUGIN_ROOT/okf-pack/topic-AGENTS.template.md" > "$dir/AGENTS.md"

# raw/SOURCES.md — scrape config (the ```sources block is parsed by scrape_topic.sh)
cat > "$dir/raw/SOURCES.md" <<EOF
# $slug — Sources

What feeds this topic's \`raw/\`. Edit the \`sources\` block below, then run
the okf plugin's \`scrape_topic.sh $slug\` (or ask Claude to refresh the topic).

Each row is one site, TAB-separated. Columns:

| site_slug | map_url | base_tags | extra_flags (optional) |

- **site_slug**   subfolder under \`raw/\` to write into
- **map_url**     URL to \`firecrawl map\` for the sitemap (its origin is used as --base-url)
- **base_tags**   comma-separated tags stamped on every doc
- **extra_flags** verbatim flags passed to firecrawl_to_md.py, e.g.
  \`--strip-path-prefix /docs --strip-title-suffix "\\s*\\|\\s*Foo\\s*$" --skip-404\`

Lines starting with # inside the block are ignored. After \`map\`, hand-edit
\`raw/<site_slug>.urls.txt\` to drop translations / blog / auto-gen dumps before
the scrape continues (scrape_topic.sh pauses for this if the file is new).

\`\`\`sources
# site_slug	map_url	base_tags	extra_flags
EOF

# wiki seed (OKF root: only index.md may carry okf_version)
cat > "$dir/wiki/index.md" <<EOF
---
okf_version: "0.1"
---
# Sources

_No raw sources indexed yet. Run the okf plugin's \`scrape_topic.sh $slug\`, then
regenerate this catalog._

# Concepts

_Synthesized on demand (see AGENTS.md → Wiki mode). Empty by default._
EOF

cat > "$dir/wiki/log.md" <<EOF
# Update Log

## $(date +%Y-%m-%d)
* **Initialization**: Created topic space \`$slug\` (raw/, wiki/, AGENTS.md).
EOF

echo "Created topic: $dir"
echo "Next: edit $dir/raw/SOURCES.md, then run scrape_topic.sh $slug"
