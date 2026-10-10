"""Report renderers: markdown / json / self-contained html dashboard."""

from __future__ import annotations

import html
import json
from datetime import datetime, timezone
from pathlib import Path
from string import Template

from parsers.findings import ScanResult, Severity

SEV_ORDER = (Severity.CRITICAL, Severity.HIGH, Severity.MEDIUM, Severity.LOW)
SEV_COLORS = {
    "CRITICAL": "#e5484d",
    "HIGH": "#f76b15",
    "MEDIUM": "#f5d90a",
    "LOW": "#46a758",
}


def _sorted(result: ScanResult):
    return sorted(result.findings, key=lambda x: (-x.severity, x.file, x.line))


def render_markdown(result: ScanResult) -> str:
    counts = result.counts()
    out = [
        "# GuardDOG report",
        "",
        f"- target: `{result.target}`",
        f"- date: {datetime.now(timezone.utc):%Y-%m-%d %H:%M UTC}",
        f"- files scanned: {result.files_scanned}",
        f"- findings: **{len(result.findings)}** "
        + " ".join(f"{s.name}: {counts[s.name]}" for s in SEV_ORDER),
    ]
    if result.llm_note:
        out.append(f"- llm layer: {result.llm_note}")
    out += ["", "| Sev | Rule | File:Line | Message |", "|-----|------|-----------|---------|"]
    for f in _sorted(result):
        out.append(f"| {f.severity.name} | `{f.rule_id}` | `{f.file}:{f.line}` | {f.message} |")
    out.append("")
    return "\n".join(out)


def render_json(result: ScanResult) -> str:
    return json.dumps(
        {
            "target": result.target,
            "date": datetime.now(timezone.utc).isoformat(),
            "files_scanned": result.files_scanned,
            "counts": result.counts(),
            "llm": result.llm_note,
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
                for f in result.findings
            ],
        },
        indent=2,
        ensure_ascii=False,
    )


def render_html(result: ScanResult, template_path: Path) -> str:
    counts = result.counts()
    rows = []
    for f in _sorted(result):
        color = SEV_COLORS[f.severity.name]
        rows.append(
            "<tr>"
            f'<td><span class="sev" style="background:{color}">{f.severity.name}</span></td>'
            f"<td><code>{html.escape(f.rule_id)}</code></td>"
            f"<td><code>{html.escape(f.file)}:{f.line}</code></td>"
            f"<td>{html.escape(f.message)}"
            + (
                f"<details><summary>snippet</summary><pre>{html.escape(f.snippet)}</pre></details>"
                if f.snippet
                else ""
            )
            + f"</td><td>{html.escape(f.source)}</td></tr>"
        )
    cards = "".join(
        f'<div class="card" style="border-top-color:{SEV_COLORS[s.name]}">'
        f'<div class="num">{counts[s.name]}</div><div class="lbl">{s.name}</div></div>'
        for s in SEV_ORDER
    )
    tpl = Template(template_path.read_text(encoding="utf-8"))
    return tpl.safe_substitute(
        target=html.escape(result.target),
        date=f"{datetime.now(timezone.utc):%Y-%m-%d %H:%M UTC}",
        files_scanned=result.files_scanned,
        total=len(result.findings),
        cards=cards,
        llm_note=html.escape(result.llm_note or "not run"),
        rows="".join(rows) or '<tr><td colspan="5">clean</td></tr>',
    )


RENDERERS = {"md": render_markdown, "json": render_json, "html": render_html}


def render(result: ScanResult, fmt: str, templates_dir: Path) -> str:
    if fmt == "html":
        return render_html(result, templates_dir / "report.html")
    return RENDERERS[fmt](result)
