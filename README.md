# GuardDOG

[![Python](https://img.shields.io/badge/python-3.10%2B-blue?logo=python&logoColor=white)](https://www.python.org/)
[![License](https://img.shields.io/badge/license-MIT-green)](LICENSE)
[![Status](https://img.shields.io/badge/status-alpha-orange)]()
[![Runtime deps](https://img.shields.io/badge/runtime%20deps-zero-brightgreen)]()
[![CI gate](https://img.shields.io/badge/exit%20code-CI%20ready-red)]()
[![Tests](https://img.shields.io/badge/tests-26%20passed-brightgreen)](tests/)

**Hybrid repository scanner for the AI-generated-code era.** A local layer
(regex + AST) catches the obvious instantly and for free; an LLM layer
audits only the files that changed. Findings land in a report and in the
process exit code — a CRITICAL hit fails the build or blocks the commit.

One command in a terminal, a `run_all.bat`, a pre-commit hook, or a CI/CD
pipeline — the project gets checked *before* the incident, not after.

## The problem

AI-generated code looks clean: correct syntax, plausible names, green
tests. Underneath — `PASSWORD = "..."` shipped to prod,
`print(entered_pass)` in a log path, `verify=False` on a payment request.
Linters don't see it: they check style, not semantics. An LLM *can* see
it — but streaming the whole repo into a model on every commit is slow
and burns tokens.

GuardDOG sits in between: the local layer is free and instant, and the LLM
is invoked only on files whose hash changed since the last run — and only
when an API key is present. No key → honest `skipped` in the report, the
local layer still runs. No fake-green, ever.

## Pipeline

```
target repo
    │
    ▼
┌─ 1. WALKER ──────────── os.walk + .gitignore + config ignore-rules,
│        │                 extension allowlist, per-file size cap
│        ▼
├─ 2. LOCAL LAYER ──────── 17 regex rules (any language) +
│        │                 ~15 Python AST checks: hardcoded secrets,
│        │                 print(secret), eval/exec, shell=True,
│        │                 verify=False, pickle/yaml.load, os.system…
│        ▼
├─ 3. LLM LAYER (opt.) ─── key-file priority → SHA-256 cache →
│        │                  changed files only → Gemini / OpenAI-compat →
│        │                  strict-JSON findings merged into the result
│        ▼
└─ 4. REPORT + GATE ────── Markdown / JSON / HTML dashboard,
                           severity matrix, exit code by fail_on threshold
```

## Layout

```
GuardDOG/
├── main.py               # thin entry → cli.main()
├── cli.py                # subcommands: scan / install-hook / rules / cache
├── config.py             # config.json → .guarddog.json (target) → --config
├── report.py             # MD / JSON / HTML renderers + severity gate
├── config.json           # single authority: ignores, extensions, fail_on, llm
├── parsers/
│   ├── findings.py       # Finding + Severity (IntEnum) + ScanResult
│   ├── rules.py          # regex rule table — single source of truth
│   ├── regex_scanner.py  # applies the table line-by-line
│   ├── ast_scanner.py    # Python semantics via stdlib ast
│   └── walker.py         # repo walk with the ignore stack
├── llm_client/
│   ├── context.py        # SHA-256 cache + key-file priority ordering
│   └── client.py         # providers: gemini | openai-compatible
├── templates/
│   ├── system_prompt.md  # auditor system prompt (strict JSON contract)
│   └── report.html       # HTML dashboard template (string.Template)
└── tests/                # pytest: walker/regex/ast/report/cli/cache/hook
```

## Usage

```bash
# local layer only (offline, CI, pre-commit)
python main.py scan /path/to/project --no-llm

# full hybrid
export GUARDDOG_API_KEY=<gemini key>      # or OPENAI_API_KEY
python main.py scan /path/to/project

# CI gate: fail on high+, JSON artifact
python main.py scan . --fail-on high --format json -o report.json

# HTML dashboard
python main.py scan . --format html -o report.html

# install a pre-commit hook into a target repo
python main.py install-hook /path/to/project --fail-on high

# list rules / manage the LLM cache
python main.py rules
python main.py cache /path/to/project --clear
```

`guarddog <path>` without a subcommand is shorthand for `guarddog scan <path>`.

**Exit codes:** `0` — clean (below threshold) · `1` — a finding ≥ `fail_on`
exists · `2` — launch error (missing target, hook exists without `--force`).

## Local rules

| Rule | Sev | Detects |
|------|-----|---------|
| `hardcoded-secret` | CRITICAL | `password/api_key/token/secret = "..."` (AST + regex) |
| `private-key-block` | CRITICAL | `-----BEGIN ... PRIVATE KEY-----` committed |
| `cloud-key` | CRITICAL | AWS `AKIA…`, GitHub `ghp_`, Slack `xox*`, OpenAI `sk-` formats |
| `print-secret` | CRITICAL | `print(password)` — secret leaked to stdout |
| `eval-exec` | HIGH | `eval()` / `exec()` on dynamic input |
| `shell-true` | HIGH | `subprocess(..., shell=True)` |
| `verify-false` | HIGH | `verify=False` — TLS verification off |
| `pickle-load` | HIGH | `pickle.load/loads` on untrusted data |
| `yaml-load-unsafe` | HIGH | `yaml.load` without `Loader=` |
| `os-system` | HIGH | `os.system()` — shell injection surface |
| `sql-format-exec` | HIGH | `execute(f"…")` / `%` / string-concat into SQL |
| `debug-enabled` | MEDIUM | `debug=True` / `DEBUG=1` in code or config |
| `bind-all-interfaces` | MEDIUM | binding to `0.0.0.0` |
| `weak-hash` | MEDIUM | `hashlib.md5/sha1`, `createHash('md5')` |
| `cors-wildcard` | MEDIUM | `Access-Control-Allow-Origin: *` |
| `silent-except` | MEDIUM | `except: pass` / `...` bodies (AST) |
| `insecure-tempfile` | MEDIUM | `tempfile.mktemp` — racy |
| `todo-leftover`, `commented-code`, `star-import`, `assert-in-prod`, `long-function` | LOW | hygiene |

On `.py` files, rules marked `ast_covered` are delegated to the AST layer —
one finding, one layer, no duplicates.

## Inline suppression

Kill a false positive where it lives — a comment on the same line:

```python
API_KEY = "test-fixture"   # guarddog: ignore hardcoded-secret
LEGACY = "..."             # guarddog: ignore   ← suppresses all rules on the line
```

Works for both regex and AST findings.

## Configuration

Three layers, later wins (dicts merge, lists append-unique, scalars replace):

1. `config.json` next to the scanner — shipped defaults
2. `.guarddog.json` at the **scanned project** root — per-repo rules
3. `--config <path>` — explicit override

| Key | Controls |
|-----|----------|
| `ignore_dirs` / `ignore_files` | what to skip (target `.gitignore` honored too) |
| `scan_extensions` | file extensions/names to scan |
| `max_file_size_kb` | per-file size cap (default 256) |
| `fail_on` | exit-1 threshold (default `critical`; `never` = always 0) |
| `llm.provider` | `gemini` \| `openai` (`base_url` → Groq/Together/llama.cpp) |
| `llm.model` / `llm.max_files` / `llm.timeout_sec` | LLM layer knobs |

## LLM layer — honest by design

- Keys: `GUARDDOG_API_KEY` → `GEMINI_API_KEY` / `OPENAI_API_KEY`.
- No key → `skipped — no key` in the report; local findings still gate.
- API failure → `skipped — <error>` in the report. A failure is never "clean".
- `.guarddog_cache.json` at the target root; payload = changed files only,
  priority to `models/settings/auth/compose/Dockerfile/…`.
- Cache is committed **only after a real API response** — otherwise a skip
  would get memoized as if it were an audit.

## Principles

- **Verify, don't trust** — every finding carries file:line, no speculation.
- **Fail-closed** — scanner errors surface in the report, never swallowed.
- **Zero runtime deps** — stdlib only: `ast`, `re`, `urllib`, `argparse`.

## Roadmap

- [x] Local layer: 17 regex rules + ~15 AST checks, severity, exit gate
- [x] CLI: `scan` / `install-hook` / `rules` / `cache`, bare-path shorthand
- [x] Reports: Markdown, JSON, self-contained HTML dashboard
- [x] LLM layer: Gemini + OpenAI-compatible providers, SHA-256 context
      cache, key-file priority, strict-JSON parsing
- [x] Per-target config (`.guarddog.json`), inline suppression comments
- [x] Pre-commit hook installer (`install-hook`)
- [ ] Live LLM run against a real key + JSON-schema validation with retry
- [ ] AST rules for JS/TS (tree-sitter)
- [ ] Go rewrite → single binary, when Python hits the wall

## License

MIT — see [LICENSE](LICENSE).
