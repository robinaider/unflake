# Unflake (Copilot instructions)

Flaky-test policy for this project: quarantine, never delete. One run proves
nothing — require >= 2 runs before calling a test flaky. Use the Unflake CLI
(`python3 -m unflake scan|analyze|quarantine`) and the skill in `skills/unflake/SKILL.md`.
Triage flaky-first, most-flaky first.
