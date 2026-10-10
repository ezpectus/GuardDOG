# GuardDOG 🐕‍🦺

[![Python](https://img.shields.io/badge/python-3.10%2B-blue?logo=python&logoColor=white)](https://www.python.org/)
[![License](https://img.shields.io/badge/license-MIT-green)](LICENSE)
[![Status](https://img.shields.io/badge/status-alpha-orange)]()
[![Runtime deps](https://img.shields.io/badge/runtime%20deps-zero-brightgreen)]()
[![CI gate](https://img.shields.io/badge/exit%20code-CI%20ready-red)]()
[![Tests](https://img.shields.io/badge/tests-25%20passed-brightgreen)](tests/)

CLI-сканер репозиториев с гибридным анализом. Локальный слой (regex + AST)
ловит очевидное мгновенно и бесплатно; LLM-слой делает глубокий аудит
только изменённых файлов. Ответ — в отчёте и в exit code: нашёл находку ≥
порога — роняет сборку или блокирует коммит.

Одна команда в терминале, в `run_all.bat`, в pre-commit hook или в пайплайне
CI/CD — проект проверяется до инцидента, а не после.

## Зачем

AI-сгенерированный код выглядит чистым: синтаксис правильный, имена
правдоподобные, тесты зелёные. Под ним — `PASSWORD = "..."` в проде,
`print(entered_pass)` в логе, `verify=False` на запросе к платёжке.
Линтеры это не видят — у них нет такой семантики. Нейросеть видит — но
гонять ей весь репозиторий на каждый коммит дорого и медленно.

GuardDOG стоит посередине: локальный слой бесплатен и мгновенен, а LLM
вызывается только на изменённых файлах (SHA-256 cache) и только когда есть
API-ключ. Нет ключа — честный `skipped`, локальный слой всё равно
отрабатывает. Никаких fake-green.

## Пайплайн

```
target repo
    │
    ▼
┌─ 1. WALKER ──────────── os.walk + .gitignore + ignore-правила из конфига,
│        │                 кап на размер файла, allowlist расширений
│        ▼
├─ 2. LOCAL LAYER ──────── regex-таблица (17 правил, любой язык) +
│        │                 AST-слой для Python (~14 проверок: секреты,
│        │                 print(secret), eval/exec, shell=True, verify=False,
│        │                 pickle/yaml.load, os.system, weak-hash, silent-except…)
│        ▼
├─ 3. LLM LAYER (opt.) ─── приоритет key-файлов → SHA-256 cache →
│        │                  только изменённые → Gemini/OpenAI-compatible REST →
│        │                  strict-JSON findings → merge в общий список
│        ▼
└─ 4. REPORT + GATE ────── Markdown / JSON / HTML-дашборд,
                           severity-матрица, exit code по порогу fail_on
```

## Архитектура

```
GuardDOG/
├── main.py               # тонкий entry → cli.main()
├── cli.py                # сабкоманды: scan / install-hook / rules / cache
├── config.py             # config.json → .guarddog.json (target) → --config
├── report.py             # MD / JSON / HTML рендеры + severity gate
├── config.json           # единый authority: ignore, extensions, fail_on, llm
├── parsers/
│   ├── findings.py       # Finding + Severity (IntEnum) + ScanResult
│   ├── rules.py          # regex-таблица — единый источник правил
│   ├── regex_scanner.py  # применяет таблицу построчно
│   ├── ast_scanner.py    # семантика Python через stdlib ast
│   └── walker.py         # обход репо с ignore-стеком
├── llm_client/
│   ├── context.py        # SHA-256 кэш + priority-порядок key-файлов
│   └── client.py         # провайдеры: gemini | openai-compatible
├── templates/
│   ├── system_prompt.md  # системный промпт аудитора (strict JSON)
│   └── report.html       # шаблон HTML-дашборда (string.Template)
├── tests/                # 25 тестов: walker/regex/ast/report/cli/cache/hook
└── .devin/               # agents-workflow: процесс работы над проектом
```

## Использование

```bash
# локальный слой (offline, CI, pre-commit)
python main.py scan /path/to/project --no-llm

# полный гибрид
set GUARDDOG_API_KEY=<gemini key>        # или OPENAI_API_KEY
python main.py scan /path/to/project

# CI-гейт: падать на high+, JSON для артефактов
python main.py scan . --fail-on high --format json -o report.json

# HTML-дашборд
python main.py scan . --format html -o report.html

# pre-commit hook в целевой репо
python main.py install-hook /path/to/project --fail-on high

# список правил / управление кэшем
python main.py rules
python main.py cache /path/to/project --clear
```

`guarddog <path>` без сабкоманды = `guarddog scan <path>`.

**Exit codes:** `0` — чисто (ниже порога) · `1` — находка ≥ `fail_on` ·
`2` — ошибка запуска (нет таргета, хук уже есть без --force).

## Локальные правила

| Rule | Sev | Что ловит |
|------|-----|-----------|
| `hardcoded-secret` | CRITICAL | `password/api_key/secret/... = "..."` (AST + regex) |
| `private-key-block` | CRITICAL | `-----BEGIN ... PRIVATE KEY-----` в репо |
| `cloud-key` | CRITICAL | форматы AWS `AKIA…`, GitHub `ghp_`, Slack `xox*`, OpenAI `sk-` |
| `print-secret` | CRITICAL | `print(password)` / утечка секрета в stdout |
| `eval-exec` | HIGH | `eval()`/`exec()` |
| `shell-true` | HIGH | `subprocess(..., shell=True)` |
| `verify-false` | HIGH | `verify=False` — TLS verification off |
| `pickle-load` | HIGH | `pickle.load/loads` |
| `yaml-load-unsafe` | HIGH | `yaml.load` без `Loader=` |
| `os-system` | HIGH | `os.system()` — shell injection |
| `sql-format-exec` | HIGH | `execute(f"..."` / `%` / конкатенация в SQL |
| `debug-enabled` | MEDIUM | `debug=True` / `DEBUG=1` |
| `bind-all-interfaces` | MEDIUM | bind на `0.0.0.0` |
| `weak-hash` | MEDIUM | `hashlib.md5/sha1`, `createHash('md5')` |
| `cors-wildcard` | MEDIUM | `Access-Control-Allow-Origin: *` |
| `silent-except` | MEDIUM | `except: pass`/`...` (AST) |
| `insecure-tempfile` | MEDIUM | `tempfile.mktemp` — race condition |
| `todo-leftover` / `commented-code` / `star-import` / `assert-in-prod` / `long-function` | LOW | гигиена |

На `.py`-файлах правила с `ast_covered` отдаются AST-слою — без дублей:
одна находка = один слой.

## Конфигурация

Три слоя, поздний побеждает (dict — merge, list — append-unique):

1. `config.json` в каталоге сканера — дефолты
2. `.guarddog.json` в корне **сканируемого** проекта — свои правила репо
3. `--config <path>` — явный override

| Ключ | Что задаёт |
|------|-----------|
| `ignore_dirs` / `ignore_files` | что не трогать (`.gitignore` читается тоже) |
| `scan_extensions` | расширения/имена файлов под скан |
| `max_file_size_kb` | кап размера файла (default 256) |
| `fail_on` | порог exit 1 (default `critical`; `never` = всегда 0) |
| `llm.provider` | `gemini` | `openai` (base_url настраивается → Groq/Together/llama.cpp) |
| `llm.model` / `llm.max_files` / `llm.timeout_sec` | нейрослой |

## Inline-suppression

Ложное срабатывание гасится на месте — комментарием в той же строке:

```python
API_KEY = "test-fixture"   # guarddog: ignore hardcoded-secret
OLD_LINE = "..."           # guarddog: ignore           ← глушит всё на строке
```

Работает и для regex-, и для AST-находок.

## LLM-слой — честность по дизайну

- Ключи: `GUARDDOG_API_KEY` → `GEMINI_API_KEY`/`OPENAI_API_KEY`.
- Нет ключа → `skipped — no key` в отчёте, exit code от локального слоя.
- API упал → `skipped — <ошибка>` в отчёте. Сбой ≠ «чисто».
- Кэш `.guarddog_cache.json` в корне цели; payload = только изменённые
  файлы, приоритет — `models/settings/auth/compose/Dockerfile/…`.
- Кэш коммитится только после реального ответа API — иначе пропуск был бы
  мемоизирован без аудита.

## Принципы

- **Verify, don't trust** — каждая находка с file:line, без спекуляций.
- **Fail-closed** — ошибка сканера видна в отчёте, не проглатывается.
- **Zero runtime deps** — stdlib only: `ast`, `re`, `urllib`, `argparse`.
- **Процесс работы** — `.devin/WORKFLOW.md` (adopted agents-workflow kit):
  маршруты задач, конечный PLAN, вопросы вместо гадания, доска находок.

## Roadmap

- [x] Local layer: 17 regex + ~14 AST правил, severity, exit gate
- [x] CLI: scan / install-hook / rules / cache; bare-path shorthand
- [x] Отчёты: Markdown, JSON, HTML-дашборд
- [x] LLM-слой: Gemini + OpenAI-compatible, SHA-256 context cache,
      priority-файлы, strict-JSON парсинг
- [x] Per-target конфиг `.guarddog.json`
- [ ] Живой LLM-прогон с ключом + retry на невалидный JSON (B1/B4 в PLAN)
- [ ] AST-правила для JS/TS (tree-sitter)
- [ ] Go-rewrite → single-binary, когда Python упрётся в скорость

## License

MIT — см. [LICENSE](LICENSE).
