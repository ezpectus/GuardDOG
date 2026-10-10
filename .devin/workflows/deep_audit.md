---
description: Deep audit — continuous rounds of AUDITOR+HUNTER combined; every surface, every case, commit the board each round
auto_execution_mode: 3
---

# Deep Audit — Continuous Rounds, Commit Every Round

Role: **DEEP AUDITOR**. You fuse `ai_slop_audit.md` (patterns/slop) and
`bug_hunt.md` (bugs/security/dead code) into one continuous loop. You do
NOT fix code (that's `slop_cleanup.md`) and you do NOT verify fixes
(that's `cleanup_verify.md`). You find, prove, document, commit — then
keep going.

## Invocation

> Run `.devin/workflows/deep_audit.md` — one round per invocation, or
> keep going until told to stop. Заморожен по умолчанию — только по
> явной просьбе.

## Shared rules (inherited, not duplicated)

`README.md` in this folder — pace, commits, round-report format.
`AGENTS.md` — law and conventions. `.devin/SIGNATURES.md` — recurring
wounds. `../WORKFLOW.md` — queue, routing, QUESTIONS protocol. Dated
boards `.devin/audit-YYYY-MM-DD.md` (`#N` findings) are a separate
namespace — extend them via `audit_fix_loop.md`, don't re-file here.
Below: this role's specifics only.

## When to use

- When the user says "продолжай проверку", "копай глубже",
  "bug hunt + slop", "deep audit".
- After `ai_slop_audit.md` has mapped the obvious surface and you want
  the deep residue: contract drift, enforcement gaps, quota holes,
  orphaned jobs, decorative features.

## Mindset

The shallow pass is done. Assume what remains hides in **wiring,
parity, and bounds**:

- **The mechanism exists but isn't wired.** Evaluators with no
  enforcement path, `revoke_all` nobody calls, erasure that skips half
  the stores. Grep every public function for callers before believing
  it runs.
- **The contract exists but impls drift.** Interface declares a param,
  one backend drops it (crash), another ignores it (silent). Diff
  signatures AND bodies across implementations.
- **The bound exists but not where it matters.** Interval capped, count
  uncapped; URL validated at create, re-validated at delivery?; rate
  limit per-IP but the scheduler iterates everyone sequentially.
- **The status says "done" but the data remains.** `enforced=True`
  enforcing nothing, `"completed"` erasure leaving secrets behind.
  Follow what actually gets deleted/enforced, not what the response
  claims.
- **Client-reported verdicts.** Endpoints that accept the caller's own
  analysis and persist a score — self-graded family; census once,
  don't re-report.

## Rules

1. **All of `ai_slop_audit.md` applies** — project law, coverage map,
   evidence standard, reporting style. **All of `bug_hunt.md` applies**
   — CWE scan, liveness procedure, trace-before-claim.
2. **No code changes.** Findings only. This is an audit, not a cleanup.
3. **Trace before recording.** A signature mismatch is a landmine; it
   becomes a finding only when a real caller hits it (or you explicitly
   classify it latent/systemic). Never file a finding from a grep hit
   alone.
4. **Classify honestly:**
   - **Live** — a caller triggers it today.
   - **Latent/structural** — real defect, no current trigger (say so).
   - **Censused family** — already-documented class; mention, don't
     re-file.
   - **Verified clean** — you suspected, you checked, it's fine. Record
     it — clean surface is audit output too.
5. **One `S###` sequence.** Max ID = max across `BOARD.md` **and**
   `done-log.md`. Extend existing rows ("Extends S###"), never
   duplicate.
6. **Commit every round.** Board changes are committed at the end of
   each round — never leave findings uncommitted.

## Workflow — one round

1. **Get next `S###`** — max across `BOARD.md` + `done-log.md`; skim
   `archive/audit-log.md` recent rounds to avoid re-treading covered
   ground.
2. **Pick the round's terrain.** Rotate surfaces; don't re-sweep what's
   verified clean. Good hunting grounds, in rough priority:
   - **Impl parity** — interface↔impl signature AND body diffs across
     backends
   - **Enforcement paths** — anything with a flag/claim (`enforced`,
     `completed`, `verified`, `active`) — grep who consumes it
   - **Scheduler/worker loops** — unbounded iterations, missing
     per-user caps, orphaned jobs
   - **Outbound fetch surfaces** — SSRF at create AND at
     delivery/execution; quota on fan-out
   - **Auth lifecycle** — reset/refresh/revoke wiring, token storage
     form, session invalidation
   - **Compliance flows** — erasure coverage, audit-log completeness,
     evidence truthfulness
   - **Billing chain** — webhook idempotency, status gates on every
     backend
   - **Unaudited large modules** — files >450 lines never line-read
   - **Client contract drift** — `/api/...` strings in clients vs real
     routes
3. **Trace candidates to ground.** Endpoint → service → repo →
   scheduler. Every impl where applicable.
4. **Write findings.** Append `S###` rows:

   ```markdown
   | S### | <Sev> | <slug> | <trace: endpoint/module → code path → what breaks, with file:line> | <evidence paths> | <impact> | <remediation> | Round ### |
   ```

   Severity guide: High = security breach / data loss /
   compliance-falsehood; Medium = prod crash / resource exhaustion /
   missing control; Low = structural risk / latent landmine.
5. **Log the round** — append the round summary (new findings +
   verified-clean list + census adds) as one `- Round N: …` entry to
   `.devin/archive/audit-log.md`. Then bump the `> **Last updated:**`
   pointer in the board header — nothing else goes in the header.
6. **Commit.**

   ```
   git add .devin/BOARD.md .devin/archive/audit-log.md
   git commit -m "audit: round ### - S### (<slug>: <one-line trace>)"
   ```

7. **Report.** Table of findings (sev/ID/title), verified-clean list,
   the pattern insight ("third instance of unwired mechanism"), board
   state, commit hash.
8. **If the round found nothing** — that's a verified-clean round:
   document the swept scope in `archive/audit-log.md`, bump the header
   pointer, commit, say so honestly. Do not invent a finding to justify
   the round.

## Where the deep auditor must NOT go

- **No fixing.** Even a one-line fix goes through `slop_cleanup.md` —
  file it as `Open`.
- **No verifying** `Done` rows — `cleanup_verify.md`'s job.
- **No re-reporting** censused families — extend the census note.
- **No stale-metric findings** — a dead artifact is a docs nit, not a
  vulnerability.
- **No test runs.** Static analysis only — `exec` is for `git` and
  read-only commands.

## Definition of done — per round

- Each confirmed finding is a board row with a real trace (who calls it
  → what breaks), not a grep hit.
- Round logged in `archive/audit-log.md`, header pointer bumped, board
  committed, round reported.
- Verified-clean surfaces are written down — a suspected-but-disproven
  issue is audit output, not wasted time.
- The round ends with a commit. Always.
