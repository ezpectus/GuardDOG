# PLAN.md — конечный путь к «базово готово»

> Единственная активная очередь проекта.
> Правило: item = один раунд = один коммит. Порядок — сверху вниз, без
> пропусков. Список КОНЕЧНЫЙ: не пополняется находками — всё вне этого
> плана уходит в `PARKED` (внизу) и не выполняется до завершения плана.
> Отметка `[x]` — только с evidence (команда + наблюдаемый результат).

## Фаза A — доказать, что проект живой (verify, не assume)

- [x] **A1. Гейты на чистой среде** — `ruff check` чист,
      `ruff format --check` чист, `pytest tests/ -q` → 25 passed,
      `python main.py scan . --no-llm` пишет отчёт, exit 0 (2026-10-10).
- [x] **A2. Живой end-to-end на подсадном репо** — tmp-репо с посаженными
      секретами/shell/eval/private-key → 6 находок (3 CRITICAL + 3 HIGH),
      exit 1 при fail_on=critical, HTML+MD отчёты с file:line
      (2026-10-10). Воспроизводимо: `tests/test_cli.py::test_scan_finds_planted_vulns`.

## Фаза B — продуктовые шаги

- [ ] **B1.** LLM-слой живой: прогон с реальным `GUARDDOG_API_KEY`,
      JSON-ответ валидируется в findings, cache реально пропускает
      неизменённые файлы (второй прогон → 0 файлов в payload).
- [x] **B2.** Pre-commit hook: `guarddog install-hook <repo>` пишет
      `.git/hooks/pre-commit` (sh, chmod +x, --force для перезаписи);
      тест `test_install_hook` + `test_hook_refuses_overwrite` (2026-10-10).
- [x] **B3.** HTML-дашборд: `templates/report.html` + `render_html` —
      severity-карточки, таблица с collapsible-сниппетами (2026-10-10).
- [ ] **B4.** JSON-схема ответа LLM — строгая валидация + retry при
      невалидном ответе (сейчас: молчаливый skip невалидных items).
- [ ] **B5.** OpenAI-провайдер: живой прогон (код есть — `_audit_openai`,
      не проверен на реальном ключе; без ключа = unverified).

## PARKED — не трогать до завершения плана

Всё, что не на пути к цели: запахи, найденные по ходу, хотелки, аудиты
новых поверхностей, рефакторы «для красоты». Одна короткая строка на
находку. Это склад, а не очередь.

- `parsers/rules.py` сам себя флагает `todo-leftover`/`commented-code`
  (литералы паттернов) — known self-hit, не баг.
- `.gitignore`-парсер без `!`-negation и anchored-путей — лимит
  задокументирован в docstring walker.py.
- AST-правила для JS/TS через tree-sitter — после MVP.
- Go-rewrite для single-binary — только если Python упрётся в скорость.
- findings-кэш (мемоизация находок на файл, не только hash для LLM) —
  потенциальный speedup, но меняет семантику — через Q-entry.
