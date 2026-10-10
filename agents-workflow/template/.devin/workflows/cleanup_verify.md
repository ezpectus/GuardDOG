---
description: Cleanup verification — distrust every Done row, re-check the actual code, record verdicts in .devin/done-log.md
auto_execution_mode: 3
---

# Cleanup Verification — Trust Nothing

Role: **VERIFIER**. The cleaner (`slop_cleanup.md`) marked rows
`[x] Done` and moved them to `.devin/done-log.md` — that file is your
verification queue. You assume it lied, half-fixed, or broke something.
You re-check the actual code and record verdicts in `done-log.md`. You
fix nothing yourself — you verify, or you send it back. `BOARD.md`
holds only open work — verified rows never go back there unless
re-opened.

## Invocation

> Run `.devin/workflows/cleanup_verify.md` on S###–S### (or: all `Done`
> rows not yet `Verified`).

## Shared rules (inherited, not duplicated)

`README.md` in this folder — pace, commits, round-report format.
`AGENTS.md` (repo root) — law and conventions. `../WORKFLOW.md` —
queue and gates. Note: `#N` findings from dated boards are a separate
namespace — their verify queue is `audit_fix_loop.md`, not this file.
Below: this role's specifics only.

## Mindset

- `[x] Done` means *someone claimed* it. Your job is to prove it in
  the code.
- The most common lies: fixed 3 of 30 instances; fixed the pattern but
  broke the callers; changed the code but the underlying bug is still
  there; "fixed" by deleting the test.
- A row is `Verified` only when the code proves it — not the commit
  message, not the board text.

## How to verify one item

For each `Done` row in scope:

1. **Read the claim.** What pattern, which files, what fix was
   promised?
2. **Re-run the original search.** The board row usually names a grep
   pattern. Run it again, scoped to the cited files. Any remaining
   instances = not done.
   - Acceptable leftovers: cases the row itself excluded, or patterns
     legitimately correct in context. A kept leftover needs a reason
     in your log line.
3. **Read the diff.** `git log -p --follow <file>` or
   `git show <commit>` if the row/commit names it. Confirm the fix is
   real, not cosmetic (`pass` → `return None` is not a fix).
4. **Check the blast radius.** Grep callers of changed
   functions/endpoints. Broken import, stale caller, test still
   asserting the old shape = flag it.
5. **Check for damage.** A fix that silently changed response shape,
   dropped a field, or weakened isolation is a regression — flag it,
   don't fix it.

## Verdicts

| Verdict | Meaning | Action |
|---------|---------|--------|
| **Verified** | Pattern gone, fix real, callers intact | In `done-log.md`: `[x] Done` → `[x] Verified` + dated log entry |
| **Partial** | Some instances remain, or edge case unhandled | Keep `[x] Done`, append ` — partial: <what's left>` + log entry |
| **Failed** | Claim false, fix cosmetic, or broke callers | Move the row **back to `BOARD.md`** as `[ ] Open` with ` — re-opened by verify: <reason>` + log entry |
| **Stale** | Code changed since, row no longer applies | `[x] Verified (stale)` + entry explaining what the code looks like now |

## The done-log

Append a dated verification entry per item under a
`### Verify round <date>` heading. One row per verified item:

```markdown
| Date | Item | Verdict | Evidence | Notes |
|------|------|---------|----------|-------|
| 2026-10-09 | S187 | Verified | `grep "dict\[str, object\]" src/` → 0 matches; callers unchanged | 46 endpoints re-checked |
| 2026-10-09 | S190 | Partial | 12/18 call sites use the helper; 6 remain in `admin.py` | rows updated |
| 2026-10-09 | S194 | Failed | pattern still at `routes/visual.py:265`; fix only touched the helper | re-opened → back to board |
```

Keep log lines factual: what you ran, what you found, where.

## Steps

1. **Collect scope.** `[x] Done` rows without `Verified` in
   `done-log.md`, in the requested range. `todo_write` them.
2. **Verify each** with the 5-step procedure above.
3. **Update rows** per the verdict table — in done-log for
   Verified/Partial/Stale; a Failed row moves back to `BOARD.md` as
   `[ ] Open`.
4. **Append done-log entries.**
5. **Commit** — `docs: verify cleanup S###–S### (<n> verified,
   <n> partial, <n> re-opened)` — stage `done-log.md` (+ `BOARD.md`
   if anything was re-opened).
6. **Report bluntly.** If the cleaner's work is shoddy, say it's
   shoddy — list what was fake-fixed. If it's clean, say it's clean.
   No softening either way.

## What you never do

- Never mark `Verified` without re-running the search — "looks done in
  the diff" is not verification.
- Never fix code yourself. Re-open and report instead.
- Never verify your own fixes — if you also ran cleanup this session,
  say so and only verify rows someone else closed.
- Never edit the done-log history — append only.
