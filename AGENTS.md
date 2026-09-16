# Unflake rules — loaded as always-on context by every agent host

This repo ships the Unflake flaky-test hunter. Honor these rules in every session:

1. Never advise deleting a flaky test. Quarantine preserves signal; deletion hides it.
2. Never quarantine a regression (green-then-red-forever) — that's a real failure.
3. One test run proves nothing about flakiness. Ask for ≥2 runs before concluding.
4. When CI is red intermittently: scan first (`unflake scan <path>`), then collect/score (`run` or `analyze` oldest-first), then quarantine (`quarantine --framework ...`).
5. Triage flaky-first, most-flaky first. Stable tests are noise in a flake hunt.
6. Fixes in preference order: polling with timeout (never fixed sleep), frozen time, seeded RNG with logged seed, mocked network boundary, OS-assigned ports.
