"""Tests for the local layer. Fixture payloads are written to tmp_path so
the scanner's own test file stays clean under self-scan."""

from pathlib import Path

from parsers.ast_scanner import scan_ast
from parsers.findings import Severity
from parsers.regex_scanner import scan_regex
from parsers.walker import iter_source_files
from report import exit_code, render_markdown


def _write(root: Path, rel: str, text: str) -> Path:
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")
    return p


def test_walker_respects_ignore_dirs(tmp_path):
    _write(tmp_path, "app.py", "x = 1\n")
    _write(tmp_path, "node_modules/dep/index.js", "y = 2\n")
    _write(tmp_path, ".git/config", "z\n")
    files = [
        p.name
        for p in iter_source_files(tmp_path, {".py", ".js"}, {"node_modules", ".git"}, set(), 256)
    ]
    assert files == ["app.py"]


def test_walker_size_cap(tmp_path):
    _write(tmp_path, "big.py", "x" * 3000 + "\n")
    files = list(iter_source_files(tmp_path, {".py"}, set(), set(), 1))
    assert files == []


def test_regex_finds_secret_in_env(tmp_path):
    p = _write(tmp_path, ".env", 'DB_PASSWORD = "s3cret-value"\n')
    hits = scan_regex(p, ".env", p.read_text())
    assert any(f.rule_id == "hardcoded-secret" and f.severity == Severity.CRITICAL for f in hits)


def test_ast_finds_hardcoded_and_print(tmp_path):
    src = 'password = "hunter2"\nprint(password)\n'
    p = _write(tmp_path, "app.py", src)
    hits = scan_ast(p, "app.py", src)
    rules = {f.rule_id for f in hits}
    assert "hardcoded-secret" in rules
    assert "print-secret" in rules
    assert all(f.severity == Severity.CRITICAL for f in hits)


def test_ast_silent_except_and_eval(tmp_path):
    src = "try:\n    risky()\nexcept Exception:\n    pass\n\neval(user_input)\n"
    p = _write(tmp_path, "x.py", src)
    rules = {f.rule_id for f in scan_ast(p, "x.py", src)}
    assert "silent-except" in rules
    assert "eval-exec" in rules


def test_regex_skips_ast_covered_rules_on_py(tmp_path):
    src = 'password = "hunter2"\n'
    p = _write(tmp_path, "app.py", src)
    assert scan_regex(p, "app.py", src) == []


def test_exit_code_threshold():
    assert exit_code([_mk_finding(Severity.HIGH)], "critical") == 0
    assert exit_code([_mk_finding(Severity.CRITICAL)], "critical") == 1
    assert exit_code([_mk_finding(Severity.LOW)], "never") == 0
    assert exit_code([], "low") == 0


def _mk_finding(sev):
    from parsers.findings import Finding

    return Finding("r", sev, "f", 1, "m")


def test_markdown_report_counts(tmp_path):
    findings = [_mk_finding(Severity.CRITICAL), _mk_finding(Severity.LOW)]
    md = render_markdown(findings, str(tmp_path))
    assert "CRITICAL: 1" in md and "LOW: 1" in md
