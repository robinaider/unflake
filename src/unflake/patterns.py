"""Static scan for flaky-test anti-patterns. No execution, no dependencies.

Each rule is (id, severity, languages, check) so contributors can add
a rule with a single function + one test. See CONTRIBUTING.md.
"""

from __future__ import annotations

import fnmatch
import io
import re
import tokenize
from dataclasses import dataclass
from pathlib import Path

SEVERITIES = ("error", "warning", "info")

TEST_FILE_HINT = re.compile(r"(test_|_test\.|\.spec\.|\.test\.)", re.IGNORECASE)
TEST_DIR_HINT = re.compile(r"(^|/)(test|tests|__tests__|spec|e2e)($|/)")
CODE_FENCE = "```"

SCAN_EXTENSIONS = {".py", ".js", ".ts", ".tsx", ".jsx", ".mts", ".cts", ".go", ".rb"}

PY_EXTS = (".py",)
JS_EXTS = (".js", ".ts", ".tsx", ".jsx", ".mts", ".cts")
ALL_EXTS = tuple(sorted(SCAN_EXTENSIONS))


@dataclass
class Finding:
    rule: str
    severity: str
    file: str
    line: int
    message: str
    fix: str = ""

    def to_dict(self) -> dict:
        return {
            "rule": self.rule,
            "severity": self.severity,
            "file": self.file,
            "line": self.line,
            "message": self.message,
            "fix": self.fix,
        }


@dataclass
class Rule:
    id: str
    severity: str
    pattern: re.Pattern
    message: str
    fix: str
    extensions: tuple = ALL_EXTS
    test_files_only: bool = True
    # Precision valve: when downgrade_if matches the same line, the finding
    # drops to downgrade_to with a note instead of firing at full severity.
    downgrade_if: re.Pattern | None = None
    downgrade_to: str = "info"
    downgrade_note: str = ""


RULES: list[Rule] = [
    Rule(
        "FLK001", "warning",
        re.compile(r"\btime\.sleep\s*\("),
        "time.sleep() in tests makes timing-dependent flakes",
        "Replace with polling (wait_for / waitFor / eventually) with a timeout, or freeze time.",
    ),
    Rule(
        "FLK002", "warning",
        re.compile(r"\b(datetime\.now|datetime\.utcnow|time\.time|Date\.now|new Date\(\))\s*\("),
        "Unfrozen wall-clock reads make tests date/time dependent",
        "Freeze time (freezegun, jest.useFakeTimers, MockDate) or inject a clock.",
    ),
    Rule(
        "FLK003", "warning",
        re.compile(r"\b(random\.(random|randint|choice|shuffle|uniform)|Math\.random\s*\()"),
        "Unseeded randomness makes failures unreproducible",
        "Seed the RNG (random.seed / faker.seed) and log the seed on failure.",
    ),
    Rule(
        "FLK004", "warning",
        re.compile(r"\b(requests\.(get|post|put|delete)|urllib\.request\.urlopen|fetch\s*\(|axios\.(get|post)|http\.(get|request))\s*\("),
        "Real network calls in tests fail without mocks and leak outside hermetic CI",
        "Mock the boundary (responses, nock, MSW, httpretty) or mark the test integration-only.",
        ALL_EXTS, True,
        re.compile(r"(localhost|127\.0\.0\.1|::1)"),
        "info",
        " (localhost server — hermetic but still a startup-race/port source)",
    ),
    Rule(
        "FLK005", "info",
        re.compile(r"for\s+\w+\s+in\s+set\s*\("),
        "Iterating a set() has nondeterministic order across runs",
        "Iterate over sorted(...) if order matters, or compare as sets.",
    ),
    Rule(
        "FLK006", "info",
        re.compile(r"(localhost|127\.0\.0\.1)\s*:\s*\d{2,5}|port\s*=\s*\d{2,5}"),
        "Hardcoded ports collide on shared/parallel CI runners",
        "Bind port 0 / let the OS pick, then read back the assigned port.",
    ),
    Rule(
        "FLK007", "warning",
        re.compile(r"(\.only\s*\(|describe\.only|it\.only|test\.only|@pytest\.mark\.skip\s*\(\s*\)|@unittest\.skip\s*\(\s*\))"),
        ".only / bare skip markers suggest a suite that is already being triaged around flakes",
        "Quarantine the flaky test explicitly (unflake quarantine) instead of .only/skip.",
    ),
    Rule(
        "FLK008", "info",
        re.compile(r"(concurrent|Parallel|Promise\.all|asyncio\.gather|ThreadPool|go\s+func)"),
        "Concurrency without deterministic synchronization is a classic flake source",
        "Join/await explicitly, avoid asserting on racy intermediate state.",
        ALL_EXTS,
    ),
    Rule(
        "FLK009", "warning",
        re.compile(r"cy\.wait\(\s*\d+"),
        "cy.wait(ms) fixed waits pass locally and flake on loaded CI runners",
        "Wait on state instead: cy.intercept() + cy.wait('@alias'), or .should() retry-ability.",
        JS_EXTS,
    ),
    Rule(
        "FLK010", "warning",
        re.compile(r"(waitForTimeout|wait_for_timeout)\s*\("),
        "Fixed-time waits (waitForTimeout / wait_for_timeout) are Playwright's documented flake factory",
        "Use web-first assertions: await expect(locator).toBeVisible() auto-retries.",
        JS_EXTS + PY_EXTS,
    ),
]


def _is_test_file(path: Path) -> bool:
    s = str(path)
    return bool(TEST_FILE_HINT.search(path.name) or TEST_DIR_HINT.search(s))


DEFAULT_EXCLUDES = (".git", "node_modules", "__pycache__", ".venv", "venv",
                    "dist", "build", ".tox", ".pytest_cache", ".eggs", "*.egg-info")


def _literal_spans(suffix: str, text: str) -> dict[int, list[tuple[int, int]]]:
    """String-literal spans per scanner: tokenize for Python, hand-rolled
    for JS/TS. Anything else yields {} (no skipping — never hide signal)."""
    if suffix == ".py":
        return _string_spans(text)
    if suffix in JS_EXTS:
        return _js_string_spans(text)
    return {}


def _string_spans(text: str) -> dict[int, list[tuple[int, int]]]:
    """Map 1-based lineno -> string-literal column spans, via stdlib tokenize.

    Matches fully inside a literal are fixture text, not executed code.
    Python only; unparseable files yield {} (no skipping — never hide signal).
    """
    spans: dict[int, list[tuple[int, int]]] = {}
    try:
        toks = tokenize.generate_tokens(io.StringIO(text).readline)
        for tok in toks:
            if tok.type not in (tokenize.STRING, getattr(tokenize, "FSTRING_MIDDLE", -1)):
                continue
            (srow, scol), (erow, ecol) = tok.start, tok.end
            for r in range(srow, erow + 1):
                spans.setdefault(r, []).append(
                    (scol if r == srow else 0, ecol if r == erow else 10 ** 9))
    except (tokenize.TokenError, SyntaxError, IndentationError):
        return {}
    return spans


def _in_literal(spans: dict[int, list[tuple[int, int]]],
                lineno: int, start: int, end: int) -> bool:
    return any(a <= start and end <= b for a, b in spans.get(lineno, []))


_JS_ID = frozenset(
    "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_$")


def _scan_js_regex(text: str, i: int, n: int) -> int:
    """End index (exclusive) of a regex starting at text[i]=='/', or -1.

    Honors backslash escapes and [/]-classes. A literal newline aborts:
    JS regexes cannot span lines, so that '/' was division, not a literal.
    """
    j = i + 1
    in_class = False
    while j < n:
        c = text[j]
        if c == "\n":
            return -1
        if c == "\\":
            j += 2
            continue
        if c == "[":
            in_class = True
        elif c == "]":
            in_class = False
        elif c == "/" and not in_class:
            return j + 1
        j += 1
    return -1


def _js_string_spans(text: str) -> dict[int, list[tuple[int, int]]]:
    """Map 1-based lineno -> JS string-literal column spans (hand scanner).

    Covers '...', "..." and `...` minus ${} interpolations, which ARE
    executed code and stay visible. Knows // and /* */ comments so quotes
    inside them don't confuse it. Comments themselves are NOT skipped
    (conservative, like Python: only literals hide matches).

    Regex literals use the standard prev-token heuristic (value before '/'
    means division). When unsure we assume division — a missed skip only
    costs precision, never hides signal. Broken files degrade to visible.
    """
    spans: dict[int, list[tuple[int, int]]] = {}
    n = len(text)

    def add_span(sline: int, scol: int, eline: int, ecol: int) -> None:
        if eline < sline or (eline == sline and ecol <= scol):
            return
        if sline == eline:
            spans.setdefault(sline, []).append((scol, ecol))
            return
        spans.setdefault(sline, []).append((scol, 10 ** 9))
        for r in range(sline + 1, eline):
            spans.setdefault(r, []).append((0, 10 ** 9))
        spans.setdefault(eline, []).append((0, ecol))

    # Frames: ("str", quote, sline, scol) | ("tpl", sline, scol)
    #         ("expr", depth) | ("lcomment",) | ("bcomment",)
    stack: list[tuple] = []
    prev_val = False  # last significant token was a value (=> '/' divides)
    i, line, col = 0, 1, 0

    while i < n:
        ch = text[i]
        nxt = text[i + 1] if i + 1 < n else ""
        top = stack[-1] if stack else None
        kind = top[0] if top else None

        if ch == "\n":
            if kind == "str":
                _, _, sl, sc = stack.pop()  # unterminated: end tolerantly
                add_span(sl, sc, line, col)
                prev_val = False
            elif kind == "lcomment":
                stack.pop()
            i += 1
            line += 1
            col = 0
            continue

        if kind == "lcomment":
            i += 1
            col += 1
            continue
        if kind == "bcomment":
            if ch == "*" and nxt == "/":
                stack.pop()
                i += 2
                col += 2
            else:
                i += 1
                col += 1
            continue
        if kind == "str":
            _, q, sl, sc = top
            if ch == "\\":
                i += 2
                col += 2
                continue
            if ch == q:
                stack.pop()
                add_span(sl, sc, line, col + 1)
                prev_val = True
                i += 1
                col += 1
                continue
            i += 1
            col += 1
            continue
        if kind == "tpl":
            _, sl, sc = top
            if ch == "\\":
                i += 2
                col += 2
                continue
            if ch == "`":
                stack.pop()
                add_span(sl, sc, line, col + 1)
                prev_val = True
                i += 1
                col += 1
                continue
            if ch == "$" and nxt == "{":
                stack.pop()
                add_span(sl, sc, line, col)
                stack.append(("expr", 1))
                prev_val = False
                i += 2
                col += 2
                continue
            i += 1
            col += 1
            continue

        # Code context (top is None or an ("expr", depth) frame).
        if kind == "expr" and ch == "{":
            stack[-1] = ("expr", top[1] + 1)
            prev_val = False
            i += 1
            col += 1
            continue
        if kind == "expr" and ch == "}":
            if top[1] == 1:
                stack.pop()
                stack.append(("tpl", line, col + 1))  # fresh text segment
            else:
                stack[-1] = ("expr", top[1] - 1)
            prev_val = False
            i += 1
            col += 1
            continue
        if ch in " \t\r\f\v":
            i += 1
            col += 1
            continue
        if ch == "/" and nxt == "/":
            stack.append(("lcomment",))
            i += 2
            col += 2
            continue
        if ch == "/" and nxt == "*":
            stack.append(("bcomment",))
            i += 2
            col += 2
            continue
        if ch in "\"'":
            stack.append(("str", ch, line, col))
            prev_val = False
            i += 1
            col += 1
            continue
        if ch == "`":
            stack.append(("tpl", line, col))
            prev_val = False
            i += 1
            col += 1
            continue
        if ch == "/":
            if prev_val:
                prev_val = False  # division
                i += 1
                col += 1
                continue
            end = _scan_js_regex(text, i, n)
            if end == -1:
                prev_val = False
                i += 1
                col += 1
                continue
            while i < end:  # skip the literal, tracking lines (no \n inside)
                i += 1
                col += 1
            prev_val = True
            continue
        if ch in _JS_ID:
            while i < n and text[i] in _JS_ID:
                i += 1
                col += 1
            prev_val = True
            continue
        if ch in ")]":
            prev_val = True
            i += 1
            col += 1
            continue
        prev_val = False
        i += 1
        col += 1

    # EOF: flush unterminated literals tolerantly (still literal-ish text).
    for fr in stack:
        if fr[0] == "str":
            _, _, sl, sc = fr
            add_span(sl, sc, line, col)
        elif fr[0] == "tpl":
            _, sl, sc = fr
            add_span(sl, sc, line, col)
    return spans


def _strip_code_fences(lines: list[str]) -> list[bool]:
    """Return mask: True if the line is live code (not inside a markdown fence)."""
    live = []
    in_fence = False
    for line in lines:
        if line.strip().startswith(CODE_FENCE):
            in_fence = not in_fence
            live.append(False)
        else:
            live.append(not in_fence)
    return live


def scan_file(path: str | Path) -> list[Finding]:
    path = Path(path)
    if path.suffix not in SCAN_EXTENSIONS:
        return []
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []
    lines = text.splitlines()
    live = _strip_code_fences(lines) if path.suffix == ".md" else [True] * len(lines)
    is_test = _is_test_file(path)
    literals = _literal_spans(path.suffix, text)
    findings: list[Finding] = []
    for rule in RULES:
        if rule.test_files_only and not is_test:
            continue
        if path.suffix not in rule.extensions:
            continue
        for i, line in enumerate(lines):
            if not live[i]:
                continue
            m = rule.pattern.search(line)
            if not m:
                continue
            if literals and _in_literal(literals, i + 1, m.start(), m.end()):
                continue  # fixture text in a literal, not executed code
            severity, message = rule.severity, rule.message
            if rule.downgrade_if and rule.downgrade_if.search(line):
                severity, message = rule.downgrade_to, message + rule.downgrade_note
            findings.append(Finding(
                rule=rule.id, severity=severity,
                file=str(path), line=i + 1,
                message=message, fix=rule.fix,
            ))
    return sorted(findings, key=lambda f: (f.file, f.line))


def _excluded(path: Path, patterns: tuple[str, ...]) -> bool:
    return any(fnmatch.fnmatchcase(part, pat)
               for part in path.parts for pat in patterns)


def scan_path(target: str | Path,
              exclude: list[str] | tuple[str, ...] | None = None) -> list[Finding]:
    """Scan a file or directory recursively, skipping DEFAULT_EXCLUDES plus extras."""
    patterns = tuple(DEFAULT_EXCLUDES) + tuple(exclude or ())
    target = Path(target)
    files: list[Path] = []
    if target.is_file():
        files = [target]
    elif target.is_dir():
        for ext in SCAN_EXTENSIONS:
            files.extend(target.rglob(f"*{ext}"))
        files = [f for f in files if not _excluded(f, patterns)]
    else:
        raise ValueError(f"{target}: no such file or directory")
    findings: list[Finding] = []
    for f in sorted(files):
        findings.extend(scan_file(f))
    return findings
