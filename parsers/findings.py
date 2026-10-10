"""Finding model: one normalized record per detected issue."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import IntEnum
from typing import Iterable


class Severity(IntEnum):
    LOW = 1
    MEDIUM = 2
    HIGH = 3
    CRITICAL = 4

    @classmethod
    def from_name(cls, name: str) -> "Severity":
        try:
            return cls[name.strip().upper()]
        except KeyError:
            raise ValueError(f"unknown severity: {name!r}") from None


@dataclass(frozen=True)
class Finding:
    rule_id: str
    severity: Severity
    file: str
    line: int
    message: str
    snippet: str = ""
    source: str = "local"
    recommendation: str = ""


@dataclass
class ScanResult:
    target: str
    files_scanned: int
    findings: list[Finding] = field(default_factory=list)
    llm_note: str | None = None
    _seen: set[tuple[str, int, str]] = field(default_factory=set, repr=False, compare=False)

    def __post_init__(self) -> None:
        self._seen = {(f.file, f.line, f.rule_id) for f in self.findings}

    def add(self, new: Iterable[Finding]) -> None:
        """Merge findings, deduped by (file, line, rule_id) — the local and
        LLM layers can legitimately hit the same line; report stays clean."""
        for f in new:
            key = (f.file, f.line, f.rule_id)
            if key not in self._seen:
                self._seen.add(key)
                self.findings.append(f)

    def counts(self) -> dict[str, int]:
        counts = {
            s.name: 0 for s in (Severity.CRITICAL, Severity.HIGH, Severity.MEDIUM, Severity.LOW)
        }
        for f in self.findings:
            counts[f.severity.name] += 1
        return counts

    def exit_code(self, fail_on: str) -> int:
        if fail_on.lower() in ("never", "none", "off"):
            return 0
        threshold = Severity.from_name(fail_on)
        return 1 if any(f.severity >= threshold for f in self.findings) else 0
