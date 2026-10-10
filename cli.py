"""GuardDOG CLI — subcommands: scan (default), install-hook, rules, cache.

    guarddog scan <target> [--no-llm] [--fail-on SEV] [--format md|json|html]
    guarddog install-hook <target> [--fail-on SEV] [--force]
    guarddog rules
    guarddog cache <target> [--clear]

Bare `guarddog <path>` is shorthand for `guarddog scan <path>`.
"""

from __future__ import annotations

import argparse
import stat
import sys
from pathlib import Path

import config as cfgmod
from parsers.ast_scanner import scan_ast
from parsers.findings import ScanResult
from parsers.regex_scanner import scan_regex
from parsers.rules import RULES
from parsers.walker import iter_source_files
from report import render

SCANNER_ROOT = Path(__file__).resolve().parent
HOOK_TEMPLATE = """#!/bin/sh
# GuardDOG pre-commit hook — blocks commits with findings >= threshold
python "{scanner}/main.py" scan . --no-llm --fail-on {fail_on} --format md -o .guarddog_report.md
"""


def _scan_parser(p: argparse.ArgumentParser) -> None:
    p.add_argument("target", nargs="?", default=".")
    p.add_argument("--config", type=Path, default=None)
    p.add_argument("--no-llm", action="store_true", help="local layer only")
    p.add_argument(
        "--fail-on",
        default=None,
        choices=["critical", "high", "medium", "low", "never"],
    )
    p.add_argument("--format", dest="fmt", default="md", choices=["md", "json", "html"])
    p.add_argument("-o", "--out", type=Path, default=None)
    p.add_argument("--quiet", action="store_true", help="no stdout report dump")


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="guarddog",
        description="Hybrid repo scanner: regex+AST local layer, optional LLM audit",
    )
    sub = p.add_subparsers(dest="cmd")

    _scan_parser(sub.add_parser("scan", help="scan a project (default command)"))

    h = sub.add_parser("install-hook", help="install git pre-commit hook into target repo")
    h.add_argument("target", nargs="?", default=".")
    h.add_argument("--fail-on", default="high")
    h.add_argument("--force", action="store_true", help="overwrite existing hook")

    sub.add_parser("rules", help="list all local rules")

    c = sub.add_parser("cache", help="inspect/clear LLM context cache")
    c.add_argument("target", nargs="?", default=".")
    c.add_argument("--clear", action="store_true")
    return p


def _local_scan(target: Path, cfg: cfgmod.Config) -> tuple[ScanResult, list[Path]]:
    files = list(
        iter_source_files(
            target,
            extensions=cfg.scan_extensions,
            ignore_dirs=cfg.ignore_dirs,
            ignore_files=cfg.ignore_files,
            max_size_kb=cfg.max_file_size_kb,
        )
    )
    result = ScanResult(target=str(target), files_scanned=len(files))
    for path in files:
        rel = path.relative_to(target).as_posix()
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        result.findings.extend(scan_regex(path, rel, text))
        if path.suffix.lower() == ".py":
            result.findings.extend(scan_ast(path, rel, text))
    return result, files


def _llm_scan(target: Path, files: list[Path], cfg: cfgmod.Config, result: ScanResult) -> str:
    llm_cfg = cfg.llm
    if not llm_cfg.get("enabled", True):
        return "disabled in config"
    from llm_client.client import audit, load_system_prompt
    from llm_client.context import build_llm_context, save_cache

    payload, unchanged, new_cache = build_llm_context(
        target, files, max_files=int(llm_cfg.get("max_files", 40))
    )
    prompt = load_system_prompt(SCANNER_ROOT / "templates")
    res = audit(prompt, payload, llm_cfg)
    if res.skipped_reason is None:
        save_cache(target, new_cache)  # commit cache only on real response
        result.findings.extend(res.findings)
        return f"audited {len(payload)} files ({len(unchanged)} unchanged/cached)"
    return f"skipped — {res.skipped_reason} ({len(unchanged)} cached)"


def cmd_scan(args: argparse.Namespace) -> int:
    target = Path(args.target).resolve()
    if not target.is_dir():
        print(f"guarddog: target not found: {target}", file=sys.stderr)
        return 2
    cfg = cfgmod.load(target=target, explicit=args.config)
    result, files = _local_scan(target, cfg)
    if not args.no_llm:
        result.llm_note = _llm_scan(target, files, cfg, result)

    fail_on = args.fail_on or cfg.fail_on
    text = render(result, args.fmt, SCANNER_ROOT / "templates")
    out = args.out or target / f"guarddog_report.{args.fmt}"
    out.write_text(text, encoding="utf-8")
    if not args.quiet:
        print(text)
    print(f"guarddog: report -> {out}", file=sys.stderr)
    return result.exit_code(fail_on)


def cmd_install_hook(args: argparse.Namespace) -> int:
    target = Path(args.target).resolve()
    hooks = target / ".git" / "hooks"
    if not hooks.is_dir():
        print(f"guarddog: {target} is not a git repo", file=sys.stderr)
        return 2
    hook = hooks / "pre-commit"
    if hook.exists() and not args.force:
        print("guarddog: pre-commit exists — use --force", file=sys.stderr)
        return 2
    hook.write_text(
        HOOK_TEMPLATE.format(scanner=SCANNER_ROOT.as_posix(), fail_on=args.fail_on),
        encoding="utf-8",
    )
    hook.chmod(hook.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    print(f"guarddog: pre-commit hook installed -> {hook} (fail_on={args.fail_on})")
    return 0


def cmd_rules() -> int:
    width = max(len(r.rule_id) for r in RULES)
    for r in RULES:
        flag = " [ast on .py]" if r.ast_covered else ""
        print(f"{r.severity.name:<8} {r.rule_id:<{width}}  {r.message}{flag}")
    return 0


def cmd_cache(args: argparse.Namespace) -> int:
    from llm_client.context import clear_cache, load_cache

    target = Path(args.target).resolve()
    if args.clear:
        print("guarddog: cache cleared" if clear_cache(target) else "guarddog: no cache")
        return 0
    cache = load_cache(target)
    print(f"guarddog: {len(cache)} cached hashes in {target}")
    return 0


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    cmds = {"scan", "install-hook", "rules", "cache"}
    # `guarddog <path>` and `guarddog --flags` both mean `guarddog scan …`;
    # only -h/--help stays at the top level to list subcommands.
    if not argv or (argv[0] not in cmds and argv[0] not in ("-h", "--help")):
        argv = ["scan"] + argv
    args = build_parser().parse_args(argv)

    if args.cmd == "install-hook":
        return cmd_install_hook(args)
    if args.cmd == "rules":
        return cmd_rules()
    if args.cmd == "cache":
        return cmd_cache(args)
    return cmd_scan(args)
