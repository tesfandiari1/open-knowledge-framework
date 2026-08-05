---
name: lint
description: |
  Health-check an OKF knowledge-base topic and report work to do. Use when the user wants to audit, validate, or find gaps in a topic, e.g. "lint my tauri wiki", "what's missing in the premiere-pro docs", "check the knowledge base for orphans or stale pages", "is this topic OKF-conformant". Reports issues grouped by severity and applies only mechanical fixes (index/log regeneration), leaving content judgment to the user.
allowed-tools:
  - Bash
  - Read
  - Write
  - Edit
---

# okf:lint — audit a topic

Run the OKF **Lint** operation over one topic: check conformance, surface orphans /
stale / missing pages / index drift, apply the mechanical fixes, and hand the user a
prioritized to-do list. Never silently overwrite content judgments.

## Critical context

- **KB root:** `KB="${OKF_KB_ROOT:-$HOME/code/knowledge-base}"`. If missing, ask.
- **Conformance applies to `wiki/` only.** `raw/` holds sources that keep their
  firecrawl frontmatter (no `type:`) — do NOT flag raw pages for missing `type`.
- **Permissive posture** (rulebook §2): broken cross-links, missing optional fields,
  and absent `index.md` are NOT failures — they're signals. The only hard failures
  are §7: unparseable frontmatter, empty `type:`, malformed reserved files.
- Apply mechanical fixes (regenerate indexes/logs). Leave contradictions, stale
  judgments, and content gaps for the user.

## Checks

Scope everything to `topics/<slug>/`.

### 1. Conformance (wiki/ concept pages) — HIGH
Every non-reserved `.md` under `wiki/` must have a parseable YAML frontmatter block
with a non-empty `type:`. The check below uses PyYAML for a full parse when it's
available, and otherwise applies a **dependency-free strict validator** that catches
the real failure modes — the unquoted `: ` (and ` #`) that silently breaks a block,
unbalanced quotes — not just a `grep` for `type:`. So it runs anywhere, PyYAML or not:
```bash
KB="${OKF_KB_ROOT:-$HOME/code/knowledge-base}"; slug=<topic>
find "$KB/topics/$slug/wiki" -name '*.md' ! -name index.md ! -name log.md \
  -print0 | while IFS= read -r -d '' f; do
    python3 - "$f" <<'PY'
import sys, re
f = sys.argv[1]; t = open(f).read()
if not t.startswith("---\n"): print(f"NO-FRONTMATTER\t{f}"); raise SystemExit
parts = t.split("---\n", 2)
if len(parts) < 3: print(f"UNTERMINATED-FRONTMATTER\t{f}"); raise SystemExit
fm = parts[1]

def stdlib_conformant(fm):
    """Dependency-free strict-ish check: catches the unquoted ': ' / ' #' and
    bad-quote traps the weak `grep type:` misses, plus non-empty type — the real
    C1/C2 failure modes from rulebook §7, no PyYAML required."""
    has_type = False
    for ln in fm.splitlines():
        if not ln.strip() or ln.lstrip().startswith("#"): continue
        if re.match(r"^\s+\S", ln) or re.match(r"^\s*-\s", ln): continue   # nested / list item
        m = re.match(r"^(\w[\w-]*):(?:\s+(.*))?$", ln)
        if not m: return False                            # unparseable top-level line
        key, val = m.group(1), (m.group(2) or "").strip()
        if key == "type" and val.strip("\"'"): has_type = True
        if not val: continue
        if val[0] in "\"'":                               # quoted scalar
            q = val[0]
            if not (val.endswith(q) and len(val) >= 2): return False
            if q == '"' and re.search(r'(?<!\\)"', val[1:-1]): return False
        elif val[0] == "[": continue                      # flow list
        else:                                             # bare scalar: the YAML traps
            if ": " in val or " #" in val: return False
            if val[0] in "#@`[]{},&*!|>%?:" or val.startswith("- "): return False
    return has_type

try:
    import yaml                                   # full YAML parse if PyYAML present
    d = yaml.safe_load(fm)
    ok = isinstance(d, dict) and str(d.get("type", "")).strip()
except ModuleNotFoundError:
    ok = stdlib_conformant(fm)                    # dependency-free strict-ish fallback
if not ok: print(f"NON-CONFORMANT\t{f}")
PY
  done
```
The exact conformance rules this implements are `$KB/okf-pack/okf-rulebook.md` §7
(parseable frontmatter, non-empty `type`, well-formed reserved files). PyYAML adds
full YAML semantics but is **not required** — the stdlib validator covers the
documented C1/C2 traps on its own.

### 2. Reserved files — MEDIUM
`wiki/index.md` may carry only `okf_version`; every other `index.md` has no
frontmatter. `log.md` uses `## YYYY-MM-DD` headings, newest first, bold action words.

### 3. Orphans — LOW
Wiki concept pages with no inbound link from any other wiki page. List them; an
orphan usually wants a link from `index.md` or a related concept.

### 4. Missing pages — LOW
Bundle-relative links (`/...md`) that point to a non-existent file. These are legal
forward references — **list, never delete**. They flag pages worth writing.

### 5. Stale sources — LOW
`raw/` pages whose `scraped_date` is more than ~90 days before today. Report the oldest
per site and suggest `okf:refresh` for any site past that age.

### 6. Index drift — MEDIUM (mechanical fix)
`CONTENTS.md` / `wiki/index.md` out of sync with files on disk. Fix by regenerating:
```bash
for d in "$KB/topics/$slug/raw"/*/; do
  python3 "$KB/scripts/gen_index.py" "$d" "$(basename "$d")"
done
```
Then reconcile `wiki/index.md`'s `# Sources` links against the sites present.

## Output

A report grouped by severity (HIGH → LOW) with file paths, then a short to-do list
("3 fixes applied automatically; 2 items need your call"). Append a `**Lint**` entry
to `wiki/log.md` summarizing what was checked and fixed. Defer all format rules to
`$KB/okf-pack/okf-rulebook.md`.

## Troubleshooting

- **Everything flagged MISSING-TYPE** — you scoped `raw/` by mistake; lint `wiki/` only.
- **`yaml` import error / PyYAML missing** — fine; the check's stdlib validator runs
  automatically and already catches the unquoted-`: `/` #` and bad-quote traps. PyYAML
  only adds full YAML semantics for exotic edge cases; it is not required.
- **Huge orphan list on a fresh topic** — expected; a light-wiki topic starts with
  only `index.md`/`log.md` and no concepts. Not a problem.
