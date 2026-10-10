"""Regex layer: fast pattern rules applied line-by-line to source files.

Rules marked ast_covered are skipped for .py files — ast_scanner reports them
with real syntax context instead of raw text matching.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import NamedTuple

from .findings import Finding, Severity


class Rule(NamedTuple):
    rule_id: str
    severity: Severity
    pattern: re.Pattern[str]
    message: str
    ast_covered: bool = False


RULES: list[Rule] = [
    Rule(
        "hardcoded-secret",
        Severity.CRITICAL,
        re.compile(
            r'\b\w*(password|passwd|pwd|secret|api_?key|access_?token|auth_?token|private_?key)\w*\s*[:=]\s*["\'][^"\']{4,}["\']',
            re.I,
        ),
        "hardcoded credential in source",
        ast_covered=True,
    ),
    Rule(
        "print-secret",
        Severity.CRITICAL,
        re.compile(r"\bprint\s*\([^)]*\b(password|passwd|secret|token|api_?key)\b", re.I),
        "sensitive value printed to stdout",
        ast_covered=True,
    ),
    Rule(
        "eval-exec",
        Severity.HIGH,
        re.compile(r"\b(eval|exec)\s*\("),
        "eval/exec on dynamic input",
        ast_covered=True,
    ),
    Rule(
        "shell-true",
        Severity.HIGH,
        re.compile(r"\bshell\s*=\s*True\b"),
        "subprocess invoked with shell enabled",
    ),
    Rule(
        "verify-false",
        Severity.HIGH,
        re.compile(r"\bverify\s*=\s*False\b"),
        "TLS certificate verification disabled",
    ),
    Rule(
        "pickle-load",
        Severity.HIGH,
        re.compile(r"\bpickle\.loads?\s*\("),
        "pickle deserialization of untrusted data risk",
    ),
    Rule(
        "yaml-load-unsafe",
        Severity.HIGH,
        re.compile(r"\byaml\.load\s*\([^)]*\)(?![^\n]*SafeLoader)"),
        "yaml.load without SafeLoader",
    ),
    Rule(
        "private-key-block",
        Severity.CRITICAL,
        re.compile(r"-----BEGIN (RSA |EC |OPENSSH |PGP )?PRIVATE KEY-----"),
        "private key material committed",
    ),
    Rule(
        "debug-enabled",
        Severity.MEDIUM,
        re.compile(r"\bdebug\s*=\s*True\b|\bDEBUG\s*=\s*1\b", re.I),
        "debug mode enabled in code/config",
    ),
    Rule(
        "bind-all-interfaces",
        Severity.MEDIUM,
        re.compile(r'["\']0\.0\.0\.0["\']|["\']::["\']'),
        "service bound to all interfaces",
    ),
    Rule(
        "todo-leftover",
        Severity.LOW,
        re.compile(r"\b(TODO|FIXME|HACK|XXX)\b"),
        "unresolved marker left in code",
    ),
]


def scan_regex(path: Path, rel: str, text: str) -> list[Finding]:
    is_python = path.suffix.lower() == ".py"
    findings: list[Finding] = []
    for lineno, line in enumerate(text.splitlines(), start=1):
        for rule in RULES:
            if is_python and rule.ast_covered:
                continue
            if rule.pattern.search(line):
                findings.append(
                    Finding(
                        rule_id=rule.rule_id,
                        severity=rule.severity,
                        file=rel,
                        line=lineno,
                        message=rule.message,
                        snippet=line.strip()[:160],
                    )
                )
    return findings
