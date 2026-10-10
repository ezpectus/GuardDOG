"""LLM context packing + hash cache.

Each file's SHA-256 is stored in .guarddog_cache.json at the scan target.
Unchanged files are excluded from the payload so tokens are not re-spent.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

CACHE_NAME = ".guarddog_cache.json"


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def load_cache(root: Path) -> dict[str, str]:
    path = root / CACHE_NAME
    if not path.is_file():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def save_cache(root: Path, cache: dict[str, str]) -> None:
    (root / CACHE_NAME).write_text(json.dumps(cache, indent=2, sort_keys=True), encoding="utf-8")


def build_llm_context(
    root: Path, files: list[Path], max_files: int, max_size_kb: int
) -> tuple[list[dict], list[str]]:
    """Return (payload files, unchanged files skipped by cache)."""
    cache = load_cache(root)
    payload: list[dict] = []
    unchanged: list[str] = []
    new_cache: dict[str, str] = {}
    for path in files:
        rel = path.relative_to(root).as_posix()
        try:
            data = path.read_bytes()
        except OSError:
            continue
        digest = _sha256(data)
        new_cache[rel] = digest
        if cache.get(rel) == digest:
            unchanged.append(rel)
            continue
        if len(payload) >= max_files:
            continue
        payload.append({"path": rel, "content": data.decode("utf-8", errors="replace")})
    save_cache(root, new_cache)
    return payload, unchanged
