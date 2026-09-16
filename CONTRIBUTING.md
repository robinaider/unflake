# Contributing to Unflake — designed for first-time contributors

Unflake grows by small, reviewable PRs. You don't need permission to start.

## Fastest first PRs (all labeled `good first issue`)

1. **New FLK rule** — one regex + message + fix + one test in `tests/test_unflake.py`.
   Copy `FLK001`, keep false positives near zero (code fences don't count, non-test files don't count).
2. **New harness adapter** — one file + one row in `docs/ADAPTERS.md`. Copy `.cursor/rules/unflake.md`.
3. **New quarantine emitter** — add a framework in `src/unflake/quarantine.py` + test.
4. **Fixture** — a tiny deliberately-flaky test file in `examples/` + expected findings in the PR description.
5. **Translation** — README or SKILL.md in your language (`README.<lang>.md`).

## Rules of the road

- Stdlib only for the core CLI (a security tool shouldn't pull a supply chain of its own).
- Every rule/emitter ships with a test. No test, no merge.
- Never recommend deleting tests — quarantine preserves signal.
- Be honest in benchmarks: method + limitations + reproduce command, or it doesn't ship.
- MIT license; by contributing you agree your PR is MIT-licensed too.

## Dev loop (60 seconds, no install)

```bash
python3 -m unittest discover -s tests
PYTHONPATH=src python3 -m unflake scan examples/flaky-pytest
PYTHONPATH=src python3 -m unflake analyze fixtures/runs/run1.xml fixtures/runs/run2.xml
```
