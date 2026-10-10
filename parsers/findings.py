"""Finding model: one normalized record per detected issue."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import IntEnum


class Severity(IntEnum):
    LOW = 1
    MEDIUM = 2
    HIGH = 3
    CRITICAL = 4

    @classmethod
    def from_name(cls, name: str) -> "Severity":
        return cls[name.strip().upper()]


@dataclass(frozen=True)
class Finding:
    rule_id: str
    severity: Severity
    file: str
    line: int
    message: str
    snippet: str = ""
    source: str = "local"


@dataclass
class ScanResult:
    target: str
    files_scanned: int
    findings: list[Finding] = field(default_factory=list)
    llm_note: str | None = None

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
