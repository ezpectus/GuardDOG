"""Walker/regex/AST tests. Payloads are written to tmp_path so the
scanner's own test file stays clean under self-scan."""

from pathlib import Path

from parsers.ast_scanner import scan_ast
from parsers.findings import Severity
from parsers.regex_scanner import scan_regex
from parsers.walker import iter_source_files


def _write(root: Path, rel: str, text: str) -> Path:
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")
    return p


# --- walker ---


def test_walker_respects_ignore_dirs(tmp_path):
    _write(tmp_path, "app.py", "x = 1\n")
    _write(tmp_path, "node_modules/dep/index.js", "y = 2\n")
    _write(tmp_path, ".git/config", "z\n")
    files = [
        p.name
        for p in iter_source_files(tmp_path, {".py", ".js"}, {"node_modules", ".git"}, set(), 256)
    ]
    assert files == ["app.py"]


def test_walker_honors_gitignore(tmp_path):
    _write(tmp_path, ".gitignore", "*.log\nbuild/\n")
    _write(tmp_path, "ok.py", "x = 1\n")
    _write(tmp_path, "build/out.py", "y = 2\n")
    _write(tmp_path, "debug.log", "z\n")
    files = [p.name for p in iter_source_files(tmp_path, {".py", ".log"}, set(), set(), 256)]
    assert files == ["ok.py"]


def test_walker_size_cap(tmp_path):
    _write(tmp_path, "big.py", "x" * 3000 + "\n")
    assert list(iter_source_files(tmp_path, {".py"}, set(), set(), 1)) == []


# --- regex ---


def test_regex_finds_secret_in_env(tmp_path):
    p = _write(tmp_path, ".env", 'DB_PASSWORD = "s3cret-value"\n')
    hits = scan_regex(p, ".env", p.read_text())
    assert any(f.rule_id == "hardcoded-secret" and f.severity == Severity.CRITICAL for f in hits)


def test_regex_cloud_key_format(tmp_path):
    p = _write(tmp_path, "deploy.sh", 'KEY="AKIA' + "A" * 16 + '"\n')
    hits = scan_regex(p, "deploy.sh", p.read_text())
    assert any(f.rule_id == "cloud-key" for f in hits)


def test_regex_private_key_block(tmp_path):
    key_literal = "-----BEGIN RSA " "PRIVATE KEY-----\n"
    p = _write(tmp_path, "id_rsa.txt", key_literal)
    hits = scan_regex(p, "id_rsa.txt", p.read_text())
    assert any(f.rule_id == "private-key-block" for f in hits)


def test_regex_skips_ast_covered_on_py(tmp_path):
    src = 'password = "hunter2"\n'
    p = _write(tmp_path, "app.py", src)
    assert scan_regex(p, "app.py", src) == []


# --- ast ---


def test_ast_finds_hardcoded_and_print(tmp_path):
    src = 'password = "hunter2"\nprint(password)\n'
    p = _write(tmp_path, "app.py", src)
    hits = scan_ast(p, "app.py", src)
    rules = {f.rule_id for f in hits}
    assert "hardcoded-secret" in rules
    assert "print-secret" in rules
    assert all(f.severity == Severity.CRITICAL for f in hits)


def test_ast_call_checks(tmp_path):
    src = (
        "import subprocess, requests, yaml, hashlib, os\n"
        "subprocess.run(cmd, shell=True)\n"
        "requests.get(u, verify=False)\n"
        "yaml.load(data)\n"
        "hashlib.md5(b'x')\n"
        "os.system(cmd)\n"
        "eval(src)\n"
    )
    p = _write(tmp_path, "x.py", src)
    rules = {f.rule_id for f in scan_ast(p, "x.py", src)}
    assert {
        "shell-true",
        "verify-false",
        "yaml-load-unsafe",
        "weak-hash",
        "os-system",
        "eval-exec",
    } <= rules


def test_ast_silent_except(tmp_path):
    src = "try:\n    risky()\nexcept Exception:\n    pass\n"
    p = _write(tmp_path, "x.py", src)
    assert any(f.rule_id == "silent-except" for f in scan_ast(p, "x.py", src))


def test_ast_assert_skipped_in_tests(tmp_path):
    src = "def f():\n    assert x\n"
    assert any(f.rule_id == "assert-in-prod" for f in scan_ast(tmp_path, "app.py", src))
    assert not any(
        f.rule_id == "assert-in-prod" for f in scan_ast(tmp_path, "tests/test_a.py", src)
    )


def test_ast_syntax_error_is_clean(tmp_path):
    assert scan_ast(tmp_path, "broken.py", "def (:\n") == []


def test_ast_os_popen_flagged(tmp_path):
    src = "import os\nos.popen(cmd)\n"
    p = _write(tmp_path, "x.py", src)
    assert any(f.rule_id == "os-system" for f in scan_ast(p, "x.py", src))


def test_ast_print_attribute_secret(tmp_path):
    src = "print(self.api_key)\n"
    p = _write(tmp_path, "x.py", src)
    assert any(f.rule_id == "print-secret" for f in scan_ast(p, "x.py", src))


def test_yaml_safeloader_not_flagged(tmp_path):
    # regex must check args inside the parens, not after the call
    src = "yaml.load(stream, Loader=SafeLoader)\n"
    p = _write(tmp_path, "x.yaml", src)
    assert not any(f.rule_id == "yaml-load-unsafe" for f in scan_regex(p, "x.yaml", src))
    bad = "yaml.load(stream)\n"
    assert any(f.rule_id == "yaml-load-unsafe" for f in scan_regex(p, "x.yaml", bad))


def test_suppression_marker(tmp_path):
    p = _write(
        tmp_path,
        ".env",
        'API_KEY = "abc12345"  # guarddog: ignore hardcoded-secret\n'
        'SECRET = "def67890"  # guarddog: ignore\n'
        'TOKEN = "ghi11111"\n',
    )
    hits = scan_regex(p, ".env", p.read_text())
    assert [f.line for f in hits if f.rule_id == "hardcoded-secret"] == [3]
