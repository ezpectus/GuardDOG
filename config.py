"""Config loading: config.json is the authority; .guarddog.json in the
scanned target and --config override it (deep-merge: dicts merge, lists
append-unique, scalars replace). Inline .get() fallbacks keep the scanner
sane if config.json is deleted.
"""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

SCANNER_ROOT = Path(__file__).resolve().parent
TARGET_CONFIG_NAME = ".guarddog.json"
KNOWN_KEYS = {
    "ignore_dirs",
    "ignore_files",
    "scan_extensions",
    "max_file_size_kb",
    "fail_on",
    "llm",
}


@dataclass
class Config:
    data: dict[str, Any] = field(default_factory=dict)

    @property
    def ignore_dirs(self) -> set[str]:
        return set(self.data.get("ignore_dirs", []))

    @property
    def ignore_files(self) -> set[str]:
        return set(self.data.get("ignore_files", []))

    @property
    def scan_extensions(self) -> set[str]:
        return {e.lower() for e in self.data.get("scan_extensions", [])}

    @property
    def max_file_size_kb(self) -> int:
        return int(self.data.get("max_file_size_kb", 256))

    @property
    def fail_on(self) -> str:
        return str(self.data.get("fail_on", "critical"))

    @property
    def llm(self) -> dict[str, Any]:
        raw = self.data.get("llm", {})
        return dict(raw) if isinstance(raw, dict) else {}


def _merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    out = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = _merge(out[key], value)
        elif isinstance(value, list) and isinstance(out.get(key), list):
            out[key] = out[key] + [v for v in value if v not in out[key]]
        else:
            out[key] = value
    return out


def _read_json(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        raise ValueError(f"bad config file {path}: {exc}") from None
    if not isinstance(data, dict):
        raise ValueError(f"bad config file {path}: top level must be an object")
    return data


def load(target: Path | None = None, explicit: Path | None = None) -> Config:
    data: dict[str, Any] = {}
    default_file = SCANNER_ROOT / "config.json"
    if default_file.is_file():
        data = _merge(data, _read_json(default_file))
    if target is not None:
        target_file = target / TARGET_CONFIG_NAME
        if target_file.is_file():
            data = _merge(data, _read_json(target_file))
    if explicit is not None and explicit.is_file():
        data = _merge(data, _read_json(explicit))
    unknown = sorted(set(data) - KNOWN_KEYS)
    if unknown:
        print(
            f"guarddog: unknown config keys ignored: {', '.join(unknown)}",
            file=sys.stderr,
        )
    return Config(data)
