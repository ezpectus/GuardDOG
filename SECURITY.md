# Security Policy

## Reporting a vulnerability

GuardDOG is itself a security tool — if you find a bug in it (a rule that
misfires dangerously, a finding-suppression bypass, a way the scanner leaks
data), please report it privately:

- Open a [security advisory](https://github.com/ezpectus/GuardDOG/security/advisories/new)
- Do **not** open a public issue for vulnerabilities.

## Scope notes

- Scan reports may contain fragments of detected secrets — report files are
  local artifacts of the scanned repo; do not commit or publish them.
- GuardDOG never executes target code (text + `ast.parse` only) and never
  sends code anywhere without an explicitly configured LLM API key.
- `.guarddog_cache.json` stores SHA-256 hashes of file contents, not the
  contents themselves.
