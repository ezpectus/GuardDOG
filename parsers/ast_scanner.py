"""AST layer: semantic checks for Python files (stdlib ast only)."""

from __future__ import annotations

import ast
import re
from pathlib import Path

from .findings import Finding, Severity

SECRET_NAME = re.compile(r"password|passwd|pwd|secret|api_?key|token|private_?key", re.I)
MAX_FUNC_LINES = 50


def _is_secret_str_assign(node: ast.AST) -> tuple[int, str] | None:
    if not isinstance(node, (ast.Assign, ast.AnnAssign)):
        return None
    value = node.value if isinstance(node, ast.AnnAssign) else node.value
    if not (
        isinstance(value, ast.Constant) and isinstance(value.value, str) and len(value.value) >= 4
    ):
        return None
    targets = node.targets if isinstance(node, ast.Assign) else [node.target]
    for t in targets:
        name = ""
        if isinstance(t, ast.Name):
            name = t.id
        elif isinstance(t, ast.Attribute):
            name = t.attr
        if name and SECRET_NAME.search(name):
            return node.lineno, name
    return None


def _call_name(node: ast.Call) -> str:
    f = node.func
    if isinstance(f, ast.Name):
        return f.id
    if isinstance(f, ast.Attribute):
        return f.attr
    return ""


def _check_node(node: ast.AST, rel: str, lines: list[str]) -> list[Finding]:
    findings: list[Finding] = []
    hit = _is_secret_str_assign(node)
    if hit:
        lineno, name = hit
        findings.append(
            Finding(
                "hardcoded-secret",
                Severity.CRITICAL,
                rel,
                lineno,
                f"hardcoded credential assigned to `{name}`",
                lines[lineno - 1].strip()[:160],
            )
        )
        return findings

    if isinstance(node, ast.Call):
        name = _call_name(node)
        if name in ("eval", "exec"):
            findings.append(
                Finding(
                    "eval-exec",
                    Severity.HIGH,
                    rel,
                    node.lineno,
                    f"{name}() on dynamic input",
                    lines[node.lineno - 1].strip()[:160],
                )
            )
        elif name == "print":
            for arg in node.args:
                if isinstance(arg, ast.Name) and SECRET_NAME.search(arg.id):
                    findings.append(
                        Finding(
                            "print-secret",
                            Severity.CRITICAL,
                            rel,
                            node.lineno,
                            f"print() leaks `{arg.id}`",
                            lines[node.lineno - 1].strip()[:160],
                        )
                    )
                    break

    if (
        isinstance(node, ast.ExceptHandler)
        and len(node.body) == 1
        and isinstance(node.body[0], (ast.Pass, ast.Expr))
    ):
        findings.append(
            Finding(
                "silent-except",
                Severity.MEDIUM,
                rel,
                node.lineno,
                "exception swallowed (pass/ellipsis body)",
                lines[node.lineno - 1].strip()[:160],
            )
        )

    if isinstance(node, ast.ImportFrom) and any(a.name == "*" for a in node.names):
        findings.append(
            Finding(
                "star-import",
                Severity.LOW,
                rel,
                node.lineno,
                f"from {node.module or '?'} import *",
                lines[node.lineno - 1].strip()[:160],
            )
        )

    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
        length = (node.end_lineno or node.lineno) - node.lineno + 1
        if length > MAX_FUNC_LINES:
            findings.append(
                Finding(
                    "long-function",
                    Severity.LOW,
                    rel,
                    node.lineno,
                    f"function `{node.name}` is {length} lines (limit {MAX_FUNC_LINES})",
                    node.name,
                )
            )
    return findings


def scan_ast(path: Path, rel: str, text: str) -> list[Finding]:
    try:
        tree = ast.parse(text, filename=rel)
    except SyntaxError:
        return []
    lines = text.splitlines()
    findings: list[Finding] = []
    for node in ast.walk(tree):
        findings.extend(_check_node(node, rel, lines))
    return findings
