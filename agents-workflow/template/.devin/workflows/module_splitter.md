---
description: Module splitter — cut god files (>500 lines) and long functions (>50 lines) into domain-cohesive pieces without breaking imports
auto_execution_mode: 3
---

# Module Splitter — Cut the Fat

Role: **SPLITTER**. You find oversized files and functions and split
them along domain boundaries. Behavior must not change — this is pure
reorganization.

## Invocation

> Run `.devin/workflows/module_splitter.md` on <dir/file>.

## Shared rules (inherited, not duplicated)

`README.md` in this folder — pace, commits, round-report format.
`AGENTS.md` (repo root) — law and conventions. `../WORKFLOW.md` —
queue, routing, gates. Below: this role's specifics only.

## Limits (project law defaults — калибруются при adoption)

| Thing | Limit | Action when over |
|-------|-------|------------------|
| File | 500 lines | Split into domain modules |
| Function | 50 lines | Extract helpers/stages |
| Function params | 5 | Introduce a params object |
| Commit | 1,000 changed lines | Sequential commits |

## Step 1 — Find candidates

Count lines per file in the source dirs (read-only `wc -l`/`find`),
sort desc, take the head. For functions, list `def`/`function`/`fn`
positions inside a fat file and eyeball the gaps — a >limit gap is a
suspect. Read it to confirm.

Prioritize:

1. God files in the flat/root dump (same-domain siblings like
   `x.py` + `x_service.py` should merge or split coherently, not
   sprawl)
2. Handler/router files >500 lines — usually several domains crammed
   into one
3. Data-layer/repo mega-files
4. CLI/command files >500 lines
5. Test files >800 lines — split only if discovery stays intact
   (`test_*`/`*.test.*` naming)

## Step 2 — Choose the cut

**By domain.** `admin.*` containing users + licensing + audit →
`admin_users.*`, `admin_licensing.*`, `admin_audit.*`. Not
`admin_part1.*`, `admin_part2.*`.

**By layer.** File mixing validation + business logic + data calls →
keep transport handling in the handler, move logic to a service,
queries to the data layer.

**By cohesion.** Functions that share private helpers and data stay
together; functions that only share the file get separated.

**For long functions:** extract stages — validate → load → compute →
persist → respond. Each stage becomes a named private function. If a
function needs too many params, first group them into a params object,
*then* split.

## Step 3 — Execute without breaking anything

1. Read the whole file. List its public symbols (everything imported
   elsewhere — grep the symbol names).
2. Create the new module(s). Move code verbatim — **do not "improve"
   while moving.** If you spot slop mid-move, note it, don't fix it
   here.
3. Update imports in every consumer. Grep each moved symbol.
4. Keep backward-compat re-exports in the original file **only** if an
   external surface depends on it (documented imports, dynamic usage).
   Otherwise update consumers properly.
5. Watch for circular imports — if the new module needs something
   from its old home, the cut is probably wrong; type-only/lazy import
   only as a last resort.
6. Syntax-parse each touched file if exec is permitted — otherwise
   re-read the imports block carefully.

## Step 4 — Document

Splits are routine refactors, not slop findings — log them in the
commit body:

```
refactor: split app/admin.py (2,140 lines) into 3 modules

- admin_users.py — user management endpoints (640 lines)
- admin_licensing.py — license key endpoints (510 lines)
- admin_audit.py — audit log endpoints (290 lines)
- admin.py keeps shared helpers + re-exports (700 lines)
```

If a split *reveals* slop (dead functions nobody imports, a fake
service), file it as an `S###` row on BOARD — that's
`ai_slop_audit.md` territory, but you're the one who found it, so
write it up.

## Hard rules

- **Project law applies** (bans table in `ai_slop_audit.md`). Moved
  code must not gain banned patterns.
- **Zero behavior change.** Same endpoints, same signatures, same
  return shapes, same side effects.
- **No rename sprees.** Move symbols under their existing names.
  Renames are a separate, discussed change.
- **Don't split what's cohesive.** A 600-line file of one tight
  domain beats four 150-line files that import each other constantly.
- **Tests:** split only across test-file boundaries; never inside a
  class mid-file; fixtures must still resolve.
- **If a file is big because it's a generated/stub dump**, don't split
  it — flag it on the board as a finding instead.
