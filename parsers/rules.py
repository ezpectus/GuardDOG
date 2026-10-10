"""Regex rule table — single authority for line-level pattern checks.

`ast_covered=True` means ast_scanner reports the same issue with real
syntax context on .py files; the regex then applies only to other
extensions (configs, yaml, env, shell, sql...). Rules without the flag
run on every scanned file.
"""

from __future__ import annotations

import re
from typing import NamedTuple

from .findings import Severity


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
            r"\b\w*(password|passwd|pwd|secret|api_?key|token|private_?key"
            r"|client_?secret)\w*\s*[:=]\s*[\"'][^\"']{4,}[\"']",
            re.I,
        ),
        "hardcoded credential in source",
        ast_covered=True,
    ),
    Rule(
        "private-key-block",
        Severity.CRITICAL,
        re.compile(r"-----BEGIN (RSA |EC |DSA |OPENSSH |PGP )?PRIVATE KEY( BLOCK)?-----"),
        "private key material committed",
    ),
    Rule(
        "cloud-key",
        Severity.CRITICAL,
        re.compile(
            r"\b(AKIA[0-9A-Z]{16}|ghp_[0-9A-Za-z]{36}|gho_[0-9A-Za-z]{36}"
            r"|xox[baprs]-[0-9A-Za-z-]{10,}|sk-[0-9A-Za-z]{32,})\b"
        ),
        "known-format cloud/API token (AWS/GitHub/Slack/OpenAI)",
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
        ast_covered=True,
    ),
    Rule(
        "verify-false",
        Severity.HIGH,
        re.compile(r"\bverify\s*=\s*False\b"),
        "TLS certificate verification disabled",
        ast_covered=True,
    ),
    Rule(
        "pickle-load",
        Severity.HIGH,
        re.compile(r"\bpickle\.loads?\s*\("),
        "pickle deserialization of untrusted data risk",
        ast_covered=True,
    ),
    Rule(
        "yaml-load-unsafe",
        Severity.HIGH,
        re.compile(r"\byaml\.load\s*\([^)]*\)(?![^\n]*SafeLoader)"),
        "yaml.load without SafeLoader",
        ast_covered=True,
    ),
    Rule(
        "os-system",
        Severity.HIGH,
        re.compile(r"\bos\.system\s*\("),
        "os.system() — shell injection surface",
        ast_covered=True,
    ),
    Rule(
        "sql-format-exec",
        Severity.HIGH,
        re.compile(r"\bexecute\s*\(\s*(f[\"']|[\"'][^\"']*[\"']\s*%|\w+\s*\+)", re.I),
        "SQL built by formatting/concat — injection risk",
    ),
    Rule(
        "debug-enabled",
        Severity.MEDIUM,
        re.compile(r"\bdebug\s*=\s*True\b|\bDEBUG\s*=\s*1\b", re.I),
        "debug mode enabled in code/config",
        ast_covered=True,
    ),
    Rule(
        "bind-all-interfaces",
        Severity.MEDIUM,
        re.compile(r"[\"']0\.0\.0\.0[\"']|[\"']::[\"']"),
        "service bound to all interfaces",
    ),
    Rule(
        "weak-hash",
        Severity.MEDIUM,
        re.compile(r"\b(hashlib\.(md5|sha1)\s*\(|MD5\.new|createHash\(['\"](md5|sha1))", re.I),
        "weak hash (md5/sha1) — not for security use",
        ast_covered=True,
    ),
    Rule(
        "cors-wildcard",
        Severity.MEDIUM,
        re.compile(r"(Access-Control-Allow-Origin|allow_origins?)\s*[:=]\s*[\"']?\*"),
        "CORS wildcard origin",
    ),
    Rule(
        "todo-leftover",
        Severity.LOW,
        re.compile(r"\b(TODO|FIXME|HACK|XXX)\b"),  # guarddog: ignore todo-leftover
        "unresolved marker left in code",
    ),
    Rule(
        "commented-code",
        Severity.LOW,
        re.compile(r"^\s*#\s*(def |class |import |from |if |for |return |print\()", re.I),
        "commented-out code block",
    ),
]


AST_RULE_IDS = {r.rule_id for r in RULES if r.ast_covered}
