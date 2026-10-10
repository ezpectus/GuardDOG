"""GuardDOG CLI — subcommands: scan (default), install-hook, rules, cache.

    guarddog scan <target> [--no-llm] [--fail-on SEV] [--format md|json|html]
    guarddog install-hook <target> [--fail-on SEV] [--force]
    guarddog rules
    guarddog cache <target> [--clear]

Bare `guarddog <path>` is shorthand for `guarddog scan <path>`.
"""

from __future__ import annotations

import argparse
import os
import stat
import sys
from pathlib import Path
from typing import Callable

import config as cfgmod
from parsers.findings import ScanResult, Severity
from parsers.rules import RULES
from parsers.scanners import SCANNERS
from parsers.walker import iter_source_files
from report import render

SCANNER_ROOT = Path(__file__).resolve().parent
HOOK_TEMPLATE = """#!/bin/sh
# GuardDOG pre-commit hook — blocks commits with findings >= threshold
# Scans staged files only; falls back to full scan outside a git repo.
python "{scanner}/main.py" scan . --staged --no-llm --fail-on {fail_on} --format md -o .guarddog_report.md
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
    p.add_argument(
        "--staged",
        action="store_true",
        help="scan git-staged files only (pre-commit mode)",
    )


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

    k = sub.add_parser("check", help="dry-run: what would be scanned, LLM payload estimate")
    k.add_argument("target", nargs="?", default=".")
    k.add_argument("--config", type=Path, default=None)

    sub.add_parser("selftest", help="built-in health check — every component, OK/FAIL")
    return p


def _staged_relpaths(target: Path) -> tuple[Path, set[str]] | None:
    """(repo root, staged paths rel. to repo root) — or None if no git/repo.

    Repo root matters: `git diff --cached` reports paths relative to the
    repository top, not to `target` — a staged scan of a subdirectory must
    still match files, otherwise it silently scans nothing (fail-open).
    """
    import shutil
    import subprocess

    if not shutil.which("git"):
        return None
    try:
        top = subprocess.run(
            ["git", "-C", str(target), "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            timeout=15,
        )
        if top.returncode != 0:
            return None
        root = Path(top.stdout.strip())
        out = subprocess.run(
            ["git", "-C", str(root), "diff", "--cached", "--name-only", "--diff-filter=ACMR"],
            capture_output=True,
            text=True,
            timeout=15,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if out.returncode != 0:
        return None
    paths = {ln.strip().replace("\\", "/") for ln in out.stdout.splitlines() if ln.strip()}
    return root, paths


def _local_scan(
    target: Path,
    cfg: cfgmod.Config,
    only: set[str] | None = None,
    rel_base: Path | None = None,
) -> tuple[ScanResult, list[Path]]:
    rel_base = rel_base or target
    files = [
        p
        for p in iter_source_files(
            target,
            extensions=cfg.scan_extensions,
            ignore_dirs=cfg.ignore_dirs,
            ignore_files=cfg.ignore_files,
            max_size_kb=cfg.max_file_size_kb,
        )
        if only is None or p.relative_to(rel_base).as_posix() in only
    ]
    result = ScanResult(target=str(target), files_scanned=len(files))
    for path in files:
        rel = path.relative_to(target).as_posix()
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for applies, scan in SCANNERS:
            if applies(path):
                result.add(scan(path, rel, text))
    return result, files


def _threat_model(target: Path, cfg: cfgmod.Config) -> str:
    """Project-provided threat model — calibrates LLM severity (oss-scanner idea).

    Sources in priority order: cfg llm.threat_model path, then conventional
    locations inside the scanned repo.
    """
    explicit = cfg.llm.get("threat_model")
    candidates: list[Path] = (
        [target / explicit]
        if explicit
        else [
            target / "threat_model.md",
            target / "THREAT_MODEL.md",
            target / ".guarddog" / "threat_model.md",
        ]
    )
    for path in candidates:
        if path.is_file():
            try:
                return path.read_text(encoding="utf-8", errors="replace")[:8000]
            except OSError:
                continue
    return ""


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
    threat = _threat_model(target, cfg)
    if threat:
        prompt += (
            "\n\n## PROJECT THREAT MODEL — calibrate severity and scope "
            "per this document\n\n" + threat
        )
    res = audit(prompt, payload, llm_cfg)
    if res.skipped_reason is None:
        save_cache(target, new_cache)  # commit cache only on real response
        result.add(res.findings)
        return f"audited {len(payload)} files ({len(unchanged)} unchanged/cached)"
    return f"skipped — {res.skipped_reason} ({len(unchanged)} cached)"


def _load_config(target: Path, explicit: Path | None) -> cfgmod.Config:
    """Config or exit 2 — a malformed config must not silently weaken ignores."""
    try:
        return cfgmod.load(target=target, explicit=explicit)
    except ValueError as exc:
        print(f"guarddog: {exc}", file=sys.stderr)
        raise SystemExit(2)


def cmd_scan(args: argparse.Namespace) -> int:
    target = Path(args.target).resolve()
    if not target.is_dir():
        print(f"guarddog: target not found: {target}", file=sys.stderr)
        return 2
    cfg = _load_config(target, args.config)
    only = None
    rel_base = target
    if args.staged:
        staged = _staged_relpaths(target)
        if staged is None:
            print("guarddog: not a git repo / no git — full scan instead", file=sys.stderr)
        else:
            rel_base, only = staged
            if not only:
                print("guarddog: nothing staged — nothing to scan", file=sys.stderr)
    result, files = _local_scan(target, cfg, only=only, rel_base=rel_base)
    if not args.no_llm:
        result.llm_note = _llm_scan(target, files, cfg, result)

    fail_on = args.fail_on or cfg.fail_on
    if fail_on.lower() not in ("never", "none", "off"):
        try:
            Severity.from_name(fail_on)
        except ValueError:
            print(f"guarddog: invalid fail_on: {fail_on!r}", file=sys.stderr)
            return 2
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


def cmd_check(args: argparse.Namespace) -> int:
    """Dry-run: shows what a scan would touch — files, LLM payload, token est."""
    target = Path(args.target).resolve()
    if not target.is_dir():
        print(f"guarddog: target not found: {target}", file=sys.stderr)
        return 2
    cfg = _load_config(target, args.config)
    files = list(
        iter_source_files(
            target,
            extensions=cfg.scan_extensions,
            ignore_dirs=cfg.ignore_dirs,
            ignore_files=cfg.ignore_files,
            max_size_kb=cfg.max_file_size_kb,
        )
    )
    print(f"target:        {target}")
    print(f"files scanned: {len(files)}")
    threat = _threat_model(target, cfg)
    print(f"threat model:  {'found' if threat else 'none'}")
    llm_cfg = cfg.llm
    if not llm_cfg.get("enabled", True):
        print("llm:           disabled in config")
        return 0
    from llm_client.context import build_llm_context

    payload, unchanged, _ = build_llm_context(
        target, files, max_files=int(llm_cfg.get("max_files", 40))
    )
    chars = sum(len(p["content"]) for p in payload)
    key = (
        "set"
        if os.environ.get("GUARDDOG_API_KEY") or os.environ.get("GEMINI_API_KEY")
        else "not set"
    )
    print(f"llm provider:  {llm_cfg.get('provider', 'gemini')} (api key {key})")
    print(f"llm payload:   {len(payload)} changed, {len(unchanged)} cached")
    print(f"llm size:      {chars} chars (~{chars // 4} tokens est.)")
    return 0


def _ok(cond: object, msg: str = "") -> None:
    if not cond:
        raise AssertionError(msg or "check failed")


def _st_rules_table() -> None:
    from parsers.rules import HINTS, RULES

    _ok(RULES, "empty rule table")
    ids = [r.rule_id for r in RULES]
    _ok(len(ids) == len(set(ids)), "duplicate rule ids")
    missing = [i for i in ids if i not in HINTS]
    _ok(not missing, f"rules without hints: {missing}")


def _st_walker() -> None:
    import tempfile

    from parsers.walker import iter_source_files

    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        (root / "keep.py").write_text("x = 1\n", encoding="utf-8")
        skip = root / "node_modules"
        skip.mkdir()
        (skip / "junk.py").write_text("y = 2\n", encoding="utf-8")
        cfg = cfgmod.load(target=root)
        seen = [
            p.name
            for p in iter_source_files(
                root,
                cfg.scan_extensions,
                cfg.ignore_dirs,
                cfg.ignore_files,
                cfg.max_file_size_kb,
            )
        ]
        _ok(seen == ["keep.py"], f"walker saw {seen}")


def _st_pipeline() -> None:
    import tempfile

    from parsers.findings import Severity

    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        (root / "app.py").write_text(
            'password = "x12345"\nimport os\nos.system("ls")\n', encoding="utf-8"
        )
        cfg = cfgmod.load(target=root)
        result, _files = _local_scan(root, cfg)
        got = {f.rule_id for f in result.findings}
        _ok({"hardcoded-secret", "os-system"} <= got, f"missing {got}")
        _ok(result.exit_code("critical") == 1)
        _ok(result.exit_code("never") == 0)
        _ok(all(f.recommendation for f in result.findings), "missing hints")
        _ok(Severity.CRITICAL > Severity.HIGH)


def _st_dedupe() -> None:
    from parsers.findings import Finding, ScanResult, Severity

    r = ScanResult(target="t", files_scanned=1)
    f = Finding("x", Severity.LOW, "a.py", 1, "m")
    r.add([f])
    r.add([f])
    _ok(len(r.findings) == 1, "dedupe broken")


def _st_renderers() -> None:
    import json

    from parsers.findings import Finding, ScanResult, Severity

    r = ScanResult(target="t", files_scanned=1)
    r.add([Finding("r", Severity.HIGH, "a.py", 1, "m", recommendation="fix it")])
    for fmt in ("md", "json", "html"):
        out = render(r, fmt, SCANNER_ROOT / "templates")
        _ok("fix it" in out, f"{fmt} lost the fix")
    json.loads(render(r, "json", SCANNER_ROOT / "templates"))


def _st_config_merge() -> None:
    import tempfile

    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        (root / ".guarddog.json").write_text(
            '{"ignore_dirs": ["custom"], "fail_on": "low"}', encoding="utf-8"
        )
        cfg = cfgmod.load(target=root)
        _ok("custom" in cfg.ignore_dirs and "node_modules" in cfg.ignore_dirs)
        _ok(cfg.fail_on == "low")
    with tempfile.TemporaryDirectory() as td2:
        bad = Path(td2)
        (bad / ".guarddog.json").write_text("{bad", encoding="utf-8")
        try:
            cfgmod.load(target=bad)
            raised = False
        except ValueError:
            raised = True
        _ok(raised, "malformed config silently accepted")


def _st_suppression() -> None:
    from parsers.regex_scanner import suppressed

    _ok(suppressed("x  # guarddog: ignore", "any"))
    _ok(suppressed("x  # guarddog: ignore eval-exec", "eval-exec"))
    _ok(not suppressed("x  # guarddog: ignore eval", "eval-exec"))


def _st_cache() -> None:
    import tempfile

    from llm_client.context import build_llm_context, save_cache

    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        f = root / "a.py"
        f.write_text("x = 1\n", encoding="utf-8")
        payload, unchanged, cache = build_llm_context(root, [f], 40)
        _ok(len(payload) == 1 and not unchanged)
        save_cache(root, cache)
        payload, unchanged, _ = build_llm_context(root, [f], 40)
        _ok(not payload and unchanged == ["a.py"], "cache diff broken")


def _st_llm_offline() -> None:
    from llm_client.client import audit

    res = audit("p", [], {"provider": "gemini"})
    _ok(res.skipped_reason, "empty payload should skip")
    res = audit("p", [{"path": "a", "content": "b"}], {"provider": "nope"})
    _ok(res.skipped_reason and "unknown provider" in res.skipped_reason)


def _st_threat() -> None:
    import tempfile

    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        (root / "threat_model.md").write_text("RULES", encoding="utf-8")
        cfg = cfgmod.load(target=root)
        _ok(_threat_model(root, cfg) == "RULES")


SELF_CHECKS: list[tuple[str, Callable[[], None]]] = [
    ("rules table + hints", _st_rules_table),
    ("walker + ignores", _st_walker),
    ("regex+AST pipeline", _st_pipeline),
    ("finding dedupe", _st_dedupe),
    ("renderers md/json/html", _st_renderers),
    ("config merge + malformed", _st_config_merge),
    ("suppression tokens", _st_suppression),
    ("llm hash-cache", _st_cache),
    ("llm skip paths", _st_llm_offline),
    ("threat model read", _st_threat),
]


def cmd_selftest() -> int:
    """Runs every core component on embedded fixtures — no network, no key.

    FAIL prints the first error so a broken component is identifiable
    without a debugger.
    """
    fails = 0
    for name, fn in SELF_CHECKS:
        try:
            fn()
            print(f"OK   {name}")
        except Exception as exc:
            fails += 1
            print(f"FAIL {name}  — {type(exc).__name__}: {exc}")
    print(f"selftest: {len(SELF_CHECKS) - fails}/{len(SELF_CHECKS)} components healthy")
    return 1 if fails else 0


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
    cmds = {"scan", "install-hook", "rules", "cache", "check", "selftest"}
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
    if args.cmd == "check":
        return cmd_check(args)
    if args.cmd == "selftest":
        return cmd_selftest()
    return cmd_scan(args)
