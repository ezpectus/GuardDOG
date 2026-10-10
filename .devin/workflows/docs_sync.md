---
description: Docs sync — verify every doc against the code, update stale numbers/claims, prune or merge excess documentation
auto_execution_mode: 3
---

# Docs Sync — Make the Docs Tell the Truth

Role: **LIBRARIAN**. Docs lie — stale counts, features that are stubs,
files describing deleted directories, near-duplicates rotting in
parallel. You verify docs against code, update what's stale, and cut
what's excess. The doc set should be minimal and accurate, not a
landfill.

## Invocation

> Run `.devin/workflows/docs_sync.md` — optionally scoped to `docs/`,
> root `*.md`, or `.devin/`.

## Shared rules (inherited, not duplicated)

`README.md` in this folder — pace, commits, round-report format.
`AGENTS.md` (repo root) — law and conventions. `../WORKFLOW.md` —
queue, routing, QUESTIONS protocol. Below: this role's specifics only.

## Step 0 — Build the doc inventory

List every doc-bearing location in THIS repo: root `*.md`, `docs/`,
per-package READMEs, nav configs (mkdocs/docusaurus/etc.), generated
artifacts (openapi.json, coverage dumps), `.devin/` state files.
`.devin/` board/logs are state, not docs — never rewrite their history
tables.

## Step 1 — Recount, don't copy

Every number in a doc is a claim. Verify the load-bearing ones:
endpoints, tests, files, commands, coverage. Check each count against
its actual definition before editing — a decorator grep, a runtime
registry count, and a collected-test count are three different numbers.
Static-only passes mark runtime/collected counts unverified rather
than copying them. Record old→new value and date.

## Step 2 — Verify claims

- Feature lists: for each claimed feature, confirm a real
  implementation exists (not a stub — fake-features table in
  `ai_slop_audit.md`). Stub → mark `[stub]` or cut the claim.
- Docs describing deleted things — cut the section or the file.
- Internal links and nav config: every target must exist.
- Version mentions vs manifests; runtime version vs actual requirement.
- `S###`/`#N` ranges referenced in docs vs the board's real max.
- Duplicated trackers (`docs/` vs `.devin/` vs other) — if duplicated,
  one wins; make the other a pointer or merge and delete.

## Step 3 — Prune the excess

Flag for deletion or merge:

- **Empty stubs** — a doc that says "TODO" or restates its title.
- **Orphans** — not in nav, not linked from any other doc or README.
- **Duplicates** — two files covering the same topic; merge into one.
- **Aspirational docs** — specs for features that don't exist and
  aren't planned.
- **Generated artifacts committed as docs** — stale exports, coverage
  dumps.

Deletion rule: delete only if clearly obsolete AND unreferenced (grep
the filename across the repo, nav configs, and CI). Anything ambiguous
→ list it in your report as a proposed deletion, don't delete.

## Step 4 — Update

- Fix stale numbers, ranges, feature claims, dead links — small edits,
  not rewrites.
- Update audit-round pointers wherever they appear **only when a new
  audit round actually ran** — don't bump numbers cosmetically.
- Write like the existing docs: terse, factual, no marketing
  adjectives. If a doc says "enterprise-grade" and the code says
  "demo" — the doc loses.

## Step 5 — Commit and report

```
docs: sync documentation with code (<n> files updated, <n> pruned)

- Recounted endpoints/tests, updated README + features doc
- Removed docs/x.md (orphaned, describes deleted surface)
- Merged a.md → b.md
```

Under 1,000 changed lines per commit. Report: what was verified, what
was wrong, what you deleted, what you propose deleting but didn't.

## Hard rules

- **Docs describe the code — never the other way.** If a doc and the
  code disagree, the doc is wrong (or the code is a bug →
  `bug_hunt.md` finding, file it, don't paper over it).
- **No new doc files** unless the user asked — the problem is too many
  docs, not too few.
- **`.devin/` files are state, not docs** — update stale header lines,
  never rewrite history tables.
- **Don't invent content.** If you can't verify a claim either way,
  mark it `<!-- unverified -->` and list it in the report.
