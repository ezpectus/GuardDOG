# AGENTS.md — Operating Manual

> Закон проекта: verified facts, не аспирации. Каждое утверждение —
> file:line или команда проверки. Секции `{{...}}` заполняются при
> adoption (инструкция — `agents-workflow/ADOPT.md`). Пустое честнее
> выдуманного.

**Работаешь? Выполняй `.devin/WORKFLOW.md`** — единственный driving loop
(orient → route → pick → do → verify → record → commit). Роли в
`.devin/workflows/` — спец-режимы под ним; их `README.md` читать первым.

## Что это за проект

{{2-4 строки: что система реально делает, стек, версии}}

## Архитектура — verified truth

{{Слои, entrypoints, state seams (где живёт состояние), кто хозяин схемы
данных, execution-модель (sync/async/worker). Каждый пункт — file:line.
«Модульный монолит, не microservices» честнее, чем красивая диаграмма
из README.}}

## Target architecture — north-star

{{Куда проект движется. Load-failure map: что умрёт первым —
2 реплики? 10x RPS? restart/deploy? shared state?}}

**Conformance rule:** перед merge спроси — дифф добавляет process-local
state, абстракцию без потребителя, endpoint без клиента, второй движок
существующего контура? Да → не делай, или запиши причину в этот файл.

## Confirmed defects — fix order

{{Только доказанные дефекты: приоритет, симптом, file:line, есть ли
тест-ловушка. Нет → «—».}}

## Design rules

- **KISS/YAGNI** — минимальный корректный дифф; абстракция — со вторым
  потребителем; паттерн — только если уже канон в этом коде, а не
  «по учебнику».
- **DRY** — две копии предиката/модели/сторежка = один латентный баг;
  слить или назвать authority.
- **Fail-loud на деньгах/тенантности, fail-closed на security** —
  catch-log-continue запрещён в этих путях.
- **Антипаттерны на охоту:** process-local state как shared; dual-write/
  read-merge stores; мёртвые feature-flags; «legacy» без плана миграции;
  endpoint/абстракция без потребителя.
- **Вопросы ≠ гадать** — блок/неоднозначность → `.devin/QUESTIONS.md`.

## Conventions — наблюдаемые, не желаемые

{{Фактические паттерны кода: naming, структура модулей, обработка
ошибок, логирование, тест-стиль. Выписано из чтения файлов домена,
не из фантазии.}}

## Anti-slop rules

- Никаких новых доменов/абстракций без потребителя.
- Не меть `Legacy`/`deprecated` то, что wired в DI/entrypoints.
- Не раздувать barrels (`__init__`/index-реэкспорты).
- Не второй engine/facade на существующий контур.
- Не контракты, которые не держишь: watchdog-тесты без зубов хуже их
  отсутствия.
- Локальные import'ы внутри функций — только против import-циклов.
- Комментарии не добавлять и не удалять без запроса; маркеры ран
  (`S###`, `#N`, `Q-###`) — реальные инциденты, не трогать.

## Generated-code signatures — recurring wounds

Канон — `.devin/SIGNATURES.md`: классы дефектов с grep-сигнатурой и
направлением фикса. Новая повторяющаяся рана → новый класс туда с датой.
Перед похожей правкой — сначала сверься с каталогом.

## Verification commands

```bash
{{GATES: lint, format-check, tests (полный + scoped), typecheck, build —
реально работающие команды. env-blocked → команда разблокировки рядом.}}
```
