# Board — GuardDOG

> **Last updated:** 2026-10-10, kit adopted + MVP scaffold
> Round-by-round history: `.devin/archive/audit-log.md`

---

## Конвенции борда

- Находки — `S###`-строки, одна сквозная нумерация: next = max по этому
  файлу **и** `.devin/done-log.md` (закрытые строки переезжают туда).
- Борд держит только `[ ] Open`. `Done` → перенос в `done-log.md` — это
  очередь верификатора; `[x] Verified` ставит только
  `workflows/cleanup_verify.md`, никогда сам фиксер.
- `#N`-находки с датированных аудит-бордов (`.devin/audit-YYYY-MM-DD.md`)
  — ОТДЕЛЬНОЕ пространство имён и отдельный цикл
  (`workflows/audit_fix_loop.md`). Не переносить туда-сюда.

## Session state — continue from here

> Kit adopted 2026-10-10: MVP-скелет сканера на месте (walker + regex +
> AST + LLM-client stub + report + gate), 8 тестов зелёные, ruff чист.
> Следующее — PLAN A1/A2.

## Open findings

| ID | Sev | Что | file:line — доказательство | P# | Status |
|----|-----|-----|----------------------------|----|--------|
