"""LLM audit client — Gemini REST (stdlib urllib, no SDK dependency).

Set GUARDDOG_API_KEY (or GEMINI_API_KEY). Without a key the LLM layer is
skipped and the report says so — never silently, never a fake verdict.
"""

from __future__ import annotations

import json
import os
import urllib.request
from dataclasses import dataclass
from pathlib import Path

from parsers.findings import Finding, Severity

API_URL = "https://generativelanguage.googleapis.com/v1beta/models/" "{model}:generateContent"


@dataclass
class LLMResult:
    findings: list[Finding]
    skipped_reason: str | None = None


def _extract_json(text: str) -> list[dict]:
    start, end = text.find("["), text.rfind("]")
    if start == -1 or end == -1:
        start, end = text.find("{"), text.rfind("}")
    if start == -1 or end == -1:
        return []
    try:
        data = json.loads(text[start : end + 1])
    except json.JSONDecodeError:
        return []
    if isinstance(data, dict):
        data = data.get("findings", [])
    return data if isinstance(data, list) else []


def audit_with_gemini(
    system_prompt: str, payload: list[dict], model: str = "gemini-2.0-flash", timeout: int = 60
) -> LLMResult:
    key = os.environ.get("GUARDDOG_API_KEY") or os.environ.get("GEMINI_API_KEY")
    if not key:
        return LLMResult([], skipped_reason="no GUARDDOG_API_KEY/GEMINI_API_KEY set")
    if not payload:
        return LLMResult([], skipped_reason="no changed files (cache hit)")

    files_blob = "\n\n".join(f"### FILE: {f['path']}\n```\n{f['content']}\n```" for f in payload)
    body = json.dumps(
        {
            "system_instruction": {"parts": [{"text": system_prompt}]},
            "contents": [{"parts": [{"text": files_blob}]}],
            "generationConfig": {"response_mime_type": "application/json"},
        }
    ).encode()

    req = urllib.request.Request(
        f"{API_URL.format(model=model)}?key={key}",
        data=body,
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read())
    except Exception as exc:  # network/API failure must not crash the scan
        return LLMResult([], skipped_reason=f"LLM request failed: {exc}")

    try:
        text = data["candidates"][0]["content"]["parts"][0]["text"]
    except (KeyError, IndexError, TypeError):
        return LLMResult([], skipped_reason="empty LLM response")

    findings: list[Finding] = []
    for raw in _extract_json(text):
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
                )
            )
        except (ValueError, KeyError, AttributeError):
            continue
    return LLMResult(findings)


def build_client(cfg: dict):
    provider = cfg.get("llm", {}).get("provider", "gemini")
    if provider != "gemini":
        return None
    return audit_with_gemini


def load_system_prompt(templates_dir: Path) -> str:
    path = templates_dir / "system_prompt.md"
    return path.read_text(encoding="utf-8") if path.is_file() else ""
