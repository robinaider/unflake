"""`unflake` CLI. Stdlib only. Exit codes: 0 clean, 1 findings, 2 usage."""

from __future__ import annotations

import argparse
import json
import sys

from . import __version__
from .ingest import load_runs
from .patterns import SEVERITIES, Finding, scan_path
from .quarantine import FRAMEWORKS, emit
from .report import (
    format_analyze_text,
    format_sarif,
    format_scan_json,
    format_scan_text,
)
from .runner import collect
from .scaffold import FRAMEWORKS as SCAFFOLD_FRAMEWORKS
from .scaffold import init_framework
from .score import score_runs

ORDER = {"error": 0, "warning": 1, "info": 2}


def _meets_threshold(f: Finding, fail_on: str) -> bool:
    return ORDER[f.severity] <= ORDER[fail_on]


def cmd_scan(args: argparse.Namespace) -> int:
    findings: list[Finding] = []
    for target in args.targets:
        try:
            findings.extend(scan_path(target, exclude=args.exclude))
        except ValueError as exc:
            print(f"unflake: error: {exc}", file=sys.stderr)
            return 2
    if args.format == "json":
        print(format_scan_json(findings))
    elif args.format == "sarif":
        print(format_sarif(findings))
    else:
        print(format_scan_text(findings))
    bad = [f for f in findings if _meets_threshold(f, args.fail_on)]
    return 1 if bad else 0


def _print_suite(suite, fmt: str) -> None:
    if fmt == "json":
        print(json.dumps(suite.to_dict(), indent=2))
    elif fmt == "sarif":
        print(format_sarif([], suite))
    else:
        print(format_analyze_text(suite))


def _analyze_gate(suite, fail_on: str) -> int:
    if fail_on == "never":
        return 0
    if fail_on == "flaky":
        return 1 if (suite.flaky_count or suite.regression_count) else 0
    return 0


def _quarantine_note(suite, framework: str | None) -> None:
    if not framework:
        return
    flaky_ids = [t.id for t in suite.tests if t.verdict == "flaky"]
    if not flaky_ids:
        return
    print()
    print(emit(framework, flaky_ids))


def cmd_analyze(args: argparse.Namespace) -> int:
    try:
        runs = load_runs(args.results)
    except ValueError as exc:
        print(f"unflake: error: {exc}", file=sys.stderr)
        return 2
    if len(runs) < 2:
        print("unflake: warning: only 1 run given — flakiness needs >= 2 runs "
              "of the same suite to compare.", file=sys.stderr)
    suite = score_runs(runs)
    _print_suite(suite, args.format)
    return _analyze_gate(suite, args.fail_on)


def cmd_quarantine(args: argparse.Namespace) -> int:
    try:
        runs = load_runs(args.results)
    except ValueError as exc:
        print(f"unflake: error: {exc}", file=sys.stderr)
        return 2
    suite = score_runs(runs)
    regressions = [t.id for t in suite.tests if t.verdict == "regression"]
    if regressions:
        print("# unflake quarantine: NOT quarantining regressions "
              "(real failures — fix them):", file=sys.stderr)
        for rid in regressions:
            print(f"#  - {rid}", file=sys.stderr)
    flaky_ids = [t.id for t in suite.tests if t.verdict == "flaky"]
    if not flaky_ids:
        print("# unflake quarantine: no flaky tests — nothing to quarantine.")
        return 0
    try:
        print(emit(args.framework, flaky_ids))
    except ValueError as exc:
        print(f"unflake: error: {exc}", file=sys.stderr)
        return 2
    return 0


def cmd_run(args: argparse.Namespace) -> int:
    if args.runs < 2:
        print("unflake: error: --runs must be >= 2 (one run proves nothing)",
              file=sys.stderr)
        return 2
    cmd = list(args.test_command or [])
    if cmd[:1] == ["--"]:
        cmd = cmd[1:]  # argparse.REMAINDER keeps the separator
    if not cmd:
        print("unflake: error: no test command given after `--`", file=sys.stderr)
        return 2
    try:
        files = collect(
            cmd, runs=args.runs, out_dir=args.out_dir,
            junit_flag=args.junit_flag, runner=args.runner, timeout=args.timeout,
            progress=lambda m: print(f"unflake: {m}", file=sys.stderr),
        )
    except ValueError as exc:
        print(f"unflake: error: {exc}", file=sys.stderr)
        return 2
    print(f"unflake: collected {len(files)} run(s) in {args.out_dir}", file=sys.stderr)
    suite = score_runs(load_runs(files))
    _print_suite(suite, args.format)
    _quarantine_note(suite, args.quarantine)
    return _analyze_gate(suite, args.fail_on)


def cmd_init(args: argparse.Namespace) -> int:
    try:
        print(init_framework(args.framework, root=args.root, write=args.write))
    except ValueError as exc:
        print(f"unflake: error: {exc}", file=sys.stderr)
        return 2
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="unflake",
        description="Green CI without the rerun ritual — detect, score, quarantine flaky tests.",
    )
    p.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    sub = p.add_subparsers(dest="command", required=True)

    s = sub.add_parser("scan", help="Static scan for flake anti-patterns (no test execution).")
    s.add_argument("targets", nargs="+", help="File(s) or directorie(s) to scan.")
    s.add_argument("--exclude", action="append", default=[],
                   help="Extra path-part glob to skip (repeatable; "
                        "defaults already skip .git, node_modules, venvs, build dirs).")
    s.add_argument("--format", choices=["text", "json", "sarif"], default="text")
    s.add_argument("--fail-on", choices=list(SEVERITIES), default="warning",
                   help="Exit 1 if any finding at/above this severity (default: warning).")
    s.set_defaults(func=cmd_scan)

    a = sub.add_parser("analyze", help="Score flakiness across >=2 result files (JUnit XML or JSON).")
    a.add_argument("results", nargs="+", help="Result files from repeated runs, oldest first.")
    a.add_argument("--format", choices=["text", "json", "sarif"], default="text")
    a.add_argument("--fail-on", choices=["flaky", "never"], default="never",
                   help="'flaky' exits 1 on flaky tests OR regressions.")
    a.set_defaults(func=cmd_analyze)

    q = sub.add_parser("quarantine", help="Emit quarantine config for flaky tests (never deletes).")
    q.add_argument("results", nargs="+", help="Result files from repeated runs, oldest first.")
    q.add_argument("--framework", choices=list(FRAMEWORKS), required=True)
    q.set_defaults(func=cmd_quarantine)

    r = sub.add_parser("run", help="Run your test command N times, then score (collects JUnit when possible).")
    r.add_argument("--runs", type=int, default=3, help="Repeat count, >= 2 (default: 3).")
    r.add_argument("--out-dir", default=".unflake/runs", help="Where per-run files land.")
    r.add_argument("--junit-flag", default=None,
                   help="Flag your runner uses for JUnit output, e.g. '--junitxml=' "
                        "(auto-detected for pytest; omit for exit-code-only mode).")
    r.add_argument("--runner", default=None,
                   help="Verified runner preset (pytest, vitest, playwright, jest). "
                        "Others: use --junit-flag.")
    r.add_argument("--timeout", type=float, default=None, help="Per-run timeout in seconds.")
    r.add_argument("--format", choices=["text", "json", "sarif"], default="text")
    r.add_argument("--fail-on", choices=["flaky", "never"], default="flaky")
    r.add_argument("--quarantine", choices=list(FRAMEWORKS), default=None,
                   help="Also emit a quarantine snippet for this framework.")
    r.add_argument("test_command", nargs=argparse.REMAINDER,
                   help="Test command after `--`, e.g. `-- pytest tests/ -q`.")
    r.set_defaults(func=cmd_run)

    i = sub.add_parser("init", help="Scaffold seeded-RNG / frozen-time helpers for a framework.")
    i.add_argument("--framework", choices=list(SCAFFOLD_FRAMEWORKS), required=True)
    i.add_argument("--root", default=".", help="Project root to write into.")
    i.add_argument("--write", action="store_true",
                   help="Write files (idempotent). Without it, print to stdout.")
    i.set_defaults(func=cmd_init)
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
