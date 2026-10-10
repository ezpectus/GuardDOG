"""LLM audit clients — Gemini and OpenAI-compatible REST (stdlib urllib only).

Key lookup order: GUARDDOG_API_KEY → provider-specific env. Without a key
the layer is skipped with a reason in the report — never silently.
"""

from __future__ import annotations

import json
import os
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

from parsers.findings import Finding, Severity

GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
OPENAI_URL = "https://api.openai.com/v1/chat/completions"


@dataclass
class LLMResult:
    findings: list[Finding]
    skipped_reason: str | None = None


def _extract_findings(text: str) -> list[Any]:
    for open_c, close_c in (("{", "}"), ("[", "]")):
        start, end = text.find(open_c), text.rfind(close_c)
        if start == -1 or end == -1:
            continue
        try:
            data = json.loads(text[start : end + 1])
        except json.JSONDecodeError:
            continue
        items = data.get("findings", data) if isinstance(data, dict) else data
        if isinstance(items, list):
            return items
    return []


def _to_findings(raw_items: list[Any]) -> list[Finding]:
    findings: list[Finding] = []
    for raw in raw_items:
        if not isinstance(raw, dict):
            continue
        try:
            findings.append(
                Finding(
                    rule_id=str(raw.get("rule_id", "llm")),
                    severity=Severity.from_name(str(raw.get("severity", "medium"))),
                    file=str(raw.get("file", "?")),
                    line=int(raw.get("line", 0)),
                    message=str(raw.get("message", "llm finding")),
                    snippet=str(raw.get("snippet", ""))[:160],
                    source="llm",
                    recommendation=str(raw.get("fix", raw.get("recommendation", "")))[:300],
                )
            )
        except (ValueError, KeyError, AttributeError):
            continue
    return findings


def _files_blob(payload: list[dict[str, str]]) -> str:
    return "\n\n".join(f"### FILE: {f['path']}\n```\n{f['content']}\n```" for f in payload)


def _post(url: str, body: dict[str, Any], headers: dict[str, str], timeout: int) -> dict[str, Any]:
    req = urllib.request.Request(
        url,
        data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json", **headers},
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return cast(dict[str, Any], json.loads(resp.read()))


def _audit_gemini(prompt: str, payload: list[dict[str, str]], cfg: dict[str, Any]) -> LLMResult:
    key = os.environ.get("GUARDDOG_API_KEY") or os.environ.get("GEMINI_API_KEY")
    if not key:
        return LLMResult([], skipped_reason="no GUARDDOG_API_KEY/GEMINI_API_KEY set")
    model = cfg.get("model", "gemini-2.0-flash")
    body = {
        "system_instruction": {"parts": [{"text": prompt}]},
        "contents": [{"parts": [{"text": _files_blob(payload)}]}],
        "generationConfig": {"response_mime_type": "application/json"},
    }
    try:
        data = _post(
            f"{GEMINI_URL.format(model=model)}?key={key}", body, {}, int(cfg.get("timeout_sec", 60))
        )
        text = data["candidates"][0]["content"]["parts"][0]["text"]
    except Exception as exc:
        return LLMResult([], skipped_reason=f"gemini request failed: {exc}")
    return LLMResult(_to_findings(_extract_findings(text)))


def _audit_openai(prompt: str, payload: list[dict[str, str]], cfg: dict[str, Any]) -> LLMResult:
    key = os.environ.get("GUARDDOG_API_KEY") or os.environ.get("OPENAI_API_KEY")
    if not key:
        return LLMResult([], skipped_reason="no GUARDDOG_API_KEY/OPENAI_API_KEY set")
    base = cfg.get("base_url", OPENAI_URL)
    body = {
        "model": cfg.get("model", "gpt-4o-mini"),
        "response_format": {"type": "json_object"},
        "messages": [
            {"role": "system", "content": prompt},
            {"role": "user", "content": _files_blob(payload)},
        ],
    }
    try:
        data = _post(
            base, body, {"Authorization": f"Bearer {key}"}, int(cfg.get("timeout_sec", 60))
        )
        text = data["choices"][0]["message"]["content"]
    except Exception as exc:
        return LLMResult([], skipped_reason=f"openai request failed: {exc}")
    return LLMResult(_to_findings(_extract_findings(text)))


PROVIDERS = {"gemini": _audit_gemini, "openai": _audit_openai}


def audit(prompt: str, payload: list[dict[str, str]], cfg: dict[str, Any]) -> LLMResult:
    if not payload:
        return LLMResult([], skipped_reason="no changed files (cache hit)")
    provider = str(cfg.get("provider", "gemini")).lower()
    fn = PROVIDERS.get(provider)
    if fn is None:
        return LLMResult([], skipped_reason=f"unknown provider: {provider}")
    return fn(prompt, payload, cfg)


def load_system_prompt(templates_dir: Path) -> str:
    path = templates_dir / "system_prompt.md"
    return path.read_text(encoding="utf-8") if path.is_file() else ""
