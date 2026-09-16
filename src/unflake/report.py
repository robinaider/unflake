"""Report formatters: text (human), json (machine), sarif (code scanning)."""

from __future__ import annotations

import json

from .patterns import RULES, Finding
from .score import SuiteScore

ORDER = {"error": 0, "warning": 1, "info": 2}


def _sarif_rules() -> list[dict]:
    rules = [{
        "id": f"unflake/{r.id}",
        "shortDescription": {"text": r.message},
        "help": {"text": r.fix},
        "defaultConfiguration": {"level": {"error": "error", "warning": "warning"}.get(r.severity, "note")},
    } for r in RULES]
    rules += [
        {"id": "unflake/FLAKY",
         "shortDescription": {"text": "Mixed outcomes across repeated runs — quarantine candidate."},
         "defaultConfiguration": {"level": "warning"}},
        {"id": "unflake/REGRESSION",
         "shortDescription": {"text": "Green-then-red-forever — real failure, never quarantine."},
         "defaultConfiguration": {"level": "error"}},
    ]
    return rules


def format_scan_text(findings: list[Finding]) -> str:
    if not findings:
        return "unflake scan: clean — no flake anti-patterns found."
    lines = [f"unflake scan: {len(findings)} finding(s)"]
    for f in sorted(findings, key=lambda x: (ORDER[x.severity], x.file, x.line)):
        lines.append(f"  {f.severity.upper():7} [{f.rule}] {f.file}:{f.line}")
        lines.append(f"           {f.message}")
        if f.fix:
            lines.append(f"           fix: {f.fix}")
    return "\n".join(lines)


def format_scan_json(findings: list[Finding]) -> str:
    return json.dumps({"findings": [f.to_dict() for f in findings]}, indent=2)


def format_sarif(findings: list[Finding], suite: SuiteScore | None = None) -> str:
    results = []
    for f in findings:
        level = {"error": "error", "warning": "warning", "info": "note"}[f.severity]
        results.append({
            "ruleId": f"unflake/{f.rule}",
            "level": level,
            "message": {"text": f"{f.message} Fix: {f.fix}" if f.fix else f.message},
            "locations": [{
                "physicalLocation": {
                    "artifactLocation": {"uri": f.file},
                    "region": {"startLine": f.line},
                }
            }],
        })
    if suite:
        for t in suite.tests:
            if t.verdict == "flaky":
                results.append({
                    "ruleId": "unflake/FLAKY",
                    "level": "warning",
                    "message": {"text": f"Flaky across {t.runs} runs: "
                                         f"{t.passes} passed, {t.fails} failed."},
                    "locations": [{
                        "physicalLocation": {
                            "artifactLocation": {"uri": t.id},
                            "region": {"startLine": 1},
                        }
                    }],
                })
            elif t.verdict == "regression":
                results.append({
                    "ruleId": "unflake/REGRESSION",
                    "level": "error",
                    "message": {"text": f"Regression: green until run {t.change_point}, "
                                         f"red ever since. Fix — do not quarantine."},
                    "locations": [{
                        "physicalLocation": {
                            "artifactLocation": {"uri": t.id},
                            "region": {"startLine": 1},
                        }
                    }],
                })
    return json.dumps({
        "$schema": "https://json.schemastore.org/sarif-2.1.0.json",
        "version": "2.1.0",
        "runs": [{
            "tool": {"driver": {
                "name": "unflake",
                "informationUri": "https://github.com/robinaider/unflake",
                "rules": _sarif_rules(),
            }},
            "results": results,
        }],
    }, indent=2)


def format_analyze_text(suite: SuiteScore) -> str:
    lines = [
        f"FlakeScore: {suite.flake_score}/100 "
        f"({suite.flaky_count} flaky of {suite.total} tests)"
    ]
    for t in suite.tests:
        if t.verdict == "flaky":
            lines.append(f"  FLAKY {t.id} ({t.passes}P/{t.fails}F over {t.runs} runs)")
    for t in suite.tests:
        if t.verdict == "regression":
            lines.append(f"  REGRESSION {t.id} (green until run {t.change_point}, "
                         f"red ever since — fix this, do NOT quarantine it)")
    for t in suite.tests:
        if t.verdict == "new":
            lines.append(f"  NEW {t.id} (only in latest run — needs more runs before judging)")
    stables = [t for t in suite.tests
               if t.verdict in ("stable-pass", "stable-fail", "skipped")]
    if stables:
        lines.append(f"  ... +{len(stables)} stable/skipped test(s) (see --format json for full list)")
    return "\n".join(lines)
