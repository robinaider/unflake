"""npm wrapper tests: sync determinism, version parity, live shim.

Live-shim test skips without node; sync/version checks are stdlib-only
and always run (they guard the single-source-of-truth rule).
"""

import hashlib
import json
import shutil
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NPM = ROOT / "npm"
SRC = ROOT / "src" / "unflake"
CORE = NPM / "unflake_core" / "unflake"
BIN = NPM / "bin" / "unflake-ci.js"

NODE = shutil.which("node")


def _hashes(d: Path) -> dict[str, str]:
    out = {}
    for f in sorted(d.rglob("*.py")):
        out[f.relative_to(d).as_posix()] = hashlib.sha256(f.read_bytes()).hexdigest()
    return out


def _src_version() -> str:
    import re
    m = re.search(r'__version__\s*=\s*"([^"]+)"',
                  (SRC / "__init__.py").read_text(encoding="utf-8"))
    assert m
    return m.group(1)


class TestNpmSync(unittest.TestCase):
    def test_sync_reproduces_src_exactly(self):
        p = subprocess.run([sys.executable, "sync.py"], capture_output=True,
                           text=True, cwd=NPM)
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertEqual(_hashes(CORE), _hashes(SRC))

    def test_versions_agree(self):
        pkg = json.loads((NPM / "package.json").read_text(encoding="utf-8"))
        self.assertEqual(pkg["version"], _src_version())
        self.assertEqual(pkg["name"], "unflake-ci")

    @unittest.skipUnless(NODE, "node not installed")
    def test_shim_reports_core_version(self):
        subprocess.run([sys.executable, "sync.py"], capture_output=True, cwd=NPM)
        p = subprocess.run([NODE, str(BIN), "--version"],
                           capture_output=True, text=True, cwd=ROOT)
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertIn(_src_version(), p.stdout)

    @unittest.skipUnless(NODE, "node not installed")
    def test_shim_scans_and_forwards_exit_code(self):
        subprocess.run([sys.executable, "sync.py"], capture_output=True, cwd=NPM)
        p = subprocess.run(
            [NODE, str(BIN), "scan", "examples/flaky-js", "--fail-on", "warning"],
            capture_output=True, text=True, cwd=ROOT)
        self.assertEqual(p.returncode, 1, p.stderr)
        self.assertIn("FLK009", p.stdout)


if __name__ == "__main__":
    unittest.main()
