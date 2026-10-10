"""Report rendering + severity-gated exit code."""

from __future__ import annotations

import json
from datetime import datetime, timezone

from parsers.findings import Finding, Severity

SEV_ORDER = (Severity.CRITICAL, Severity.HIGH, Severity.MEDIUM, Severity.LOW)


def _counts(findings: list[Finding]) -> dict[str, int]:
    counts = {s.name: 0 for s in SEV_ORDER}
    for f in findings:
        counts[f.severity.name] += 1
    return counts


def render_markdown(findings: list[Finding], target: str, llm_note: str | None = None) -> str:
    counts = _counts(findings)
    out = [
        "# GuardDOG report",
        "",
        f"- target: `{target}`",
        f"- date: {datetime.now(timezone.utc):%Y-%m-%d %H:%M UTC}",
        f"- findings: **{len(findings)}** "
        + " ".join(f"{s.name}: {counts[s.name]}" for s in SEV_ORDER),
    ]
    if llm_note:
        out.append(f"- llm layer: {llm_note}")
    out += ["", "| Sev | Rule | File:Line | Message |", "|-----|------|-----------|---------|"]
    for f in sorted(findings, key=lambda x: (-x.severity, x.file, x.line)):
        out.append(f"| {f.severity.name} | `{f.rule_id}` | `{f.file}:{f.line}` " f"| {f.message} |")
    out.append("")
    return "\n".join(out)


def render_json(findings: list[Finding], target: str, llm_note: str | None = None) -> str:
    return json.dumps(
        {
            "target": target,
            "date": datetime.now(timezone.utc).isoformat(),
            "counts": _counts(findings),
            "llm": llm_note,
            "findings": [
                {
                    "rule_id": f.rule_id,
                    "severity": f.severity.name,
                    "file": f.file,
                    "line": f.line,
                    "message": f.message,
                    "snippet": f.snippet,
                    "source": f.source,
                }
                for f in findings
            ],
        },
        indent=2,
        ensure_ascii=False,
    )


def exit_code(findings: list[Finding], fail_on: str) -> int:
    if fail_on.lower() in ("never", "none", "off"):
        return 0
    threshold = Severity.from_name(fail_on)
    return 1 if any(f.severity >= threshold for f in findings) else 0
