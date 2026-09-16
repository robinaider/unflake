"""End-to-end proof on a REAL test runner (pytest).

Skipped when pytest isn't installed (stdlib-only dev loop stays intact);
CI installs pytest so this runs there. This is the test that earns the
README's claims: real JUnit capture, real flaky verdict, real quarantine.
"""

import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"

PYTEST = shutil.which("pytest")

FLAKY_SUITE = '''\
import pathlib

COUNTER = pathlib.Path(__file__).parent / ".counter"

def _n():
    n = int(COUNTER.read_text()) + 1 if COUNTER.exists() else 1
    COUNTER.write_text(str(n))
    return n

def test_stable():
    assert 1 + 1 == 2

def test_flaky_checkout():
    assert _n() % 2 == 1
'''


def _unflake(*args: str, cwd: Path) -> subprocess.CompletedProcess:
    import os
    env = {"PYTHONPATH": str(SRC), "PATH": os.environ.get("PATH", "/usr/bin:/bin")}
    return subprocess.run([sys.executable, "-m", "unflake", *args],
                          capture_output=True, text=True, cwd=cwd, env=env)


@unittest.skipUnless(PYTEST, "pytest not installed — pip install pytest for e2e proof")
class TestRealPytest(unittest.TestCase):
    def test_run_scores_real_flake(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / "tests").mkdir()
            (root / "tests" / "test_shop.py").write_text(FLAKY_SUITE)
            out = root / "runs"
            p = _unflake("run", "--runs", "4", "--runner", "pytest",
                         "--out-dir", str(out),
                         "--", PYTEST, "tests", "-q", "-p", "no:cacheprovider",
                         cwd=root)
            self.assertEqual(p.returncode, 1, p.stderr)
            self.assertIn("FlakeScore: 50.0/100", p.stdout)
            self.assertIn("FLAKY", p.stdout)
            self.assertIn("test_flaky_checkout", p.stdout)
            self.assertNotIn("test_stable", p.stdout)  # stable stays out of the verdict
            xmls = sorted(out.glob("run*.xml"))
            self.assertEqual(len(xmls), 4)  # real JUnit captured per run
            logs = sorted(out.glob("run*.log"))
            self.assertEqual(len(logs), 4)  # runner output preserved per run

            q = _unflake("quarantine", *[str(x) for x in xmls],
                         "--framework", "pytest", cwd=root)
            self.assertEqual(q.returncode, 0, q.stderr)
            self.assertIn("not test_flaky_checkout", q.stdout)
            self.assertNotIn("not test_stable", q.stdout)  # never quarantine stable
