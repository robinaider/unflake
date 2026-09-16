# Changelog — all notable changes, newest first.

## [0.6.1] — scorecard hardening
### Added
- OpenSSF Scorecard push: SHA-pinned Actions, minimal tokens, injection-free
  action, Dependabot (actions/pip/npm), CodeQL (Python+JS), self-score
  workflow, Sigstore-attested releases with PyPI OIDC + npm provenance.
- `docs/SCORECARD.md`: per-check evidence table + repo-settings click-list.

## [0.6.0] — all four runners + real-repo study
### Added
- `--runner playwright`: verified e2e with a real browser test
  (`--reporter=junit` + `PLAYWRIGHT_JUNIT_OUTPUT_NAME`); presets now support
  env-var JUnit paths, not just argv flags.
- `--runner jest`: verified e2e (`--reporters jest-junit` space form +
  `JEST_JUNIT_OUTPUT_FILE`; the `=` form breaks reporter parsing — documented).
- Frozen real outputs: `fixtures/runs/{playwright,jest}-{pass,fail}.xml`
  with `TestJsRunnerFixtures` (runner JUnit drift fails loudly).
- Real-repo study v1: attrs/click/tqdm, 3,676 tests × 5 runs, 0 false
  quarantines — see `benchmarks/BENCH.md`.
- Recall study v2 harness: `benchmarks/study_v2/` (subjects + hermetic driver
  + nightly workflow); first results (freezegun 10× stable, requests 635×5
  clean, vpype blocked on Python pin) documented in BENCH.md.

## [0.5.0] — npx + vitest
### Added
- `unflake-ci` npm package (`npx unflake-ci …`): zero-dep Node shim vendoring
  the Python core (needs Python 3.9+; `sync.py` keeps it byte-identical).
- `--runner vitest`: verified end-to-end against real vitest 4.x JUnit output
  (`--reporter=junit --outputFile=`); fixtures frozen in `fixtures/runs/vitest-*.xml`.
### Notes
- npm name `unflake` was already taken — the wrapper ships as `unflake-ci`;
  PyPI keeps the clean `unflake` name.

## [0.4.0] — precision + integration quality
### Added
- Localhost-aware FLK004: localhost literals downgrade to info with a note.
- String-literal awareness for Python (stdlib `tokenize`): fixture text no longer flagged.
- `scan --exclude`: repeatable path-part globs; defaults skip venvs/build dirs/caches.
- SARIF output now carries full rule metadata (ids, descriptions, fixes).
- Quarantine warns on unsafe `-k` names (spaces/quotes) and suggests `--deselect`.
- CI matrix Python 3.10–3.14; repo dogfoods its own hook (`.pre-commit-config.yaml`).
### Fixed
- Self-scan down to 0 findings; requests-suite FLK006 proxy-dict FPs retired by the literal fix.

## [0.3.0] — launch candidate
### Added
- `run --runner pytest`: verified preset + per-run `.log` capture (stdout stays clean).
- `tests/test_e2e.py`: end-to-end proof on real pytest (skips without pytest; CI installs it).
- `scan` accepts multiple targets (`scan src tests`).
- Launch kit: `demo.sh` 60-second tour, issue/PR templates, `SECURITY.md`, `docs/LAUNCH.md`, `docs/RELEASING.md`, `CHANGELOG.md`.
- `benchmarks/BENCH.md`: real-repo validation (`psf/requests`, 124 findings/0.08s) with documented limitations.
### Fixed
- `scan` rejected multiple paths while CI passed three (exit 2); covered by test.
- Generic-JSON parser didn't recognize its own `"failed"` status word.

## [0.2.0]
### Added
- `run`: collect N runs (JUnit auto-capture for pytest, `--junit-flag` generic, exit-code fallback).
- Verdicts: `regression` with change-point (≥3 runs), `new`; `quarantine` refuses regressions.
- `init`: seeded-RNG scaffolder for pytest/jest/vitest/playwright (`--write` idempotent).
- Rules FLK009 (`cy.wait`), FLK010 (`waitForTimeout`); per-rule file extensions enforced.
- Packaging: `pip install unflake` verified, pre-commit hook, GitHub Action (SARIF + gate).

## [0.1.0]
### Added
- `scan` (8 rules), `analyze` (FlakeScore), `quarantine` (pytest/jest/vitest/playwright).
- JSON + SARIF output, skill (`skills/unflake/SKILL.md`) + 6 harness adapters, CI dogfooding.
