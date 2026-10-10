"""LLM context packing + hash cache.

Each file's SHA-256 is stored in .guarddog_cache.json at the scan target.
Unchanged files never enter the payload — tokens are not re-spent.
Payload order prioritizes "key" files (models, config, infra) where
high-signal issues concentrate.
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

CACHE_NAME = ".guarddog_cache.json"

KEY_FILE = re.compile(
    r"(^|/)(models?|schemas?|settings|config|conf|urls|routers?|routes?"
    r"|services?|auth|security|middleware|database|db|migrations?"
    r"|docker-compose[^/]*|compose\.ya?ml|Dockerfile|requirements[^/]*\.txt"
    r"|pyproject\.toml|package\.json|\.env[^/]*)$",
    re.I,
)


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


def clear_cache(root: Path) -> bool:
    path = root / CACHE_NAME
    if path.is_file():
        path.unlink()
        return True
    return False


def _priority(rel: str) -> tuple[int, str]:
    return (0 if KEY_FILE.search(rel) else 1, rel)


def build_llm_context(
    root: Path, files: list[Path], max_files: int
) -> tuple[list[dict], list[str], dict[str, str]]:
    """Return (payload, skipped-unchanged, updated cache)."""
    cache = load_cache(root)
    entries: list[tuple[Path, str, bytes]] = []
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
        else:
            entries.append((path, rel, data))
    entries.sort(key=lambda e: _priority(e[1]))
    payload = [
        {"path": rel, "content": data.decode("utf-8", errors="replace")}
        for _, rel, data in entries[:max_files]
    ]
    return payload, unchanged, new_cache
