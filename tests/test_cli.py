"""End-to-end CLI tests: scan pipeline, config merge, hook, cache."""

import json
import os
import shutil
import sys
from pathlib import Path

import pytest

import cli
from llm_client.context import build_llm_context, save_cache
from parsers.findings import Severity

ROOT = Path(__file__).resolve().parent.parent


def _plant(root: Path):
    (root / "app.py").write_text(
        'db_password = "s3cret"\nprint(db_password)\nimport os\nos.system("ls")\n',
        encoding="utf-8",
    )
    (root / "config.yaml").write_text("debug: true\n", encoding="utf-8")


def test_scan_finds_planted_vulns(tmp_path):
    _plant(tmp_path)
    code = cli.main(["scan", str(tmp_path), "--no-llm", "--quiet", "--fail-on", "critical"])
    assert code == 1
    report_file = tmp_path / "guarddog_report.md"
    assert report_file.is_file()
    text = report_file.read_text(encoding="utf-8")
    assert "hardcoded-secret" in text and "print-secret" in text


def test_scan_clean_target_exit_zero(tmp_path):
    (tmp_path / "ok.py").write_text("x = 1\n", encoding="utf-8")
    code = cli.main(["scan", str(tmp_path), "--no-llm", "--quiet"])
    assert code == 0


def test_scan_json_format(tmp_path):
    _plant(tmp_path)
    out = tmp_path / "r.json"
    cli.main(["scan", str(tmp_path), "--no-llm", "--quiet", "--format", "json", "-o", str(out)])
    data = json.loads(out.read_text(encoding="utf-8"))
    assert data["counts"]["CRITICAL"] >= 2


def test_target_guarddog_json_overrides(tmp_path):
    _plant(tmp_path)
    (tmp_path / ".guarddog.json").write_text(json.dumps({"fail_on": "never"}), encoding="utf-8")
    code = cli.main(["scan", str(tmp_path), "--no-llm", "--quiet"])
    assert code == 0


def test_bare_path_shorthand(tmp_path):
    (tmp_path / "ok.py").write_text("x = 1\n", encoding="utf-8")
    assert cli.main([str(tmp_path), "--no-llm", "--quiet"]) == 0


def test_install_hook(tmp_path):
    (tmp_path / ".git" / "hooks").mkdir(parents=True)
    assert cli.main(["install-hook", str(tmp_path), "--fail-on", "high"]) == 0
    hook = tmp_path / ".git" / "hooks" / "pre-commit"
    assert hook.is_file() and "guarddog" in hook.read_text(encoding="utf-8")
    assert os.access(hook, os.X_OK) or sys.platform == "win32"


def test_hook_refuses_overwrite(tmp_path):
    hooks = tmp_path / ".git" / "hooks"
    hooks.mkdir(parents=True)
    (hooks / "pre-commit").write_text("#!/bin/sh\n", encoding="utf-8")
    assert cli.main(["install-hook", str(tmp_path)]) == 2
    assert cli.main(["install-hook", str(tmp_path), "--force"]) == 0


def test_cache_skips_unchanged(tmp_path):
    f = tmp_path / "a.py"
    f.write_text("x = 1\n", encoding="utf-8")
    payload, unchanged, cache = build_llm_context(tmp_path, [f], 40)
    assert len(payload) == 1 and unchanged == []
    save_cache(tmp_path, cache)
    payload, unchanged, _ = build_llm_context(tmp_path, [f], 40)
    assert payload == [] and unchanged == ["a.py"]
    f.write_text("x = 2\n", encoding="utf-8")
    payload, unchanged, _ = build_llm_context(tmp_path, [f], 40)
    assert len(payload) == 1


def test_llm_skipped_without_key(tmp_path, monkeypatch):
    monkeypatch.delenv("GUARDDOG_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    f = tmp_path / "a.py"
    f.write_text("x = 1\n", encoding="utf-8")
    code = cli.main(["scan", str(tmp_path), "--quiet"])
    assert code == 0
    text = (tmp_path / "guarddog_report.md").read_text(encoding="utf-8")
    assert "skipped" in text


def test_rules_command(capsys):
    assert cli.main(["rules"]) == 0
    out = capsys.readouterr().out
    assert "hardcoded-secret" in out and "CRITICAL" in out


def test_findings_deduped_on_merge(tmp_path):
    from parsers.findings import Finding, ScanResult

    r = ScanResult(target=str(tmp_path), files_scanned=1)
    f = Finding("hardcoded-secret", Severity.CRITICAL, "a.py", 1, "x")
    r.add([f])
    r.add([f, Finding("hardcoded-secret", Severity.CRITICAL, "a.py", 1, "y")])
    r.add([Finding("hardcoded-secret", Severity.CRITICAL, "a.py", 2, "z")])
    assert len(r.findings) == 2


def test_unknown_config_key_warns(tmp_path, capsys):
    (tmp_path / "x.py").write_text("x = 1\n", encoding="utf-8")
    (tmp_path / ".guarddog.json").write_text(
        json.dumps({"ignore_dirz": ["x"], "fail_on": "never"}), encoding="utf-8"
    )
    cli.main(["scan", str(tmp_path), "--no-llm", "--quiet"])
    assert "ignore_dirz" in capsys.readouterr().err


def test_check_command_reports_scan_plan(tmp_path, capsys):
    _plant(tmp_path)
    assert cli.main(["check", str(tmp_path)]) == 0
    out = capsys.readouterr().out
    assert "files scanned:" in out and "llm payload:" in out
    assert "threat model:  none" in out


def test_threat_model_reaches_llm_prompt(tmp_path, monkeypatch):
    (tmp_path / "a.py").write_text("x = 1\n", encoding="utf-8")
    (tmp_path / "threat_model.md").write_text(
        "post-auth SQLi = HIGH, never CRITICAL", encoding="utf-8"
    )
    captured = {}

    def fake_audit(prompt, payload, cfg):
        captured["prompt"] = prompt
        from llm_client.client import LLMResult

        return LLMResult([], skipped_reason="captured")

    monkeypatch.setattr("llm_client.client.audit", fake_audit)
    cli.main(["scan", str(tmp_path), "--quiet"])
    assert "post-auth SQLi" in captured["prompt"]


def test_llm_fix_field_parsed():
    from llm_client.client import _to_findings

    findings = _to_findings(
        [
            {
                "rule_id": "x",
                "severity": "high",
                "file": "a.py",
                "line": 1,
                "message": "m",
                "fix": "rotate the key",
            }
        ]
    )
    assert findings[0].recommendation == "rotate the key"


def test_report_has_fix_column(tmp_path):
    _plant(tmp_path)
    cli.main(["scan", str(tmp_path), "--no-llm", "--quiet"])
    text = (tmp_path / "guarddog_report.md").read_text(encoding="utf-8")
    assert "| Fix |" in text and "secrets manager" in text


def test_bad_fail_on_in_config_exits_2(tmp_path):
    (tmp_path / "x.py").write_text("x = 1\n", encoding="utf-8")
    (tmp_path / ".guarddog.json").write_text(json.dumps({"fail_on": "banana"}), encoding="utf-8")
    assert cli.main(["scan", str(tmp_path), "--no-llm", "--quiet"]) == 2


def test_malformed_config_exits_2_not_traceback(tmp_path, capsys):
    (tmp_path / "x.py").write_text("x = 1\n", encoding="utf-8")
    (tmp_path / ".guarddog.json").write_text("{not json", encoding="utf-8")
    with pytest.raises(SystemExit) as e:
        cli.main(["scan", str(tmp_path), "--no-llm", "--quiet"])
    assert e.value.code == 2
    assert "bad config" in capsys.readouterr().err


def test_suppression_is_token_not_substring(tmp_path):
    from parsers.regex_scanner import suppressed

    assert suppressed("x  # guarddog: ignore eval", "eval")
    assert not suppressed("x  # guarddog: ignore eval", "eval-exec")
    assert suppressed("x  # guarddog: ignore eval-exec,os-system", "os-system")


@pytest.mark.skipif(not shutil.which("git"), reason="git not installed")
def test_staged_mode_scans_only_staged(tmp_path):
    import subprocess

    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    (tmp_path / "vuln.py").write_text('token = "abc12345"\n', encoding="utf-8")
    (tmp_path / "clean.py").write_text("x = 1\n", encoding="utf-8")
    # nothing staged -> clean
    assert cli.main(["scan", str(tmp_path), "--staged", "--no-llm", "--quiet"]) == 0
    # stage only the clean file -> still clean
    subprocess.run(["git", "add", "clean.py"], cwd=tmp_path, check=True)
    assert cli.main(["scan", str(tmp_path), "--staged", "--no-llm", "--quiet"]) == 0
    # stage the vulnerable file -> critical hits the gate
    subprocess.run(["git", "add", "vuln.py"], cwd=tmp_path, check=True)
    assert cli.main(["scan", str(tmp_path), "--staged", "--no-llm", "--quiet"]) == 1


@pytest.mark.skipif(not shutil.which("git"), reason="git not installed")
def test_staged_mode_from_subdirectory(tmp_path):
    """git reports repo-root-relative paths; target=subdir must still match."""
    import subprocess

    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    sub = tmp_path / "pkg"
    sub.mkdir()
    (sub / "vuln.py").write_text('token = "abc12345"\n', encoding="utf-8")
    (tmp_path / "clean.py").write_text("x = 1\n", encoding="utf-8")
    subprocess.run(["git", "add", "."], cwd=tmp_path, check=True)
    # scanning the SUBDIR staged must see pkg/vuln.py (repo-relative path)
    assert cli.main(["scan", str(sub), "--staged", "--no-llm", "--quiet"]) == 1
