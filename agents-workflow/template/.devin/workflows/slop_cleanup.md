---
description: Slop cleanup — fix Open S### items on BOARD with minimal diffs, mark Done, commit per batch
auto_execution_mode: 3
---

# Slop Cleanup — Fix the Board

Role: **CLEANER**. You take `[ ] Open` items on `.devin/BOARD.md` and
fix them. You do NOT re-audit (that's `ai_slop_audit.md`) and you do
NOT verify your own work (that's `cleanup_verify.md`).

## Invocation

> Run `.devin/workflows/slop_cleanup.md` on items S###–S### (or: all
> Open items / all Open items in a named scope).

## Shared rules (inherited, not duplicated)

`README.md` in this folder — pace, commits, round-report format.
`AGENTS.md` (repo root) — law and conventions. `../WORKFLOW.md` —
queue, routing, gates, QUESTIONS protocol. Note: `#N` findings on
dated boards (`.devin/audit-*.md`) are a separate namespace — that's
`audit_fix_loop.md`'s board (`S###` only here). Below: specifics.

## Rules — read before touching code

**Project law applies** (table in `ai_slop_audit.md` → "Project law" as
calibrated for this stack). A fix that introduces a banned pattern is
not a fix.

1. **Minimal diffs.** Fix the flagged lines. Do not refactor the file
   around them.
2. **Never break the API.** Keep endpoint paths, response shapes,
   function signatures, and exported names stable.
3. **Never delete tests.** A test can only be edited if the test
   itself contains the bug — and say why.
4. **No new dependencies** without asking the user.
5. **No new features, no new files** unless the fix requires a helper —
   prefer existing helper/convention modules.
6. **Don't batch unrelated fixes.** One commit per S### or per
   coherent group of instances of one S###.
7. **Commit ceiling: 1,000 changed lines.** Split bigger fixes into
   sequential commits.
8. **If a board item is wrong** — the "slop" is actually legitimate
   code — don't force a fix. Mark it `[x] Done`, append
   `— not slop: <reason>`, and move it to `done-log.md` like any
   other closed row.

## Workflow

1. **Read the board.** Open `.devin/BOARD.md`, collect `[ ] Open`
   rows in the requested scope. `todo_write` them.
2. **Reproduce mentally.** For each item, open the file at the cited
   line. Confirm the pattern still exists — the board may be stale.
   If the code moved, find where it lives now.
3. **Fix.** Apply the "what to use instead" from the row. Standard
   fixes (Python/TS-примеры — калибруй под стек):

   | Slop | Fix |
   |------|-----|
   | `except Exception: pass` | Specific exceptions + `logger.error(...)` |
   | `except Exception: return None` | Specific exceptions + log, or let it propagate |
   | untyped/`dict` endpoint return | typed response model |
   | `random.` as metric/score | real computation, or mark deprecated |
   | `range(len(x))` | `enumerate(x)` / direct iteration |
   | `len(x) > 0` / `== 0` | `if x:` / `if not x:` |
   | `setattr(model, f, v)` | validated copy/`model_copy(update=…)` |
   | `str(p).startswith(str(base))` | `is_relative_to`/equivalent |
   | `sorted(k=-x.n)` | `sorted(key=x.n, reverse=True)` |
   | `async def` no `await` | drop `async` or make the body actually async |
   | sync HTTP in `async def` | async client |
   | `datetime.now()` | `datetime.now(timezone.utc)` |
   | mutable default arg | `None` default + guard |
   | `or ""`/`or []`/`or {}` masking `None` | fix the model/default |
   | star import | explicit names |
   | module-level mutable dict | injected store/shared-state helper (project pattern) |

4. **Check the blast radius.** Grep callers of what you changed.
   Changed a return type → update callers. Test asserted the old slop
   shape → fix the test only if it was asserting the bug.
5. **Close the row.** Mark `[ ] Open` → `[x] Done` and **move the row
   to `.devin/done-log.md`** (verifier's queue). Do not touch other
   rows. If the fix leaves a residual (partial coverage, deferred
   legs), record it in the board's residual/session-state block.
6. **Commit.**

   ```
   git add <files> .devin/BOARD.md .devin/done-log.md
   git commit -m "refactor: fix S### <title> (<n> instances)"
   ```

   `fix:` for behavior corrections, `refactor:` for pure cleanup,
   `test:` for test-only changes.
7. **Report.** What was fixed, what was skipped and why, what couldn't
   be fixed without a bigger decision — put that back to the user,
   don't silently drop it.

## Where the cleaner must NOT go

- **No drive-by edits.** You see slop that isn't on the board? Note it
  in your report — don't fix it in this pass (it needs an `S###` first).
- **No verification theater.** You mark `Done`; `cleanup_verify.md`
  marks `Verified`. Never mark `Verified` yourself.
- **No mass rewriting.** An item needing >1,000 lines gets split into
  phases — say so.

## Definition of done

- Every in-scope `Open` row is either `Done` with a commit, or left
  `Open` with a reason reported to the user.
- Board updated, commits made, working tree clean.
