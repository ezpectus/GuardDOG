"""Repository walker: yields source files honoring ignore rules and size caps.

Ignore order: config.ignore_dirs/ignore_files → target's .gitignore →
extension allowlist → size cap. .gitignore support covers the common cases
(plain names, *.ext globs, dir/ entries, !negation is intentionally ignored —
anchored/negated patterns are out of MVP scope).
"""

from __future__ import annotations

import fnmatch
import os
from pathlib import Path
from typing import Iterable, Iterator


def _load_gitignore_patterns(root: Path) -> list[str]:
    gitignore = root / ".gitignore"
    if not gitignore.is_file():
        return []
    patterns = []
    for raw in gitignore.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw.strip()
        if line and not line.startswith("#") and not line.startswith("!"):
            patterns.append(line)
    return patterns


def _ignored(
    rel: str,
    name: str,
    ignore_dirs: Iterable[str],
    ignore_files: Iterable[str],
    gitignore: list[str],
    is_dir: bool,
) -> bool:
    rel = rel.replace("\\", "/")
    parts = rel.split("/")
    if any(d in parts or fnmatch.fnmatch(name, d) for d in ignore_dirs):
        return True
    if not is_dir and any(fnmatch.fnmatch(name, p) for p in ignore_files):
        return True
    for pat in gitignore:
        pat = pat.rstrip("/")
        if fnmatch.fnmatch(rel, pat) or fnmatch.fnmatch(name, pat):
            return True
    return False


def iter_source_files(
    root: Path,
    extensions: set[str],
    ignore_dirs: set[str],
    ignore_files: set[str],
    max_size_kb: int,
) -> Iterator[Path]:
    gitignore = _load_gitignore_patterns(root)
    for dirpath, dirnames, filenames in os.walk(root):
        base = Path(dirpath)
        rel_dir = base.relative_to(root).as_posix() if base != root else ""
        dirnames[:] = sorted(
            d
            for d in dirnames
            if not _ignored(
                f"{rel_dir}/{d}".lstrip("/"), d, ignore_dirs, ignore_files, gitignore, is_dir=True
            )
        )
        for fname in sorted(filenames):
            path = base / fname
            rel = path.relative_to(root).as_posix()
            if _ignored(rel, fname, ignore_dirs, ignore_files, gitignore, is_dir=False):
                continue
            if (
                extensions
                and path.suffix.lower() not in extensions
                and path.name.lower() not in extensions
            ):
                continue
            try:
                if path.stat().st_size > max_size_kb * 1024:
                    continue
            except OSError:
                continue
            yield path
