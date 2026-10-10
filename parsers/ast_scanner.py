"""AST layer: semantic checks for Python files (stdlib ast only).

Each check produces the same rule_ids as the ast_covered regex rules, so a
.py file is never double-reported. AST-only extras: silent-except,
star-import, long-function, assert-in-prod, insecure-tempfile.
"""

from __future__ import annotations

import ast
import dataclasses
import re
from pathlib import Path

from .findings import Finding, Severity
from .regex_scanner import suppressed
from .rules import HINTS

SECRET_NAME = re.compile(
    r"password|passwd|pwd|secret|api_?key|token|private_?key|client_?secret",
    re.I,
)
MAX_FUNC_LINES = 50
TEST_PATH = re.compile(r"(^|/)(tests?|testing|conftest)(/|$)|_test\.py$|test_.*\.py$")


def _call_name(node: ast.Call) -> str:
    f = node.func
    if isinstance(f, ast.Name):
        return f.id
    if isinstance(f, ast.Attribute):
        base = f.value.id if isinstance(f.value, ast.Name) else ""
        return f"{base}.{f.attr}" if base else f.attr
    return ""


def _kw_true(node: ast.Call, name: str) -> bool:
    return any(
        kw.arg == name and isinstance(kw.value, ast.Constant) and kw.value.value is True
        for kw in node.keywords
    )


def _kw_false(node: ast.Call, name: str) -> bool:
    return any(
        kw.arg == name and isinstance(kw.value, ast.Constant) and kw.value.value is False
        for kw in node.keywords
    )


def _secret_assign(node: ast.AST) -> tuple[int, str] | None:
    if not isinstance(node, (ast.Assign, ast.AnnAssign)):
        return None
    value = node.value
    if not (
        isinstance(value, ast.Constant) and isinstance(value.value, str) and len(value.value) >= 4
    ):
        return None
    targets = node.targets if isinstance(node, ast.Assign) else [node.target]
    for t in targets:
        name = t.id if isinstance(t, ast.Name) else t.attr if isinstance(t, ast.Attribute) else ""
        if name and SECRET_NAME.search(name):
            return node.lineno, name
    return None


def _check_call(node: ast.Call, rel: str, lines: list[str]) -> list[Finding]:
    name = _call_name(node)
    line = node.lineno
    snip = lines[line - 1].strip()[:160]

    def f(rule_id: str, sev: Severity, msg: str) -> Finding:
        return Finding(rule_id, sev, rel, line, msg, snip)

    if name in ("eval", "exec"):
        return [f("eval-exec", Severity.HIGH, f"{name}() on dynamic input")]
    if name == "print":
        for arg in node.args:
            leaked = (
                arg.id
                if isinstance(arg, ast.Name)
                else arg.attr
                if isinstance(arg, ast.Attribute)
                else ""
            )
            if leaked and SECRET_NAME.search(leaked):
                return [f("print-secret", Severity.CRITICAL, f"print() leaks `{leaked}`")]
        return []
    if name == "os.system":
        return [f("os-system", Severity.HIGH, "os.system() — shell injection surface")]
    if name == "os.popen":
        # os.popen has no shell= kwarg — it is always a shell
        return [f("os-system", Severity.HIGH, "os.popen() — shell injection surface")]
    if name.startswith("subprocess.") and _kw_true(node, "shell"):
        return [f("shell-true", Severity.HIGH, "subprocess invoked with shell enabled")]
    if _kw_false(node, "verify"):
        return [f("verify-false", Severity.HIGH, "TLS certificate verification disabled")]
    if name == "pickle.loads" or name == "pickle.load":
        return [f("pickle-load", Severity.HIGH, "pickle deserialization of untrusted data risk")]
    if name == "yaml.load" and not any(kw.arg == "Loader" for kw in node.keywords):
        return [f("yaml-load-unsafe", Severity.HIGH, "yaml.load without SafeLoader")]
    if name in ("hashlib.md5", "hashlib.sha1"):
        return [f("weak-hash", Severity.MEDIUM, f"{name}() — weak hash for security use")]
    if name == "tempfile.mktemp":
        return [
            f("insecure-tempfile", Severity.MEDIUM, "mktemp is racy — use mkstemp/TemporaryFile")
        ]
    if _kw_true(node, "debug"):
        return [f("debug-enabled", Severity.MEDIUM, "debug mode enabled in call")]
    return []


def _check_node(node: ast.AST, rel: str, lines: list[str], is_test: bool) -> list[Finding]:
    hit = _secret_assign(node)
    if hit:
        lineno, name = hit
        return [
            Finding(
                "hardcoded-secret",
                Severity.CRITICAL,
                rel,
                lineno,
                f"hardcoded credential assigned to `{name}`",
                lines[lineno - 1].strip()[:160],
            )
        ]

    if isinstance(node, ast.Call):
        return _check_call(node, rel, lines)
    return _check_misc(node, rel, lines, is_test)


def _check_misc(node: ast.AST, rel: str, lines: list[str], is_test: bool) -> list[Finding]:
    def f(rule_id: str, sev: Severity, line: int, msg: str) -> Finding:
        return Finding(rule_id, sev, rel, line, msg, lines[line - 1].strip()[:160])

    if (
        isinstance(node, ast.ExceptHandler)
        and len(node.body) == 1
        and isinstance(node.body[0], (ast.Pass, ast.Expr))
    ):
        return [
            f(
                "silent-except",
                Severity.MEDIUM,
                node.lineno,
                "exception swallowed (pass/ellipsis body)",
            )
        ]

    if isinstance(node, ast.ImportFrom) and any(a.name == "*" for a in node.names):
        return [f("star-import", Severity.LOW, node.lineno, f"from {node.module or '?'} import *")]

    if isinstance(node, ast.Assert) and not is_test:
        return [
            f(
                "assert-in-prod",
                Severity.LOW,
                node.lineno,
                "assert in non-test code — stripped under python -O",
            )
        ]

    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
        length = (node.end_lineno or node.lineno) - node.lineno + 1
        if length > MAX_FUNC_LINES:
            return [
                f(
                    "long-function",
                    Severity.LOW,
                    node.lineno,
                    f"function `{node.name}` is {length} lines (limit {MAX_FUNC_LINES})",
                )
            ]
    return []


def scan_ast(path: Path, rel: str, text: str) -> list[Finding]:
    try:
        tree = ast.parse(text, filename=rel)
    except SyntaxError:
        return []
    lines = text.splitlines()
    is_test = bool(TEST_PATH.search(rel.replace("\\", "/")))
    findings: list[Finding] = []
    for node in ast.walk(tree):
        findings.extend(_check_node(node, rel, lines, is_test))
    kept = [f for f in findings if not suppressed(lines[f.line - 1], f.rule_id)]
    return [dataclasses.replace(f, recommendation=HINTS.get(f.rule_id, "")) for f in kept]
