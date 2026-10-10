# GuardDOG 🐕‍🦺

[![Python](https://img.shields.io/badge/python-3.10%2B-blue?logo=python&logoColor=white)](https://www.python.org/)
[![License](https://img.shields.io/badge/license-MIT-green)](LICENSE)
[![Status](https://img.shields.io/badge/status-alpha-orange)]()
[![Deps](https://img.shields.io/badge/runtime%20deps-zero-brightgreen)]()
[![CI gate](https://img.shields.io/badge/exit%20code-CI%20ready-red)]()

CLI-сканер репозиториев с гибридным анализом: локальный слой (regex + AST)
ловит очевидное мгновенно и бесплатно, LLM-слой делает глубокий аудит
архитектуры и уязвимостей. Ответ — в отчёт и в exit code: нашёл CRITICAL —
роняет сборку.

Одна команда в терминале, в `run_all.bat` или в пайплайне CI/CD — и проект
проверен до коммита, а не после инцидента.

## Зачем

AI-сгенерированный код выглядит чистым: синтаксис правильный, имена
правдоподобные, тесты зелёные. Под ним — `PASSWORD = "..."` в проде,
`print(entered_pass)` в логе, `verify=False` на запросе к платёжке.
Линтеры это не видят — у них нет семантики. Нейросеть видит — но отправлять
ей весь репозиторий на каждый коммит дорого и медленно.

GuardDOG стоит между: локальный слой бесплатен и мгновенен, LLM вызывается
только на изменённых файлах (hash-cache) и только когда нужен.

## Как работает — пайплайн

```
target repo
    │
    ▼
┌─ 1. WALKER ──────────────── рекурсивный обход, .gitignore + ignore-правила
│        │                     из config.json, кап на размер файла
│        ▼
├─ 2. LOCAL LAYER ─────────── regex-правила (любой язык) + AST (Python):
│        │                     секреты в коде, print(secret), eval/exec,
│        │                     shell=True, verify=False, pickle, silent-except
│        ▼
├─ 3. LLM LAYER (опционально) сборка контекста → SHA-256 cache →
│        │                     изменённые файлы + system prompt → Gemini API →
│        │                     строгий JSON findings
│        ▼
└─ 4. REPORT + GATE ────────── Markdown/JSON отчёт, матрица severity,
                               exit code по порогу fail_on
```

## Архитектура

```
GuardDOG/
├── main.py              # точка входа: CLI, оркестрация слоёв, exit code
├── config.json          # ignore-правила, расширения, лимиты, fail_on, LLM
├── report.py            # Markdown/JSON рендер + severity gate
├── parsers/
│   ├── walker.py        # обход репо: .gitignore, ignore_dirs, size cap
│   ├── findings.py      # модель Finding + Severity (CRITICAL>HIGH>MED>LOW)
│   ├── regex_scanner.py # правила по строкам, мультиязычно
│   └── ast_scanner.py   # семантические проверки Python (stdlib ast)
├── llm_client/
│   ├── context.py       # SHA-256 кэш, сборка payload только из изменённых
│   └── client.py        # Gemini REST (urllib, без SDK), strict-JSON парсинг
├── templates/
│   └── system_prompt.md # системный промпт аудитора
└── tests/               # pytest: walker, regex, ast, gates
```

## Фичи

- **Zero runtime deps** — весь локальный слой на stdlib; LLM — через REST
  `urllib`, никаких SDK.
- **Hash-cache контекста** — SHA-256 каждого файла в `.guarddog_cache.json`;
  неизменённый файл не уходит в LLM повторно = токены не жгутся.
- **Severity Scopes** — CRITICAL / HIGH / MEDIUM / LOW; порог паники
  `--fail-on` или `fail_on` в конфиге. Любая находка ≥ порога → exit 1 →
  сборка падает.
- **Pre-commit режим** — в `.git/hooks/pre-commit`:
  ```bash
  python /path/to/GuardDOG/main.py . --no-llm --fail-on high --format json -o .guarddog_report.json
  ```
  Нашёл критическое — коммит блокируется.
- **Fail-open by design** — нет API-ключа? LLM-слой честно пишет
  `skipped — no GUARDDOG_API_KEY`, локальный слой всё равно отрабатывает.
  Никаких fake-green.

## Использование

```bash
# локальный слой только (offline, CI, pre-commit)
python main.py /path/to/project --no-llm

# полный гибрид (нужен ключ)
set GUARDDOG_API_KEY=<gemini key>
python main.py /path/to/project

# в CI: падать на high+, отчёт в JSON
python main.py . --fail-on high --format json -o report.json
echo %ERRORLEVEL%   # 0 = чисто, 1 = порог превышен, 2 = ошибка запуска
```

## Правила локального слоя

| Rule | Sev | Что ловит |
|------|-----|-----------|
| `hardcoded-secret` | CRITICAL | `password = "..."`, `api_key: "..."` (AST + regex) |
| `private-key-block` | CRITICAL | `-----BEGIN ... PRIVATE KEY-----` в репо |
| `print-secret` | CRITICAL | `print(password)` / `print(token)` |
| `eval-exec` | HIGH | `eval()`/`exec()` на динамическом вводе |
| `shell-true` | HIGH | `subprocess(..., shell=True)` |
| `verify-false` | HIGH | `requests.get(..., verify=False)` — TLS off |
| `pickle-load` | HIGH | `pickle.loads` на недоверенных данных |
| `yaml-load-unsafe` | HIGH | `yaml.load` без SafeLoader |
| `debug-enabled` | MEDIUM | `debug=True` / `DEBUG=1` в коде |
| `bind-all-interfaces` | MEDIUM | биндинг на `0.0.0.0` |
| `silent-except` | MEDIUM | `except Exception: pass` (AST) |
| `star-import` / `long-function` | LOW | гигиена |
| `todo-leftover` | LOW | TODO/FIXME/HACK маркеры |

## Конфиг (`config.json`)

| Ключ | Что задаёт |
|------|-----------|
| `ignore_dirs` / `ignore_files` | что не трогать (`.gitignore` читается тоже) |
| `scan_extensions` | расширения файлов под скан |
| `max_file_size_kb` | кап размера файла |
| `fail_on` | порог exit 1 (default `critical`) |
| `llm.provider` / `llm.model` / `llm.max_files` | нейрослой |

## Roadmap

- [x] MVP: walker + regex + AST + MD/JSON отчёт + severity gate
- [ ] LLM-слой: живой прогон Gemini с ключом, валидация JSON-схемы ответа
- [ ] HTML-дашборд (матрица severity, фильтры по правилам)
- [ ] `run_all.bat` / pre-commit installer (`guarddog install-hook`)
- [ ] AST-правила для JS/TS (tree-sitter)
- [ ] Go-rewrite для single-binary скорости, когда Python упрётся

## Принципы

- **Verify, don't trust** — каждая находка с file:line, никакой спекуляции.
- **Fail-closed on security** — ошибка сканера ≠ "всё чисто"; сбой LLM
  помечается в отчёте, не проглатывается.
- **Рабочий процесс** — `.devin/WORKFLOW.md` (adopted agents-workflow kit):
  маршруты задач, конечный PLAN, вопросы вместо гадания, доска находок.

## License

MIT — см. [LICENSE](LICENSE).
