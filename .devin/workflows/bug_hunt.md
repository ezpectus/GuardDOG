---
description: Bug hunt — deep-read code for real bugs, security holes, dead code and obviously unnecessary junk; document or remove safely
auto_execution_mode: 3
---

# Bug Hunt — Find What's Actually Broken

Role: **HUNTER**. `ai_slop_audit.md` hunts *patterns*; you hunt
*consequences* — logic errors, security holes, dead code, and stuff that
plainly shouldn't exist. Findings go on `.devin/BOARD.md` as `S###`
rows with severity tags.

## Invocation

> Run `.devin/workflows/bug_hunt.md` on <directory/file> — no scope
> means work the hunt order below. Заморожен по умолчанию — только по
> явной просьбе (см. `../WORKFLOW.md` Шаг 2).

## Shared rules (inherited, not duplicated)

`README.md` in this folder — pace, commits, round-report format.
`AGENTS.md` (repo root) — law and conventions. `.devin/SIGNATURES.md` —
recurring wound catalog. `../WORKFLOW.md` — queue, routing, gates.
Below: this role's specifics only.

## What you're looking for

### Bugs (severity: BUG)

- `None`/null dereference: optional returns used without a guard
- Wrong async: `await` forgotten, coroutine/promise returned instead of
  result, blocking calls inside `async def`, deprecated loop APIs
- Race conditions: check-then-act on shared state, unguarded
  module-level caches, wrong lock primitive for the execution model
- Logic errors: off-by-one, inverted conditions, wrong comparison
  operator, copy-paste blocks where one branch wasn't updated
- Resource leaks: files/connections/sessions opened without close,
  unbounded caches, tasks created and never awaited/cancelled
- Error swallowing with data loss: `except` that drops a
  record/payment/webhook silently
- Missing tenant/owner scoping on a data access — cross-tenant leak
  (historically a real bug class — check `SIGNATURES.md` post-filter)
- Mutable shared state: default args, class attrs mutated per-instance

### Security (severity: SEC)

CWE quick-scan:

| Pattern | CWE | Grep | Why it's dangerous |
|---------|-----|------|--------------------|
| SQL injection | CWE-89 | `f"(SELECT\|INSERT\|UPDATE\|DELETE)` / string-concat queries | `' OR 1=1 --` reads everything |
| Hardcoded secrets | CWE-798 | `(password\|secret\|api_key)\s*=\s*['"]` | Key in git = leak |
| Weak crypto | CWE-327 | `md5\|sha1\|DES\|ECB` | Broken/visible patterns |
| Path traversal | CWE-22 | `open(.*\+`, missing `is_relative_to`/resolve-check | `../../etc/passwd` |
| SSRF | CWE-918 | fetch of user-supplied URL w/o validation | `169.254.169.254` metadata |
| XSS | CWE-79 | `innerHTML`, `dangerouslySetInnerHTML`, `\|safe` | Session theft |
| No auth check | CWE-306 | handler/route without auth dependency | Anyone calls it |
| Mass assignment | CWE-915 | `Model(**body)` / `setattr` loops over request dict | `{"is_admin": true}` |
| Race condition | CWE-362 | check-then-act w/o transaction/lock | Duplicate/conflict |
| Info disclosure | CWE-200 | `{"error": str(e)}` / raw traceback in response | Internals leak |
| No rate limit | CWE-770 | Auth endpoint without throttle | Brute force |
| Insecure deserialization | CWE-502 | `pickle.loads`, `yaml.load` w/o SafeLoader, `eval` on input | RCE |

Plus: `verify=False`, CORS `*`, `shell=True`, `eval`/`exec`, middleware
order that skips the check, missing tenant scope on data access.

### Dead code (severity: DEAD)

Liveness check procedure — a symbol is dead only if ALL fail:

1. grep the name project-wide — only definition + tests hit
2. grep the route/path in every client surface — nothing calls it
3. grep in templates/static/docs — nothing references it
4. check `__all__`, `importlib`/`getattr`/dynamic dispatch uses — none

Dead shapes: functions, files, endpoints, models, repos never injected,
CLI commands, IPC channels, unused deps, unreachable code after
`return`, commented-out blocks. **Careful:** «мёртвый» метод может быть
живым путём (compliance/erasure/admin) — grep'ай вызовы, не только имя.

### Junk (severity: JUNK)

- Files that shouldn't exist: shim/re-export dumps, `_missing_models`-
  style stub files, backup/`_old`/`_v2` copies, committed scratch
- Placeholder features presented as real (fake-features table in
  `ai_slop_audit.md`)
- Duplicate implementations of the same thing in two places

## How to work

1. **Pick a file, read it fully.** Not pattern-grep — read. Large
   files in ~200-line chunks. Order suggestion: services → handlers/
   routes → data layer → infra → client critical paths (auth, billing,
   execution).
2. **Trace the suspicious thing.** A bug claim needs the full path:
   who calls it, what data flows in, what the wrong outcome is.
   "Looks wrong" without a trace isn't a finding.
3. **Classify severity:** `BUG` / `SEC` / `DEAD` / `JUNK` + a real
   priority (P0 = security/data loss, P1 = wrong behavior, P2 = dead
   weight, P3 = smell).
4. **Dedupe against the board AND `done-log.md`** — closed findings
   live in done-log; extend existing `S###` when it's the same thing.

## What you may fix inline

- **Yes:** removing a dead *private* symbol with zero references; a
  one-line obvious bug fix (inverted condition, missing `await`) —
  commit it, note the board row.
- **Ask first:** deleting whole files, deleting endpoints, deleting
  tests, changing public signatures, anything touching
  auth/billing/crypto, anything >50 lines → `Q-NNN` entry in
  `.devin/QUESTIONS.md` and wait for `**Ответ:**` — do not guess.
- **No:** refactors, renames, "while I'm here" improvements. Hunt,
  don't redecorate.

## Output

```markdown
| **S###** | [BUG\|SEC\|DEAD\|JUNK] <title> | `<file>:<line>` — what's wrong, the trace (who calls it → what breaks), proposed action | P# | [ ] Open |
```

Removed dead code gets logged in the commit body. Proposed deletions
get board rows and wait for the user.

Commit format: `fix:` for bugs, `refactor:` for dead-code removal,
`docs:` for board-only updates. Report at the end: counts by severity,
the worst thing you found, what you removed, what needs user decision.
