# Contributing

GuardDOG is intentionally small and dependency-free. Before sending a PR:

## Rules of the house

- **Zero runtime deps** — stdlib only (`ast`, `re`, `urllib`, `argparse`).
  A new dependency needs a very good reason.
- **One table per truth** — regex rules live in `parsers/rules.py`, hints in
  `HINTS`, scanners register in `parsers/scanners.py`. No second engines.
- **Every rule needs a test** — fixtures go in `tmp_path`; test sources must
  not themselves trip the scanner (self-scan must stay at 0 findings).
- **Fail-closed** — errors surface in the report (`skipped_reason`), never
  swallowed.
- **No abstractions without a consumer** — extension points exist
  (`SCANNERS` registry); use them, don't add new layers.

## Gates (must be green)

```bash
ruff check .
ruff format --check .
pytest tests/ -q
python main.py scan . --no-llm --quiet   # self-scan → 0 findings
```

## How to add things

| Want | Touch |
|---|---|
| Regex rule | one `Rule(...)` in `rules.py` + `HINTS` entry + test |
| Python AST check | branch in `_check_node`/`_check_call` + `HINTS` + test |
| New language | `parsers/<lang>_scanner.py` + register in `SCANNERS` |
| LLM provider | function in `llm_client/client.py` + `PROVIDERS` entry |
