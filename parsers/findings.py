"""Finding model: one normalized record per detected issue."""

from __future__ import annotations

from dataclasses import dataclass
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
