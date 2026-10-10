# AGENTS.md — Operating Manual

> Закон проекта: verified facts, не аспирации. Каждое утверждение —
> file:line или команда проверки. Пустое честнее выдуманного.

**Работаешь? Выполняй `.devin/WORKFLOW.md`** — единственный driving loop
(orient → route → pick → do → verify → record → commit). Роли в
`.devin/workflows/` — спец-режимы под ним; их `README.md` читать первым.

## Что это за проект

GuardDOG — CLI-сканер репозиториев с гибридным анализом: локальный слой
(regex + AST, stdlib only) ловит хардкод-секреты/опасные паттерны, LLM-слой
(Gemini REST) делает глубокий аудит изменённых файлов. Результат —
Markdown/JSON отчёт + severity-gated exit code для CI/pre-commit.
Python 3.10+, runtime-зависимостей нет (urllib + ast + re).

## Архитектура — verified truth

- Entry: `main.py` — argparse CLI (`target`, `--no-llm`, `--fail-on`,
  `--format`, `--config`, `-o`), оркестрирует слои, возвращает exit code.
- `parsers/walker.py` — `iter_source_files()`: os.walk + `.gitignore` +
  `ignore_dirs`/`ignore_files`/`scan_extensions`/`max_file_size_kb`
  из `config.json`.
- `parsers/findings.py` — `Finding` (frozen dataclass) + `Severity`
  (IntEnum LOW< MEDIUM< HIGH< CRITICAL) — единая модель для обоих слоёв.
- `parsers/regex_scanner.py` — `RULES`: NamedTuple-таблица
  (rule_id, severity, compiled pattern, message, ast_covered). Строки
  `ast_covered=True` для `.py` пропускаются — их закрывает AST-слой.
- `parsers/ast_scanner.py` — `_check_node()` по `ast.walk`: hardcoded
  secret (Assign/AnnAssign со str-константой и secret-именем), print(secret),
  eval/exec, silent-except, star-import, long-function (>50 строк).
- `llm_client/context.py` — SHA-256 кэш `.guarddog_cache.json` в корне
  цели; неизменённые файлы не уходят в payload.
- `llm_client/client.py` — `audit_with_gemini()`: urllib POST на
  `generativelanguage.googleapis.com`, ключ из `GUARDDOG_API_KEY`/
  `GEMINI_API_KEY`; без ключа → `skipped_reason`, не падение.
  Ответ парсится как strict JSON → `Finding(source="llm")`.
- `report.py` — `render_markdown`/`render_json` +
  `exit_code(findings, fail_on)` (fail_on=never → всегда 0).
- State: процесс one-shot, состояние только в cache-файле на диске.
  Execution: sync, sequential — параллелизм не реализован.

## Target architecture — north-star

CLI-утилита, работающая в трёх контурах: ручной запуск, pre-commit hook,
CI-гейт. Куда движется: кэш → не только пропуск файлов, но и мемоизация
findings на файл; LLM → batching нескольких провайдеров; отчёт → HTML.
Load-failure map: LLM-слой — единственная точка сетевого отказа
(обрабатывается `skipped_reason`, не крашем); большие монорепы упрутся
в sequential walk + regex-per-line — тогда Go-rewrite или multiprocessing,
не раньше.

**Conformance rule:** перед merge спроси — дифф добавляет process-local
state, абстракцию без потребителя, endpoint без клиента, второй движок
существующего контура? Да → не делай, или запиши причину в этот файл.

## Confirmed defects — fix order

—

## Design rules

- **KISS/YAGNI** — минимальный корректный дифф; абстракция — со вторым
  потребителем; паттерн — только если уже канон в этом коде, а не
  «по учебнику».
- **DRY** — две копии предиката/модели/сторежка = один латентный баг;
  слить или назвать authority.
- **Fail-closed на security** — сбой LLM/API/файла помечается в отчёте
  (`skipped_reason`), никогда catch-log-continue и никогда fake-clean.
- **Антипаттерны на охоту:** regex-правило и AST-правило, проверяющие
  одно и то же на `.py` (→ `ast_covered`-флаг); мёртвые feature-flags;
  абстракция/функция без потребителя.
- **Вопросы ≠ гадать** — блок/неоднозначность → `.devin/QUESTIONS.md`.

## Conventions — наблюдаемые, не желаемые

- Модули — flat, по назначению слоя; никаких фабрик/регистри.
- Новое regex-правило = одна строка `Rule(...)` в `RULES`; AST-правило =
  ветка в `_check_node`.
- `from __future__ import annotations` вверху каждого модуля.
- Типизация — аннотации на всех публичных сигнатурах.
- Тесты: pytest + `tmp_path`, фикстуры-пэйлоады пишутся в tmp — исходники
  тестов не содержат секретов-паттернов (self-scan остаётся чистым).
- Ошибки запуска → `print(..., file=sys.stderr)` + exit 2; находки →
  stdout/отчёт, не stderr.

## Anti-slop rules

- Никаких новых доменов/абстракций без потребителя.
- Не меть `Legacy`/`deprecated` то, что wired в entrypoints.
- Не раздувать barrels (`__init__` пустые — так и держать).
- Не второй engine/facade на существующий контур (один LLM-клиент —
  один provider за раз).
- Не контракты, которые не держишь: watchdog-тесты без зубов хуже их
  отсутствия.
- Локальные import'ы внутри функций — только против import-циклов
  (`run_llm_layer` импортирует llm_client лениво — это осознанно:
  `--no-llm` не должен трогать LLM-модуль).
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
python -m pytest tests/ -q             # 8 passed
python -m pytest tests/test_scanners.py -q   # scoped
python main.py . --no-llm --fail-on never -o guarddog_report.md
                                       # smoke: генерит отчёт, exit 0
python main.py --help                  # CLI живой
```
