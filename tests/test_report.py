from parsers.findings import Finding, ScanResult, Severity
from report import render_json, render_markdown


def _result(tmp_path):
    r = ScanResult(target=str(tmp_path), files_scanned=3)
    r.findings = [
        Finding("hardcoded-secret", Severity.CRITICAL, "a.py", 1, "leak"),
        Finding("todo-leftover", Severity.LOW, "b.py", 5, "marker"),
    ]
    return r


def test_markdown_counts(tmp_path):
    md = render_markdown(_result(tmp_path))
    assert "CRITICAL: 1" in md and "LOW: 1" in md
    assert "a.py:1" in md


def test_json_structure(tmp_path):
    import json

    data = json.loads(render_json(_result(tmp_path)))
    assert data["counts"]["CRITICAL"] == 1
    assert data["findings"][0]["rule_id"] == "hardcoded-secret"
    assert data["files_scanned"] == 3


def test_exit_code_threshold(tmp_path):
    r = _result(tmp_path)
    assert r.exit_code("critical") == 1
    assert r.exit_code("low") == 1
    r.findings = [f for f in r.findings if f.severity < Severity.CRITICAL]
    assert r.exit_code("critical") == 0
    assert r.exit_code("never") == 0
