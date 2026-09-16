"""`unflake run`: collect the >=2 runs that flake-hunting requires.

Runs your test command N times, collects a JUnit XML per run, then scores.
With a JUnit flag the per-test analysis works; without one, each run's exit
code still gives an honest suite-level verdict (stable vs flaky suite).
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

from .ingest import FAIL, PASS


def _detect_junit_flag(cmd: list[str]) -> str | None:
    joined = " ".join(cmd)
    if "pytest" in cmd[0] or "pytest" in joined.split()[0]:
        return "--junitxml="
    return None


# Verified presets: only runners proven end-to-end (see tests/test_e2e.py).
# Anything else uses --junit-flag explicitly — we'd rather error than guess.
# Each preset is (argv_fn, env_fn|None): some runners take the JUnit path
# as a flag (pytest, vitest), others as an env var (playwright).
def _pytest_args(dest: str) -> list[str]:
    return [f"--junitxml={dest}"]


def _vitest_args(dest: str) -> list[str]:
    return ["--reporter=junit", f"--outputFile={dest}"]


def _playwright_args(dest: str) -> list[str]:
    return ["--reporter=junit"]


def _playwright_env(dest: str) -> dict[str, str]:
    return {"PLAYWRIGHT_JUNIT_OUTPUT_NAME": dest}


def _jest_args(dest: str) -> list[str]:
    # NOTE: space form — `--reporters=jest-junit` breaks reporter parsing.
    return ["--reporters", "jest-junit"]


def _jest_env(dest: str) -> dict[str, str]:
    return {"JEST_JUNIT_OUTPUT_FILE": dest}


RUNNERS = {
    "pytest": (_pytest_args, None),
    "vitest": (_vitest_args, None),
    "playwright": (_playwright_args, _playwright_env),
    "jest": (_jest_args, _jest_env),
}


def resolve_junit_flag(runner: str | None, junit_flag: str | None,
                       cmd: list[str]) -> str | None:
    """Explicit --junit-flag wins; --runner pytest/vitest are verified; anything
    else falls back to pytest auto-detect, else exit-code-only mode."""
    if junit_flag:
        return junit_flag
    if runner:
        if runner not in RUNNERS:
            raise ValueError(f"unknown --runner {runner!r} (try: {', '.join(sorted(RUNNERS))})")
        return None  # preset handled via runner_args(), not a single flag
    return _detect_junit_flag(cmd)


def runner_args(runner: str | None, dest: str) -> list[str] | None:
    """Extra argv for a verified preset, or None."""
    if runner and runner in RUNNERS:
        return RUNNERS[runner][0](dest)
    return None


def runner_env(runner: str | None, dest: str) -> dict[str, str]:
    """Extra env for a verified preset (empty when the path goes via argv)."""
    if runner and runner in RUNNERS:
        fn = RUNNERS[runner][1]
        return dict(fn(dest)) if fn else {}
    return {}


def collect(cmd: list[str], runs: int, out_dir: str | Path,
            junit_flag: str | None = None, runner: str | None = None,
            timeout: float | None = None,
            progress=None) -> list[Path]:
    """Run cmd N times. Return per-run result files (JUnit XML if possible,
    else generic JSON with one suite-level entry)."""
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    if runner and runner not in RUNNERS:
        raise ValueError(f"unknown --runner {runner!r} (try: {', '.join(sorted(RUNNERS))})")
    single = resolve_junit_flag(runner, junit_flag, cmd)
    flag = single  # legacy single-flag path (explicit --junit-flag or pytest auto-detect)
    files: list[Path] = []
    for i in range(1, runs + 1):
        if progress:
            progress(f"run {i}/{runs}: {' '.join(cmd)}")
        log = open(out / f"run{i}.log", "w", encoding="utf-8")  # closed below
        try:
            dest = out / f"run{i}.xml"
            preset = runner_args(runner, str(dest))
            if preset is not None:
                full = [*cmd, *preset]
            elif flag:
                full = [*cmd, f"{flag}{dest}"]
            else:
                full = None
            if full is not None:
                run_env = dict(os.environ)
                run_env.update(runner_env(runner, str(dest)))
                try:
                    proc = subprocess.run(full, timeout=timeout, env=run_env,
                                          stdout=log, stderr=subprocess.STDOUT)
                    ok = proc.returncode == 0
                except subprocess.TimeoutExpired:
                    ok = False
                if not dest.exists():
                    # Command swallowed the flag (or never wrote XML):
                    # fall back to an exit-code entry so the run still counts.
                    dest = _write_json_fallback(out, i, cmd, ok, timed_out=True)
                files.append(dest)
            else:
                try:
                    proc = subprocess.run(cmd, timeout=timeout,
                                          stdout=log, stderr=subprocess.STDOUT)
                    ok, timed_out = proc.returncode == 0, False
                except subprocess.TimeoutExpired:
                    ok, timed_out = False, True
                files.append(_write_json_fallback(out, i, cmd, ok, timed_out))
        finally:
            log.close()
    return files


def _write_json_fallback(out: Path, i: int, cmd: list[str],
                         ok: bool, timed_out: bool = False) -> Path:
    import json
    dest = out / f"run{i}.json"
    status = PASS if ok else FAIL
    note = "suite exit 0" if ok else ("suite timed out" if timed_out else "suite exit != 0")
    dest.write_text(json.dumps({"tests": [
        {"id": f"suite::{' '.join(cmd)}", "status": status, "note": note},
    ]}), encoding="utf-8")
    return dest
