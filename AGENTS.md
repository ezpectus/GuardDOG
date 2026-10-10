# AGENTS.md — Operating Manual

> Закон проекта: verified facts, не аспирации. Каждое утверждение —
> file:line или команда проверки. Пустое честнее выдуманного.

**Работаешь? Выполняй `.devin/WORKFLOW.md`** — единственный driving loop
(orient → route → pick → do → verify → record → commit). Роли в
`.devin/workflows/` — спец-режимы под ним; их `README.md` читать первым.

## Что это за проект

GuardDOG — CLI-сканер репозиториев с гибридным анализом: локальный слой
(17 regex-правил + ~15 AST-проверок, stdlib only) ловит хардкод-секреты и
опасные паттерны; LLM-слой (Gemini / OpenAI-compatible REST) аудирует
только изменённые файлы (SHA-256 cache). Отчёт — Markdown/JSON/HTML +
severity-gated exit code для CI/pre-commit. Python 3.10+, runtime
deps = 0.

## Архитектура — verified truth

- Entry: `main.py` (10 строк, thin) → `cli.py:main()` — argparse с
  сабкомандами `scan` (default; bare `<path>` = scan), `install-hook`,
  `rules`, `cache`.
- `config.py` — `load()`: `config.json` (scanner root, authority) →
  `<target>/.guarddog.json` → `--config`; `_merge`: dict merge, list
  append-unique, scalar replace. `Config` — typed accessor-обёртка.
- `parsers/findings.py` — `Finding` (frozen dataclass), `Severity`
  (IntEnum LOW<MEDIUM<HIGH<CRITICAL), `ScanResult` (counts + exit_code).
- `parsers/rules.py` — `RULES`: NamedTuple-таблица (rule_id, severity,
  pattern, message, ast_covered). `ast_covered=True` → на `.py` файле
  правило пропускается, его закрывает AST (без дублей). `AST_RULE_IDS`.
- `parsers/regex_scanner.py` — построчное применение RULES.
- `parsers/ast_scanner.py` — `_check_node`/`_check_call` по `ast.walk`:
  secret-assign, print(secret), eval/exec, subprocess shell=True,
  verify=False, pickle.load(s), yaml.load без Loader, hashlib.md5/sha1,
  tempfile.mktemp, debug=True kwarg, silent-except, star-import,
  assert-in-prod (пропуск в tests/), long-function (>50 строк).
- `parsers/walker.py` — `iter_source_files`: os.walk + `.gitignore`
  цели (без `!`-negation — задокументированный лимит) + ignore_dirs/
  ignore_files + extension allowlist + size cap.
- `llm_client/context.py` — `.guarddog_cache.json` (path→sha256),
  `KEY_FILE` regex даёт приоритет models/settings/auth/compose при
  наборе payload.
- `llm_client/client.py` — `audit()` диспетчер по `llm.provider`:
  `_audit_gemini` / `_audit_openai` (urllib POST, strict-JSON extract
  → `Finding(source="llm")`). Нет ключа/сбой → `skipped_reason`,
  не падение. Cache сохраняется только после успешного ответа.
- `report.py` — `render_markdown` / `render_json` / `render_html`
  (`templates/report.html` + `string.Template`, self-contained CSS).
- State: процесс one-shot; единственное состояние — cache-файл и
  report-файл в корне цели. Execution: sync, sequential.

## Target architecture — north-star

CLI-утилита в трёх контурах: ручной запуск, pre-commit hook, CI-гейт.
Куда движется: живой LLM-прогон с retry-валидацией JSON (PLAN B1/B4),
tree-sitter для JS/TS AST, Go-rewrite при упоре в скорость.
Load-failure map: LLM — единственная сетевая точка отказа (обработан
через skipped_reason); большие монорепы упрутся в sequential
walk+regex — тогда multiprocessing, не раньше.

**Conformance rule:** перед merge спроси — дифф добавляет process-local
state, абстракцию без потребителя, endpoint без клиента, второй движок
существующего контура? Да → не делай, или запиши причину в этот файл.

## Confirmed defects — fix order

—

## Design rules

- **KISS/YAGNI** — минимальный корректный дифф; абстракция — со вторым
  потребителем; паттерн — только если уже канон в этом коде.
- **DRY** — две копии предиката/модели = один латентный баг. `config.json`
  — единый authority дефолтов (в коде только .get-фолбэки); `rules.py` —
  единая таблица regex-правил.
- **Fail-closed на security** — сбой LLM/API/файла помечается в отчёте
  (`skipped_reason`/`llm_note`), никогда catch-log-continue.
- **Антипаттерны на охоту:** regex и AST проверяющие одно на `.py`
  (→ `ast_covered`); мёртвые feature-flags; абстракция без потребителя;
  провайдер LLM добавленный «про запас».
- **Вопросы ≠ гадать** — блок/неоднозначность → `.devin/QUESTIONS.md`.

## Conventions — наблюдаемые, не желаемые

- Flat-модули по назначению слоя; `main.py` остаётся thin (10 строк).
- Новое regex-правило = одна строка `Rule(...)` в `RULES`; AST-правило =
  ветка в `_check_node`/`_check_call`; правило, покрытое AST, получает
  `ast_covered=True` в таблице.
- `from __future__ import annotations` вверху каждого модуля; аннотации
  на публичных сигнатурах.
- Тесты: pytest + `tmp_path`; пэйлоады-«секреты» пишутся в tmp — исходники
  тестов чисты под self-scan.
- Ошибки запуска → `print(..., file=sys.stderr)` + exit 2; находки →
  stdout/отчёт.
- LLM-импорты ленивые внутри `_llm_scan` — `--no-llm` не трогает
  llm_client вообще.

## Anti-slop rules

- Никаких новых доменов/абстракций без потребителя.
- Не меть `Legacy`/`deprecated` то, что wired в entrypoints.
- `__init__.py` пустые — не раздувать barrels.
- Не второй engine/facade на существующий контур.
- Не контракты, которые не держишь.
- Локальные import'ы внутри функций — только ленивый LLM-слой
  (осознанно, зафиксировано выше).
- Комментарии не добавлять и не удалять без запроса; маркеры ран
  (`S###`, `#N`, `Q-###`) — реальные инциденты, не трогать.

## Generated-code signatures — recurring wounds

Канон — `.devin/SIGNATURES.md`: классы дефектов с grep-сигнатурой и
направлением фикса. Новая повторяющаяся рана → новый класс туда с датой.
Перед похожей правкой — сначала сверься с каталогом.

## Verification commands

```bash
python -m ruff check .                 # lint — чист
python -m ruff format --check .        # format check
python -m pytest tests/ -q             # 25 passed
python -m pytest tests/test_scanners.py -q   # scoped
python main.py scan . --no-llm --fail-on never -o guarddog_report.md
                                       # smoke: self-scan, exit 0
python main.py --help && python main.py rules   # CLI живой
# e2e (A2): подсадный репо с секретами → exit 1, находки в отчёте —
#   воспроизводится tests/test_cli.py::test_scan_finds_planted_vulns
```
