#!/usr/bin/env bash
# Unflake 60-second demo — the whole loop on fixtures, no install.
# Usage:  bash demo.sh   (or: pip install unflake, then drop PYTHONPATH=src)
set -u
cd "$(dirname "$0")"
if command -v unflake >/dev/null 2>&1; then
  U="unflake"
else
  export PYTHONPATH="src${PYTHONPATH:+:$PYTHONPATH}"  # zero-install fallback
  U="python3 -m unflake"
fi

echo "=== 1/4  scan: smells, instantly (Python + JS fixtures) ==="
$U scan examples/
echo
echo "=== 2/4  analyze: FlakeScore across 3 runs (JUnit fixtures) ==="
$U analyze fixtures/runs/run1.xml fixtures/runs/run2.xml fixtures/runs/run3.xml || true
echo
echo "=== 3/4  quarantine: gating stays green, nightly still reports ==="
$U quarantine fixtures/runs/run1.xml fixtures/runs/run2.xml fixtures/runs/run3.xml --framework pytest
echo
echo "=== 4/4  init: prevention scaffold (stdout preview) ==="
$U init --framework pytest | head -6
echo
echo "Done. Your repo next: unflake scan tests/  |  unflake run --runs 3 -- pytest -q"
