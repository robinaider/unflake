"""Ingest test results from JUnit XML and generic JSON result files.

Universal input: anything that can emit JUnit XML works
(pytest --junitxml, jest-junit, vitest --reporter=junit, Playwright,
JUnit/Gradle, go-junit-report, ...). No framework SDK required.
"""

from __future__ import annotations

import json
import xml.etree.ElementTree as ET
from pathlib import Path

PASS = "passed"
FAIL = "failed"
SKIP = "skipped"


def _test_id(classname: str, name: str, filepath: str = "") -> str:
    if classname:
        return f"{classname}::{name}"
    if filepath:
        return f"{filepath}::{name}"
    return name


def parse_junit_xml(path: str | Path) -> dict[str, str]:
    """Parse one JUnit XML file -> {test_id: status}."""
    path = Path(path)
    try:
        tree = ET.parse(path)
    except ET.ParseError as exc:
        raise ValueError(f"{path}: not valid XML ({exc})") from exc
    root = tree.getroot()
    results: dict[str, str] = {}
    suites = [root] if root.tag == "testsuite" else root.findall("testsuite")
    if not suites and root.tag != "testsuite":
        raise ValueError(f"{path}: no <testsuite> found, is this JUnit XML?")
    for suite in suites:
        for case in suite.iter("testcase"):
            name = case.get("name", "unknown")
            classname = case.get("classname", "") or ""
            filepath = case.get("file", "") or ""
            tid = _test_id(classname, name, filepath)
            if case.find("failure") is not None or case.find("error") is not None:
                status = FAIL
            elif case.find("skipped") is not None:
                status = SKIP
            else:
                status = PASS
            results[tid] = status
    return results


def parse_generic_json(path: str | Path) -> dict[str, str]:
    """Parse {"tests": [{"id": ..., "status": "passed|failed|skipped"}]}."""
    path = Path(path)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"{path}: not valid JSON ({exc})") from exc
    items = data.get("tests", data if isinstance(data, list) else [])
    results: dict[str, str] = {}
    for item in items:
        tid = str(item.get("id", item.get("name", "unknown")))
        status = str(item.get("status", item.get("outcome", PASS))).lower()
        if status in {"failure", "fail", "failed", "error"}:
            status = FAIL
        elif status in {"skip", "skipped", "xskip"}:
            status = SKIP
        else:
            status = PASS
        results[tid] = status
    return results


def parse_file(path: str | Path) -> dict[str, str]:
    """Auto-detect format by extension/content -> {test_id: status}."""
    path = Path(path)
    if not path.exists():
        raise ValueError(f"{path}: file not found")
    if path.suffix.lower() == ".json":
        return parse_generic_json(path)
    head = path.read_bytes()[:2000].lstrip()
    if head.startswith(b"{") or head.startswith(b"["):
        return parse_generic_json(path)
    return parse_junit_xml(path)


def load_runs(paths: list[str | Path]) -> list[dict[str, str]]:
    """Load N result files (e.g. N repeated runs of the same suite)."""
    runs = []
    for p in paths:
        runs.append(parse_file(p))
    return runs
