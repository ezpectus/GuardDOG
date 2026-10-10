#!/usr/bin/env python3
"""GuardDOG — hybrid repo scanner: local regex/AST rules + optional LLM audit.

Usage:
    python main.py <target_dir> [--no-llm] [--fail-on critical|high|medium|low|never]
                   [--format md|json] [-o report.md] [--config config.json]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from parsers.ast_scanner import scan_ast
from parsers.findings import Finding
from parsers.regex_scanner import scan_regex
from parsers.walker import iter_source_files
from report import exit_code, render_json, render_markdown

SCANNER_ROOT = Path(__file__).resolve().parent


def load_config(path: Path | None) -> dict:
    cfg_path = path or (SCANNER_ROOT / "config.json")
    if cfg_path.is_file():
        return json.loads(cfg_path.read_text(encoding="utf-8"))
    return {}


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(prog="guarddog", description="Hybrid repo security/quality scanner")
    p.add_argument("target", nargs="?", default=".", help="project dir to scan")
    p.add_argument("--config", type=Path, default=None)
    p.add_argument("--no-llm", action="store_true", help="local layer only")
    p.add_argument(
        "--fail-on", default=None, choices=["critical", "high", "medium", "low", "never"]
    )
    p.add_argument("--format", dest="fmt", default="md", choices=["md", "json"])
    p.add_argument(
        "-o",
        "--out",
        type=Path,
        default=None,
        help="report file (default: guarddog_report.<ext> in target)",
    )
    return p.parse_args(argv)


def scan_local(target: Path, cfg: dict) -> list[Finding]:
    files = list(
        iter_source_files(
            target,
            extensions=set(cfg.get("scan_extensions", [])),
            ignore_dirs=set(cfg.get("ignore_dirs", [])),
            ignore_files=set(cfg.get("ignore_files", [])),
            max_size_kb=int(cfg.get("max_file_size_kb", 256)),
        )
    )
    findings: list[Finding] = []
    for path in files:
        rel = path.relative_to(target).as_posix()
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        findings.extend(scan_regex(path, rel, text))
        if path.suffix.lower() == ".py":
            findings.extend(scan_ast(path, rel, text))
    return findings, files


def run_llm_layer(
    target: Path, files: list[Path], cfg: dict, findings: list[Finding]
) -> str | None:
    if not cfg.get("llm", {}).get("enabled", True):
        return "disabled in config"
    from llm_client.client import audit_with_gemini, load_system_prompt
    from llm_client.context import build_llm_context

    llm_cfg = cfg.get("llm", {})
    payload, unchanged = build_llm_context(
        target,
        files,
        max_files=int(llm_cfg.get("max_files", 40)),
        max_size_kb=int(cfg.get("max_file_size_kb", 256)),
    )
    prompt = load_system_prompt(SCANNER_ROOT / "templates")
    result = audit_with_gemini(prompt, payload, model=llm_cfg.get("model", "gemini-2.0-flash"))
    findings.extend(result.findings)
    if result.skipped_reason:
        return f"skipped — {result.skipped_reason} ({len(unchanged)} cached)"
    return f"audited {len(payload)} files ({len(unchanged)} unchanged/cached)"


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    target = Path(args.target).resolve()
    if not target.is_dir():
        print(f"guarddog: target not found: {target}", file=sys.stderr)
        return 2

    cfg = load_config(args.config)
    findings, files = scan_local(target, cfg)

    llm_note = None
    if not args.no_llm:
        llm_note = run_llm_layer(target, files, cfg, findings)

    fail_on = args.fail_on or cfg.get("fail_on", "critical")
    report = (render_markdown if args.fmt == "md" else render_json)(findings, str(target), llm_note)

    out = args.out or target / f"guarddog_report.{args.fmt}"
    out.write_text(report, encoding="utf-8")
    print(report)
    print(f"\nreport -> {out}", file=sys.stderr)
    return exit_code(findings, fail_on)


if __name__ == "__main__":
    sys.exit(main())
