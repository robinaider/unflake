"""`unflake init`: scaffold the two cheapest flake preventions.

1. Seeded RNG + logged seed (unseeded randomness is unreproducible by definition).
2. A frozen-time pointer (wall clocks are the #2 classic).

`--write` creates files idempotently (marker-guarded, never duplicates).
Without `--write`, snippets print to stdout with wiring instructions.
"""

from __future__ import annotations

from pathlib import Path

MARKER = "# unflake:seed-logging"

PYTEST_SNIPPET = '''%(marker)s (added by `unflake init --framework pytest --write`)
# Deterministic RNG per test + logged seed: rerun any failure exactly with
#   UNFLAKE_SEED=<seed> pytest ...
import os
import random

import pytest


@pytest.fixture(autouse=True)
def _unflake_seed(request):
    seed = os.environ.get("UNFLAKE_SEED", "0")
    random.seed(f"{seed}-{request.node.nodeid}")
    print(f"\\n[unflake] seed={seed} test={request.node.nodeid}")
    yield
'''

JEST_SNIPPET = '''// unflake:seed-logging (added by `unflake init --framework jest`)
// Deterministic RNG per test file. Wire into jest config:
//   { setupFiles: ["<rootDir>/unflake.setup.cjs"] }
const seed = process.env.UNFLAKE_SEED || "0";
let s = [...seed].reduce((a, c) => (a * 33 + c.charCodeAt(0)) >>> 0, 7) || 7;
const file = expect.getState().testPath || "unknown";
console.log(`[unflake] seed=${seed} file=${file}`);
Math.random = () => (s = (s * 1103515245 + 12345) & 0x7fffffff) / 0x7fffffff;
'''

VITEST_SNIPPET = '''// unflake:seed-logging (added by `unflake init --framework vitest`)
// Wire into vitest config: export default { test: { setupFiles: ["./unflake.setup.js"] } }
const seed = process.env.UNFLAKE_SEED || "0";
console.log(`[unflake] seed=${seed}`);
'''

PLAYWRIGHT_SNIPPET = '''// unflake:seed-logging (added by `unflake init --framework playwright`)
// Playwright has built-in retries — prefer them over fixed waits:
//   { retries: 2, use: { trace: "retain-on-failure" } }
// And NEVER page.waitForTimeout(): use web-first assertions:
//   await expect(page.getByRole("button")).toBeVisible();
'''

SNIPPETS = {
    "pytest": ("tests/conftest.py", PYTEST_SNIPPET),
    "jest": ("unflake.setup.cjs", JEST_SNIPPET),
    "vitest": ("unflake.setup.js", VITEST_SNIPPET),
    "playwright": ("unflake.playwright-notes.js", PLAYWRIGHT_SNIPPET),
}

FRAMEWORKS = tuple(SNIPPETS)


def snippet(framework: str) -> tuple[str, str]:
    """Return (relative_path, content) for a framework."""
    if framework not in SNIPPETS:
        raise ValueError(f"unknown framework {framework!r} (try: {', '.join(FRAMEWORKS)})")
    rel, template = SNIPPETS[framework]
    return rel, template % {"marker": MARKER}


def init_framework(framework: str, root: str | Path = ".", write: bool = False) -> str:
    """Print or write the scaffold. Returns a human summary."""
    rel, content = snippet(framework)
    if not write:
        return f"# {rel} — create this file with the content below:\n\n{content}"
    dest = Path(root) / rel
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists():
        existing = dest.read_text(encoding="utf-8", errors="replace")
        if MARKER in existing or "unflake:seed-logging" in existing:
            return f"{dest}: already scaffolded — left untouched."
        with dest.open("a", encoding="utf-8") as fh:
            fh.write("\n" + content)
        return f"{dest}: snippet appended (existing file preserved)."
    dest.write_text(content, encoding="utf-8")
    return f"{dest}: created. Rerun any failure exactly with UNFLAKE_SEED=<seed>."
