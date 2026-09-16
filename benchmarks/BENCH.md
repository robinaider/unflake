# Benchmarks — honest numbers, reproducible method

> Status: fixtures + unit-verified verdicts. No grand claims until the real-repo study below ships.
> Every number here reproduces with one command. If it doesn't, file a bug.

## Fixture benchmark (ships today, runs in CI)

Corpus: `examples/flaky-pytest/test_cart.py` (5 injected anti-pattern classes) +
`examples/flaky-js/login.spec.ts` (FLK009 + FLK010) +
`fixtures/runs/run{1,2,3}.xml` (3 runs, 2 flaky of 4 tests).

Reproduce:

```bash
unflake scan examples/
unflake analyze fixtures/runs/run1.xml fixtures/runs/run2.xml fixtures/runs/run3.xml
```

Expected (v0.3.0): scan reports 6 findings across 5 rule classes on the
Python fixture and 2/2 wait rules on the JS fixture; analyze reports
FlakeScore 50.0/100 with `test_cart::test_discount` and
`test_cart::test_checkout` flaky-first. Scan time on this repo: <1s
(stdlib only, no model calls).

## Real-code validation (measured 2026-09-12, unflake 0.4.0)

**Real suite — `psf/requests` tests** (cloned, ~10 test files):
`unflake scan tests/` → **120 findings in ~0.1s**.
- FLK001 ×3 (sleeps in the local test server) — legit, real flake surface.
- FLK004 ×116 warning + ×1 info — **still noisy**: this suite serves HTTP
  via localhost through variables (`f"http://{host}:{port}"`), which no
  static rule can distinguish from wild-internet calls. Localhost literals
  now downgrade to info; variable-host servers remain the residual gap.
  Per-run `analyze` is the arbiter there, not `scan` — documented, not hidden.
- FLK006 proxy-dict hits from v0.3 are gone: correctly retired by the
  string-literal fix (fixture data, not binds).

**Self-scan** (`scan src tests`): **0 findings** (was 5) — all were
anti-patterns inside string literals in test-writing-tests, now skipped
via stdlib `tokenize` (Python only; JS literal-awareness is open).
`examples/` still reports 7 by design (deliberate fixtures, incl. 1
localhost-downgraded FLK004).

**Real runner** (`tests/test_e2e.py`, pytest 9.1.1): 4-run collection with
per-run JUnit capture → FlakeScore 50.0, 1 flaky (2P/2F), stable test never
quarantined. Runs in CI; skips gracefully without pytest.

**Real runner, JS** (vitest 4.x, verified 2026-09-12): `run --runner vitest`
with per-run `--reporter=junit --outputFile=` on a 3-test suite (1
deterministically flaky) → FlakeScore 66.7, the flaky test triaged first,
exit 1. Raw outputs frozen as `fixtures/runs/vitest-pass.xml` /
`vitest-fail.xml` and scored in `TestVitestCompat` — the preset can't rot
without a test failing.

## Known limitations (good first issues — file them at launch)

1. Variable-host local servers (see above): needs runtime/server-config hints.
2. JS/TS string-literal awareness (Python done via `tokenize`).
3. Two runs can't distinguish regression from flake — by design, documented.

## Verdict checks (unit-tested in `tests/test_unflake.py`)

- pass,pass,fail,fail (≥3 runs, clean break) → REGRESSION with change-point run 3.
- pass,fail over 2 runs → FLAKY (two runs can't distinguish regression from flake).
- pass,fail,pass → FLAKY (no clean break).
- Test appearing only in the latest run → NEW, never flaky.
- Exit-code-only `run` collection (no JUnit flag) still yields honest suite-level verdicts.

## Real-repo study v1 (done 2026-09-12, unflake 0.5.x)

Question: on healthy real suites, does Unflake stay quiet? A hunter that
cries flake at stable tests is worse than none — false-quarantine rate must
be 0. Method: clone 3 dependency-light OSS repos, `scan` them, then
`unflake run --runs 5 --runner pytest` each full suite and score.

| Repo | Tests × runs | Scan findings | FlakeScore | Flaky | Stable-fails* |
|---|---|---|---|---|---|
| `python-attrs/attrs` | 1413 × 5 | 2 (bench sleeps) | 100.0 | 0 | ≥1 (packaging metadata, env breakage) |
| `pallets/click` | 2084 × 5 | 6 (wall clock, concurrency notes) | 100.0 | 0 | 25 (pager tests need `less`) |
| `tqdm/tqdm` | 179 × 5 | 15 (unseeded random, asyncio notes) | 100.0 | 0 | 0 |

\* Stable-fails are environment breakage (missing `less`, editable-install
metadata), identical across all 5 runs. All three suites quarantine
**nothing** — 3,676 tests, 18,380 executions, 0 false quarantines.
`quarantine` output on these runs is empty by construction (only `flaky`
verdicts qualify; `stable-fail` never does).

Honest limits of this study: these suites turned out healthy, so it proves
*specificity* (no false alarms), not *recall* (catching real flakes).
Recall is covered by the deterministic flaky fixtures (pytest/vitest/
playwright/jest e2e) and the `psf/requests` scan above. A v2 study on
suites with known flakes is open — see CONTRIBUTING.md.

## Recall study v2 (harness live, hunting)

Recall needs *wild* flakes — tests someone else already documented as flaky.
Two sourcing channels, both verified working:

1. **IDoFT** (`TestingResearchIllinois/idoft`, `py-data.csv`, 1,618 Python
   rows with project + SHA + pytest test name). Attempted 2026-09-12:
   `spulec/freezegun::test_import_after_start` (listed NOD+NIO) ran 10/10
   stable at HEAD — likely fixed upstream. Honest negative; the subject
   stays in the harness as a regression guard.
2. **Rerun-mining** (Sourcegraph public API): projects that ship
   `pytest-rerunfailures` confess to flakes. Thousands of hits; attempted
   `abey79/vpype` — blocked locally (requires Python <3.14), runs in the
   CI matrix (3.11–3.13) instead.

Prospecting `psf/requests` full suite 5× (635 tests, network+timing heavy):
FlakeScore 100, 0 flaky.

The hunter is automated: `benchmarks/study_v2/run_study.py` (stdlib only,
hermetic venv, every command logged to results JSON) runs nightly via
`.github/workflows/study.yml`. **CI time answer: public repos get unlimited
free Actions minutes** — ~10 min/night is effectively free. Each run either
reproduces a wild flake (recall data + launch content) or extends the
specificity record. Both outcomes ship in this file.

## Recall attempts log (all honest negatives so far)

| Date | Subject | Source | Runs | Result |
|---|---|---|---|---|
| 2026-09-12 | freezegun `test_import_after_start` (IDoFT NOD+NIO) | IDoFT py-data.csv | 10 | stable — likely fixed upstream |
| 2026-09-12 | requests full suite (635 tests) | prospecting | 5 | FlakeScore 100 |
| 2026-09-12 | grabbit `test_core.py[local]` (IDoFT NOD ×5) | IDoFT py-data.csv | 10 | 15 tests stable |
| 2026-09-12 | Flask-JWT-Router `test_routing.py` (IDoFT NOD ×9) | IDoFT py-data.csv | 10 | 15 tests stable |
| 2026-09-12 | tukio | IDoFT (NOD ×9) | — | repo gone (deleted/renamed), dropped |

Notes: IDoFT SHAs are old — most listed flakes appear fixed at HEAD.
Flask-JWT-Router needed 4 dependency rounds (flask → sqlalchemy → dateutil
→ flask-sqlalchemy); collection errors surface as single-item suites, so
always check `run1.log` when a suite reports 1 test. grabbit + Flask-JWT
subjects added to `study_v2/subjects.json` as nightly specificity guards.
