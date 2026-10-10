---
description: AI Slop audit — find and document anti-patterns across the WHOLE project (code, tests, frontend, cli, docs, CI)
auto_execution_mode: 3
---

# AI Slop Audit — Whole Project

Role: **AUDITOR**. You find AI slop and document it on `.devin/BOARD.md`.
You do NOT fix code — fixing is `slop_cleanup.md`'s job. Verification of
fixes is `cleanup_verify.md`'s job.

## Invocation

> Run `.devin/workflows/ai_slop_audit.md` over the whole project (or a
> named scope). Append new `S###` rows to BOARD.

## Shared rules (inherited, not duplicated)

`README.md` in this folder — pace, commits, round-report format.
`AGENTS.md` (repo root) — law and conventions; §«Generated-code
signatures» + `.devin/SIGNATURES.md` = the recurring wound catalog —
check it before writing new findings. `../WORKFLOW.md` — queue, routing,
QUESTIONS protocol. Below: this role's specifics only.

## When to use

- After any feature/refactor batch lands.
- Before a release or docs checkpoint.
- When the user says "аудит", "найди slop", "обнови доску".
- **Заморожен по умолчанию** (см. `../WORKFLOW.md` Шаг 2): только по
  явной просьбе — бесконтрольные прогоны генерят бесконечную чистку.

## Project snapshot (verify, don't trust)

| Surface | Что там | Размер (2026-10-10, `wc -l`) |
|---|---|---|
| `main.py` | CLI entry, оркестрация слоёв | 122 LOC |
| `report.py` | MD/JSON рендер + exit gate | 68 LOC |
| `parsers/` | walker + findings + regex + ast | 5 files, 362 LOC |
| `llm_client/` | context (SHA-256 cache) + Gemini REST client | 3 files, 160 LOC |
| `tests/` | pytest suite | 1 file, 8 tests (`pytest --collect-only`), 83 LOC |
| `templates/` | system prompt для LLM | 1 file, 28 LOC |
| `config.json` | правила игнора, лимиты, fail_on | 24 строки |
| `.devin/` | workflow-система | — |

Правил regex: 11 (метод: `len(RULES)` в `regex_scanner.py`).
Правил AST: 6 (метод: счёт веток `_check_node` в `ast_scanner.py`).

Board convention: findings are `S###` rows, one global sequence
(next: max existing + 1 — search **both** `BOARD.md` and `done-log.md`,
closed rows live there). Statuses: `[ ] Open` on the board → cleaner
moves the row to `done-log.md` as `[x] Done` → verifier marks
`[x] Verified` in done-log. The board holds only open work.

## Core mindset

**Assume the architecture is shit until proven otherwise.** AI-generated
code looks clean on the surface — correct syntax, plausible names,
passing tests — but is hollow underneath. Your job is to find where
it's hollow.

- **Don't trust the docs.** README says "enterprise-grade" — check if
  it's real or a stub.
- **Don't trust the tests.** Tests pass because they assert
  `isinstance(result, dict)` — not because the code works.
- **Don't trust the names.** `SelfHealingService` might just return
  `True`. `AIRootCauseAnalyzer` might be keyword matching.
- **Follow the data.** If a function returns a dict, trace what actually
  goes in it. If it's hardcoded — it's fake.
- **Count everything, label the counting method.** A decorator-grep
  count and a runtime registry count are different numbers. Never copy
  a number without its definition and date.

## Project law — hard bans (always count as slop)

Стек — чистый Python 3.10+ (stdlib only, runtime deps = 0). Таблица
дефолта Python/TS оставлена целиком; TS/React и desktop-секции в
coverage map ниже для этого репо не существуют — пропускать.

New occurrences are findings. Existing occurrences in documented
compatibility/re-export hubs are verified and tracked as exceptions,
not silently counted as clean.

| # | Ban | Correct form |
|---|-----|--------------|
| 1 | `Any`/`any` type (typed-стек) | конкретные типы, `Protocol`/generics |
| 2 | `# type: ignore` / `@ts-ignore` без причины | fix the type |
| 3 | `datetime.now()` без tz | `datetime.now(timezone.utc)` |
| 4 | mutable default `def f(x=[])` | `x: list \| None = None` |
| 5 | `except: pass` / `except Exception: pass` | specific exceptions + log |
| 6 | `threading.Lock` в async-коде | `asyncio.Lock` |
| 7 | sync HTTP/blocking в `async def` | async client / executor |
| 8 | new star imports вне barrel-файла | explicit imports |
| 9 | `\|safe` в шаблонах / unescaped `dangerouslySetInnerHTML` | remove/escape |
| 10 | `print()`/`console.log` в прод-коде | `logging`/`logger` |
| 11 | magic numbers | named constants |
| 12 | inline imports (non-circular) | top of file |
| 13 | `eval()`/`exec()` | delete |
| 14 | unsolicited comments/docstrings | don't add |
| 15 | `pickle.loads`/`yaml.load` без SafeLoader | delete/safe loader |

Limits: functions <50 lines, files <500 lines, params <5, commits
<1,000 lines.

## Before you start

1. `todo_write` an audit plan per surface.
2. Get the next `S` number: max `S###` across `BOARD.md` **and**
   `done-log.md` (closed rows moved there — board max ≠ global max).
3. Skim the board's existing rows — do NOT re-report known findings.
   Extend them instead ("Extends S###…").

## Coverage map — check EVERY surface

Do not stop at the main source dir. A whole-project audit touches all
surfaces that exist in this repo (calibrate at adoption — удалить
несуществующие):

### 1. Backend/source (line-level)

- `range(len(`, `len(x) > 0`/`== 0`/`!= 0` где хватает truthiness,
  `== ""`/`== []`/`== {}`
- `getattr(`/`hasattr(` duck-typing вместо `isinstance`
- `except Exception:`/bare `except:`/copy-paste exception tuples,
  особенно тела `pass`/`return None`/`return {}`
- Избыточные конверсии `str(Path(`, `Path(str(`, `str(str(`
- `async def` без `await` — sync притворяется async; blocking-вызовы
  внутри `async def`
- `time.time()` для duration (→ `time.monotonic()`), `sleep` в
  request-path
- `type(x) ==` вместо `isinstance()`
- `random.`/`Math.random()` в сервисах — фейковые метрики/score
- `setattr(model, f, v)` partial updates мимо валидации
- `startswith()` для path-containment (→ `is_relative_to`/equivalent)
- `import *`, `# type: ignore`, `# noqa` без причины,
  `TODO`/`FIXME`/`HACK`, `pass` как тело

### 2. Backend/source (structural)

- Flat dump: один домен размазан по `x.py` + `x_service.py` +
  `routers/x.py` + `models/x.py`
- Layer bypass: endpoint/handler дёргает repo напрямую, минуя service
- God files >500 строк, функции >50 строк, >5 params без params-object
- Module-level mutable `dict`/`list`/`set` глобалы (process-local state
  как shared — SIGNATURES)
- Нетипизированные endpoint returns / `dict` вместо response-модели
- Stub-модели, существующие только ради `__all__`-импортов
- Циклические import'ы, спрятанные за `TYPE_CHECKING`/lazy imports
- Fake features: hardcoded returns, `random` scores, "connected" без
  API-вызова, keyword-matching "AI"
- Repo/ABC-пролиферация: оправдан ли новый интерфейс, или это CRUD-
  обёртка без второго потребителя?

### 3. Tests — test slop

- Единственные assertions: `isinstance()`, `callable()`,
  `issubclass()`, `is not None` на импортах
- `assert len(...) == 0`/`> 0`, `== ""`/`== []`/`== {}` — пустоту, не
  содержимое
- `assert ... or ...` — проходит на любой ветке
- `assert status_code in (200, 400, 500)` — принимает и успех, и отказ
- `patch()` без `autospec`, тесты на mock-вызовах, не на поведении
- `try/except` вместо `pytest.raises`/assert-error
- `skip`/`xfail` без reason
- Дубли тест-функций в разных файлах; shim-файлы, реэкспортирующие
  тесты — двойная коллекция
- **Vacuum coverage** (SIGNATURES): файлы, названные integration/contract,
  но не трогающие реальный ресурс

### 4. Frontend — TS/React (если есть)

- `any`, `as any`, `@ts-ignore`/`@ts-expect-error` без обоснования,
  non-null `!`
- `console.log` в прод-путях
- `useEffect` с missing deps / `eslint-disable exhaustive-deps`
- `dangerouslySetInnerHTML` — XSS surface
- Mock-массивы отрендерены как реальный UI; `fetch`/`axios` на
  endpoints, которых нет в backend — сверять каждый `/api/...` string
  с реальными роутами
- Dead pages/routes/components, unused exports, commented-out blocks
- Дубли компонентов вместо shared-пакета
- Generated client drift vs API-контракт

### 5. CLI / tooling surface (если есть)

- Флаги парсятся, но игнорируются (`elif args.x: pass`)
- Команды зарегистрированы, но не подключены к dispatcher'у
- `except Exception: pass` прячет сбои; `exit(0)` на error-path
- `print` для ошибок вместо stderr + non-zero exit
- Опции в help, которые никто не читает

### 6. Desktop/extension surfaces (если есть)

- `nodeIntegration: true`, `contextIsolation: false`, `webSecurity: false`
- `openExternal()`/`loadURL()` на untrusted input
- Dead IPC-каналы (handle без caller'а и наоборот)
- Зарегистрированные команды со stub-handler'ами

### 7. Templates / static (если есть)

- `|safe`/unescaped интерполяция — инъекция
- `{{ var }}`, которых нет ни в одном render-контексте
  (placeholder theatre — SIGNATURES)
- Шаблоны, которые никто не рендерит (grep имени в коде)
- Статические файлы без referrer'ов

### 8. Docs — документы, которые врут

- Числа, не совпадающие с пересчётом (endpoints/tests/repos) —
  recount, don't copy
- Feature-claims для endpoints-заглушек
- Доки про удалённые вещи: старые dirs, заархивированные SDK,
  снятые endpoints
- Дублирующиеся файлы (`migration.md` vs `migrations.md` и т.п.)
- Мёртвые внутренние ссылки, stale диапазоны `S###`

### 9. CI/infra

- Jobs/steps, ссылающиеся на удалённые пути
- Actions/tools, запиначенные на `@main`/`@master` вместо SHA/tag
- Скрипты/targets, вызывающие удалённые инструменты
- Миграции, разошедшиеся с моделями; disconnected heads
- Дрифт зависимостей между манифестами (`requirements.txt` vs
  `pyproject.toml` и т.п.)
- Секреты/креды в plain text где угодно

### 10. Cross-cutting

- Dead code: функции без callers, файлы без импортов, endpoints без
  клиентов, модели без инстанцирования, repos без injection
- Version drift между манифестами и `__init__`/version-файлами
- Dependency bloat: зависимости, которые ничто не импортирует
- **Interface width as fiction** (SIGNATURES): интерфейсы/тройки без
  потребителя — доказать caller-отсутствие grep'ом перед вердиктом

## How to tell real from fake

| Looks real | Actually fake |
|---|---|
| `def analyze_quality(code)` | Returns `{"score": 0.85}` — hardcoded |
| `def detect_flaky_tests(runs)` | Always returns `[]` or same list |
| `def predict_failure(test)` | `return random.uniform(0.7, 0.95)` |
| `def heal_selector(selector)` | `return f"{selector}-fixed"` — string concat |
| `class AIRootCauseAnalyzer` | `if "timeout" in error: return "network"` — keyword matching |
| `class SelfHealingService` | `verify()` always returns `True` |
| `class IntegrationsHub` | `connect_jira()` returns `{"status": "connected"}` — no API call |
| `const Dashboard = () => …` | Renders `mockData` const, never fetches |
| `program.command("fix")` | Handler body is `pass` / only prints "done" |

## Measuring the fake percentage

1. Total endpoints/commands (runtime-регистрация, не grep — укажи метод).
2. Endpoints без response-модели / возвращающие голый dict.
3. Endpoints с `random.`/hardcoded payload.
4. Endpoints без repo/service/external API вызова.
5. **fake % = (stubs + random + hardcoded + dead) / total**

| fake % | Verdict |
|---|---|
| < 10% | Normal |
| 10–30% | Warning — clean before launch |
| 30–50% | Feature factory — half the surface is fake |
| > 50% | Demo, not a product |

## Steps

1. **Plan** — `todo_write` one item per surface.
2. **Search** — targeted `grep` per section; `find_file_by_name` for
   liveness checks; `exec` only for read-only counting (`ls`, `wc -l`)
   and `git`.
3. **Analyze** — read context around each match. Distinguish real slop
   from legitimate use:
   - `if not user:` after a repo `get()` — usually fine
   - `if not data: return []` on a list param — often legitimate
   - `range(len(...))` in a comprehension — almost always slop
   - `assert len(x) > 0` in tests — weak, counts
   - When a grep caps out at the match limit, it's systemic — say so.
4. **Document** — append `S###` rows to `.devin/BOARD.md` (format
   below). Then log the round: append one
   `- <date> audit round N: <findings + verified-clean summary>` entry
   to `.devin/archive/audit-log.md`, and update the
   `> **Last updated:**` pointer in the board header — one line only;
   история живёт в audit-log (шапка однажды выросла до 145KB — не
   повторять).
5. **Report** — blunt summary: counts per surface, fake %, top-3 worst
   findings, and what you did NOT cover.

## Output format — new `S###` row

```markdown
| **S###** | <short title> | `<file>:<line>` — `<snippet>`. <why it is slop>. <what to use instead>. <count>. | <priority> | [ ] Open |
```

Write findings like a human who found garbage, not a linter:

- **Bad:** "S241: Flat namespace detected. 194 files found."
- **Good:** "S241: `app/` is a flat dump of 194 files. `billing.py`,
  `billing_service.py`, `routers/billing.py`, `models/billing.py` —
  same domain in 4 places. You need grep to find anything."
- **Bad:** "S242: Simulated functionality in performance.py."
- **Good:** "S242: `performance.py` returns `random.randint(60, 95)`
  as a Lighthouse score. It's not running Lighthouse. It's a dice roll."

## Reporting rules — be brutally honest

- Flat dump → say "flat dump, no bounded contexts"
- Half the endpoints fake → say "feature factory, not a product"
- Tests verify nothing → say "these tests can't fail —
  `isinstance(result, dict)` passes for anything"
- AI over-generated → "created N abstraction classes when M would do —
  needs deletion, not a patch"
- Security risk → "silent auth failures, no rate limiting, untyped
  responses with no validation"
- **Quality code with no consumer** → say exactly that — the dominant
  AI-slop class is «настоящий код, которым никто не пользуется», and it
  is still slop.

**Never say:** "could benefit from improvements", "might need
attention", "consider refactoring".

## Restrictions

- **DO NOT run** test suites, builds, linters, package managers, docker
  — static analysis only.
- **DO NOT fix or refactor code.** Find and document only.
- **DO NOT delete files** — propose deletions as board rows.
- `exec` is for `git` and read-only counting commands only.
- Keep each docs commit under 1,000 changed lines.
