---
description: Full check — sweep every project surface for breakage, inconsistency, dead references and drift between code, config and docs
auto_execution_mode: 3
---

# Full Check — The Whole-Project Sweep

Role: **INSPECTOR**. Not a deep audit (`ai_slop_audit.md`) and not a
bug hunt (`bug_hunt.md`) — a breadth-first pass over **everything** to
catch what's broken, stale, or drifting. Findings go on
`.devin/BOARD.md` as `S###` rows. You fix nothing.

## Invocation

> Run `.devin/workflows/full_check.md` — no scope argument means all
> surfaces below. Заморожен по умолчанию — только по явной просьбе.

## Shared rules (inherited, not duplicated)

`README.md` in this folder — pace, commits, round-report format.
`AGENTS.md` (repo root) — law and conventions. `../WORKFLOW.md` —
queue, routing, QUESTIONS protocol. Below: this role's specifics only.

## The sweep — check each surface, in order

### 1. Wiring — does the app actually assemble?

- Every route/module/command/handler is registered in the entrypoint —
  a file that exists but isn't wired is dead.
- Every registration target exists; every DI provider resolves to a
  real class.
- Barrel/`__all__` entries point at symbols that exist.
- CLI commands wired into the entry point; IPC channels have both ends;
  extension manifests match registered handlers.

### 2. Version and contract consistency

- Version string: all manifests + `__init__`/version files + docs
  claims must agree.
- API-spec artifacts (openapi.json, generated clients) freshness vs
  actual routes — check mtime/commit history, flag drift, don't
  regenerate unless asked.
- Dependency manifests agree with each other (lockfiles, duplicate
  requirement files, workspace roots vs package deps).
- Deps nothing imports (cross-check import lists).

### 3. Dead references — things pointing at ghosts

- CI configs, Makefiles, scripts, `.bat`/`.sh` — any path or command
  that no longer exists.
- Docs nav config entries → files that exist.
- Config/env examples → keys actually read by the code.
- Templates referencing deleted static files; clients fetching paths
  no route serves.
- Root packaging/deploy files (`Dockerfile`, compose, action.yml,
  installers) — paths and entrypoints still real?

### 4. Dead weight — things nothing points at

- Files never imported anywhere (grep the module name).
- Doc pages not in nav and not linked from README.
- Test files the runner would not collect (wrong naming, no tests).
- Exported symbols never used outside their own file + tests.
- Duplicate doc pairs rotting in parallel.

### 5. Board-vs-reality drift

- Board snapshot numbers vs recount: endpoints, tests, files —
  with method labels.
- Board claims "0 banned-pattern" → grep it.
- `[x] Done` rows in `done-log.md` where the pattern trivially still
  exists — flag for `cleanup_verify.md` (don't re-open yourself, list
  them).

### 6. Quick health probes per language

- Syntax-parse recently-changed files if exec allowed — or careful read.
- Strictness flags actually on (`tsconfig strict`, type-checker config,
  lint config not disabled).
- `package.json`/`Makefile` scripts pointing at existing files.
- Git: dirty tree, untracked temp files, committed artifacts
  (build output, `__pycache__`, `.env`).

## Rules

- **Static analysis only.** `read`, `grep`, `find_file_by_name`,
  `exec` for read-only commands + `git`. No test runs, no builds.
- **Breadth over depth.** Cover all surfaces; when something smells
  deep, file it and move on — deep dives belong to the other workflows.
- **Dedupe.** Skim board rows AND `done-log.md` first; extend an
  `S###` rather than duplicating it.
- **Evidence or it didn't happen.** Every finding: `file:line` + what
  you expected vs what you found.

## Output

1. `S###` rows appended to BOARD for real findings.
2. A sweep report: per-surface ✅/⚠️/❌, counts, and a short list of
   what needs a deep pass (`ai_slop_audit` for patterns, `bug_hunt`
   for suspected bugs, `docs_sync` for doc rot).
3. `docs:` commit if the board changed.
