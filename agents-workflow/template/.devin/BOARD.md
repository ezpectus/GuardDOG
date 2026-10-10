# Board — {{PROJECT_NAME}}

> **Last updated:** {{date}}, {{что было}}
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

> Что делала последняя сессия (commits, где резюмировать). Одна-две
> строки. История — в `archive/audit-log.md`; шапку не раздувать
> (прецедент: однажды она выросла до 145KB).

## Open findings

| ID | Sev | Что | file:line — доказательство | P# | Status |
|----|-----|-----|----------------------------|----|--------|
