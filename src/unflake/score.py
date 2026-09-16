"""Flakiness scoring across repeated runs.

Pass result files oldest -> newest. Verdicts per test:

  stable-pass  always green
  stable-fail  always red — a real failure, NOT a flake, never quarantine
  flaky        mixed outcomes with no clean break — quarantine candidate
  regression   green, then red from some run on and never green again
               (needs >= 3 runs; with 2 runs a pass->fail looks identical
               to a flake, so it stays flaky) — fix, never quarantine
  new          only appeared in the latest run — needs more runs
  skipped      never produced a pass/fail

Suite FlakeScore: 0-100, share of non-flaky tests (higher = healthier).
"""

from __future__ import annotations

from dataclasses import dataclass

from .ingest import FAIL, PASS, SKIP


@dataclass
class TestScore:
    id: str
    passes: int
    fails: int
    skips: int
    runs: int
    verdict: str
    flakiness: float  # 0.0 stable .. 1.0 maximally flaky (50/50 split)
    change_point: int | None = None  # 1-based run where a regression starts

    def to_dict(self) -> dict:
        return {
            "id": self.id, "passes": self.passes, "fails": self.fails,
            "skips": self.skips, "runs": self.runs,
            "verdict": self.verdict, "flakiness": round(self.flakiness, 3),
            "change_point": self.change_point,
        }


@dataclass
class SuiteScore:
    tests: list[TestScore]
    flake_score: float
    flaky_count: int
    regression_count: int
    total: int

    def to_dict(self) -> dict:
        return {
            "flake_score": round(self.flake_score, 1),
            "flaky_count": self.flaky_count,
            "regression_count": self.regression_count,
            "total": self.total,
            "tests": [t.to_dict() for t in self.tests],
        }

    def issues(self) -> list[TestScore]:
        """Actionable tests: flaky first, then regressions."""
        return [t for t in self.tests if t.verdict in ("flaky", "regression")]


def _is_clean_break(statuses: list[str]) -> int | None:
    """If statuses are pass* then fail* (skips ignored), return the 1-based
    index of the first fail. Otherwise None."""
    pf = [s for s in statuses if s in (PASS, FAIL)]
    if len(pf) < 3 or PASS not in pf or FAIL not in pf:
        return None
    first_fail = pf.index(FAIL)
    if first_fail == 0:
        return None  # failed from the start — stable-fail territory
    if all(s == FAIL for s in pf[first_fail:]):
        return statuses.index(FAIL) + 1  # 1-based, counting all runs
    return None


def score_runs(runs: list[dict[str, str]]) -> SuiteScore:
    if not runs:
        raise ValueError("need at least one run to score")
    ids: set[str] = set()
    for run in runs:
        ids.update(run.keys())
    tests: list[TestScore] = []
    for tid in sorted(ids):
        statuses = [run.get(tid, "missing") for run in runs]
        present = [s for s in statuses if s != "missing"]
        passes = sum(1 for s in present if s == PASS)
        fails = sum(1 for s in present if s == FAIL)
        skips = sum(1 for s in present if s == SKIP)
        change_point: int | None = None
        if "missing" in statuses:
            if len(present) == 1 and statuses[-1] != "missing":
                verdict, flakiness = "new", 0.0
            else:
                verdict, flakiness = "flaky", 0.5  # appears/disappears
        elif passes and fails:
            cp = _is_clean_break(statuses)
            if cp is not None:
                verdict, flakiness, change_point = "regression", 0.0, cp
            else:
                rate = passes / (passes + fails)
                verdict, flakiness = "flaky", round(1.0 - abs(rate - 0.5) * 2, 3)
        elif fails and not passes:
            verdict, flakiness = ("stable-fail", 0.0) if not skips else ("flaky", 0.3)
        elif passes and not fails:
            verdict, flakiness = ("stable-pass", 0.0) if not skips else ("flaky", 0.2)
        else:
            verdict, flakiness = "skipped", 0.0
        tests.append(TestScore(tid, passes, fails, skips, len(runs),
                               verdict, flakiness, change_point))
    flaky = [t for t in tests if t.verdict == "flaky"]
    regressions = [t for t in tests if t.verdict == "regression"]
    total = len(tests) or 1
    flake_score = 100.0 * (total - len(flaky)) / total
    order = {"flaky": 0, "regression": 1, "stable-fail": 2,
             "new": 3, "stable-pass": 4, "skipped": 5}
    tests.sort(key=lambda t: (order.get(t.verdict, 9), -t.flakiness, t.id))
    return SuiteScore(tests, round(flake_score, 1), len(flaky),
                      len(regressions), len(tests))
