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

> 2026-10-10: полноценное приложение — cli.py (scan/install-hook/rules/
> cache), 17 regex + ~15 AST правил, HTML-дашборд, config-слои
> (config.json → .guarddog.json → --config), LLM: gemini+openai-compat.
> A1/A2/B2/B3 done. Открыто: B1 (живой LLM-прогон), B4, B5.

## Open findings

| ID | Sev | Что | file:line — доказательство | P# | Status |
|----|-----|-----|----------------------------|----|--------|
