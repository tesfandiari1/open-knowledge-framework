# OKF Concept Authoring — on-demand craft

> Companion to [`okf-rulebook.md`](okf-rulebook.md). The **rulebook** defines the
> FORMAT (frontmatter, body, links, citations, conformance, template — §3–§11).
> This file holds the JUDGMENT for writing one good concept on demand: choosing
> `type`, a pre-file self-check, and recording gaps and conflicts honestly.
> Vendor-neutral plain Markdown. Used whenever an operator files a concept back
> (e.g. the `okf` skill's "file back" step) or synthesizes a `wiki/` page — there is
> no batch pipeline; synthesis is one concept at a time.

## Choosing `type`

`type` is the only required field (rulebook §3/§7). Pick it by asking *"what kind of
thing is this?"*:

| The source is… | `type` |
|---|---|
| a person, org, or place | `Entity` |
| an idea, term, or method | `Concept` |
| a broad subject area / overview | `Topic` |
| the source document itself, mirrored as a page | `Source` |
| a how-to / procedure | `Playbook` |
| a measured quantity | `Metric` |
| a structured asset (table, dataset, API) | `Dataset` / `API Endpoint` / `Reference` |
| an external doc you're pointing at | `Reference` |
| a side-by-side of options | `Comparison` |
| genuinely unsure | a broad honest value (`Concept`, `Reference`, `Source`) — never blank, never an invented precise taxonomy |

## Pre-file self-check

**Conformance is the only hard gate** (rulebook §7): parseable frontmatter +
non-empty `type`. Everything else is soft — improve it and file anyway; a thin
honest page beats a padded one. Never discard a page for a soft miss (rulebook §2).

Quick quality bar (aim for, don't gate on):
- `type` set; `description` is one stand-alone sentence (it surfaces in `index.md`).
- Body favors structure (headings/lists/tables) over an undifferentiated prose dump.
- Real relationships are linked bundle-relative, with the relationship stated in the
  prose — not buried in link text (rulebook §5).
- Externally-sourced claims — and only those — carry a `# Citations` entry. Never
  invent a citation, date, `resource` URI, or relationship to look complete.

## Enrich, don't invent — gaps & conflicts

When a fact would improve a page but no source supports it, **do not write the
fact** — record a gap inline where it belongs:

```
> _Gap: <what's missing and what source could fill it>._
```

When a new page contradicts an existing one, **never silently overwrite**. Note it
on both pages and surface it for a human to adjudicate:

```
> _Conflict: this page says X; [other](/path.md) says Y (as of <date>)._
```

Everything else — frontmatter fields, body headings, link syntax, the citation
format, the copy-paste template — lives in `okf-rulebook.md` (§3, §4, §5, §8, §11).
Don't restate it here.
