"""Scanner registry — the seam for adding new analysis layers.

Each entry: (applies_to(path) -> bool, scan(path, rel, text) -> Findings).
New scanners (JS/TS tree-sitter, entropy scan, …) register here — cli.py
and the report path never change.
"""

from __future__ import annotations

from pathlib import Path

from .ast_scanner import scan_ast
from .regex_scanner import scan_regex


def _always(_path: Path) -> bool:
    return True


def _is_python(path: Path) -> bool:
    return path.suffix.lower() == ".py"


SCANNERS = [
    (_always, scan_regex),
    (_is_python, scan_ast),
]
