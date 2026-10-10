"""End-to-end CLI tests: scan pipeline, config merge, hook, cache."""

import json
import os
import sys
from pathlib import Path

import cli
from llm_client.context import build_llm_context, save_cache

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
