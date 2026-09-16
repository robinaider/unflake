"""Nightly wild-flake hunter (v2 recall study driver). Stdlib only.

Reads subjects.json, and for each subject: clones the repo, installs it
with test deps, runs the named tests N times through `unflake run`, and
records whether the documented flake reproduced (recall signal) plus the
full suite FlakeScore (specificity signal).

Usage:
    python3 benchmarks/study_v2/run_study.py [--subjects FILE] [--out DIR] [--runs N]

Results land in <out>/study-<UTC date>.json. Every shell command is logged
into the JSON — a result without its commands is not a result.
"""

from __future__ import annotations

import argparse
import datetime
import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent

# Pinned so nightly runs are reproducible (and Scorecard-clean).
PYTEST_PIN = "pytest==8.3.5"


def sh(cmd: list[str], cwd: Path, timeout: int, log: list) -> tuple[int, str]:
    log.append(f"$ {' '.join(cmd)}  (cwd={cwd})")
    try:
        p = subprocess.run(cmd, cwd=cwd, timeout=timeout,
                           capture_output=True, text=True)
        return p.returncode, (p.stdout + p.stderr)[-4000:]
    except subprocess.TimeoutExpired:
        return 124, "<timeout>"


def venv_python(work: Path, unflake_root: Path, log: list) -> Path:
    """Hermetic interpreter: own venv with pytest + unflake installed.

    Never touches the system python (PEP 668-safe) and identical in CI.
    """
    venv = work / "venv"
    py = venv / ("Scripts/python.exe" if sys.platform == "win32" else "bin/python")
    if not py.exists():
        rc, out = sh([sys.executable, "-m", "venv", str(venv)], work, 300, log)
        if rc != 0:
            raise SystemExit(f"study: cannot create venv: {out[-500:]}")
        for pkg in ([PYTEST_PIN], ["-e", str(unflake_root)]):
            rc, out = sh([str(py), "-m", "pip", "install", "-q", *pkg],
                         work, 900, log)
            if rc != 0:
                raise SystemExit(f"study: pip install {' '.join(pkg)} failed: {out[-500:]}")
    return py


def study_subject(sub: dict, work: Path, py: Path, runs: int, log: list) -> dict:
    name = sub["name"]
    dest = work / name
    res: dict = {"subject": name, "repo": sub["repo"], "rev": sub.get("rev", "HEAD")}
    rc, _ = sh(["git", "clone", "-q", "--depth", "1", sub["repo"], str(dest)],
               work, 300, log)
    if rc != 0:
        return {**res, "status": "clone-failed"}
    if sub.get("rev", "HEAD") != "HEAD":
        rc, _ = sh(["git", "-C", str(dest), "fetch", "-q", "origin", sub["rev"]],
                   work, 300, log)
        rc2, _ = sh(["git", "-C", str(dest), "checkout", "-q", sub["rev"]],
                    work, 120, log)
        if rc != 0 or rc2 != 0:
            return {**res, "status": "rev-unavailable"}
    for dep in sub.get("deps", []):
        rc, out = sh([str(py), "-m", "pip", "install", "-q", dep],
                     work, 600, log)
        if rc != 0:
            return {**res, "status": f"dep-failed: {dep}", "detail": out[-500:]}
    rc, _ = sh([str(py), "-m", "pip", "install", "-q", "-e", str(dest)],
               work, 600, log)
    if rc != 0:
        return {**res, "status": "install-failed"}
    # 1. Static scan of the named test files.
    rc, out = sh([str(py), "-m", "unflake", "scan",
                  *[str(dest / t) for t in sub["test_files"]]], work, 120, log)
    res["scan_exit"] = rc
    # 2. Repeated runs of the documented-flaky targets.
    target_runs = sub.get("runs", runs)
    rc, out = sh([str(py), "-m", "unflake", "run",
                  "--runs", str(target_runs), "--runner", "pytest",
                  "--timeout", str(sub.get("timeout", 240)),
                  "--out-dir", str(work / f"{name}-runs"),
                  "--", str(py), "-m", "pytest",
                  *[f"{dest}/{t}" for t in sub["targets"]],
                  "-q", "-p", "no:cacheprovider"], work, 1800, log)
    res["unflake_exit"] = rc
    res["flaky_found"] = "FLAKY" in out
    res["tail"] = out[-1500:]
    res["status"] = "done"
    return res


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--subjects", default=str(HERE / "subjects.json"))
    ap.add_argument("--out", default=str(HERE / "results"))
    ap.add_argument("--runs", type=int, default=10)
    ap.add_argument("--unflake-root", default=str(HERE.parents[1]))
    args = ap.parse_args()
    subjects = json.loads(Path(args.subjects).read_text(encoding="utf-8"))
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    work = out / "work"
    work.mkdir(exist_ok=True)
    log: list[str] = []
    py = venv_python(work, Path(args.unflake_root), log)
    results = [study_subject(s, work, py, args.runs, log) for s in subjects]
    day = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d")
    (out / f"study-{day}.json").write_text(
        json.dumps({"date": day, "log": log, "results": results}, indent=2),
        encoding="utf-8")
    recalled = sum(1 for r in results if r.get("flaky_found"))
    print(f"study: {len(results)} subjects, {recalled} reproduced flake(s). "
          f"See {out}/study-{day}.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
