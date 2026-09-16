# Unflake (Cursor rule)

When tests fail intermittently in this project:

1. Do NOT suggest deleting the test or re-running until green.
2. Run the static scan: `python3 -m unflake scan <changed-tests>` and report rule IDs.
3. If JUnit XML from repeated runs exists, score it: `python3 -m unflake analyze run*.xml`.
4. Propose quarantine (not deletion) via `python3 -m unflake quarantine run*.xml --framework <pytest|jest|vitest|playwright>`.
5. Prefer fixes: polling with timeout, frozen time, seeded RNG, mocked network, OS-assigned ports.
