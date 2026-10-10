"""Regex layer: fast pattern rules applied line-by-line to source files.

Rules with ast_covered=True are skipped for .py — ast_scanner reports them
with real syntax context instead of raw text matching.
"""

from __future__ import annotations

import re
from pathlib import Path

from .findings import Finding
from .rules import HINTS, RULES

SUPPRESS_MARK = "guarddog: ignore"


def suppressed(line: str, rule_id: str) -> bool:
    if SUPPRESS_MARK not in line:
        return False
    tail = line.split(SUPPRESS_MARK, 1)[1].strip()
    # token match, not substring: `ignore eval` must not kill `eval-exec`
    return not tail or rule_id in re.split(r"[\s,]+", tail)


def scan_regex(path: Path, rel: str, text: str) -> list[Finding]:
    is_python = path.suffix.lower() == ".py"
    findings: list[Finding] = []
    for lineno, line in enumerate(text.splitlines(), start=1):
        for rule in RULES:
            if is_python and rule.ast_covered:
                continue
            if rule.pattern.search(line) and not suppressed(line, rule.rule_id):
                findings.append(
                    Finding(
                        rule_id=rule.rule_id,
                        severity=rule.severity,
                        file=rel,
                        line=lineno,
                        message=rule.message,
                        snippet=line.strip()[:160],
                        recommendation=HINTS.get(rule.rule_id, ""),
                    )
                )
    return findings
