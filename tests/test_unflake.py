"""Unit tests (stdlib unittest — no install needed to run: python3 -m unittest)."""

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

from unflake.ingest import load_runs  # noqa: E402
from unflake.patterns import scan_file  # noqa: E402
from unflake.quarantine import emit  # noqa: E402
from unflake.score import score_runs  # noqa: E402

RUN1 = """<?xml version="1.0" encoding="utf-8"?>
<testsuite name="pytest" tests="3">
  <testcase classname="test_cart" name="test_total" />
  <testcase classname="test_cart" name="test_discount" />
  <testcase classname="test_cart" name="test_checkout"><failure message="boom"/></testcase>
</testsuite>"""

RUN2 = """<?xml version="1.0" encoding="utf-8"?>
<testsuite name="pytest" tests="3">
  <testcase classname="test_cart" name="test_total" />
  <testcase classname="test_cart" name="test_discount"><failure message="boom"/></testcase>
  <testcase classname="test_cart" name="test_checkout" />
</testsuite>"""


class TestIngestScore(unittest.TestCase):
    def test_mixed_outcomes_are_flaky(self):
        with tempfile.TemporaryDirectory() as d:
            r1, r2 = Path(d) / "r1.xml", Path(d) / "r2.xml"
            r1.write_text(RUN1)
            r2.write_text(RUN2)
            suite = score_runs(load_runs([r1, r2]))
        by_id = {t.id: t for t in suite.tests}
        self.assertEqual(by_id["test_cart::test_total"].verdict, "stable-pass")
        self.assertEqual(by_id["test_cart::test_discount"].verdict, "flaky")
        self.assertEqual(by_id["test_cart::test_checkout"].verdict, "flaky")
        self.assertEqual(suite.flaky_count, 2)
        self.assertAlmostEqual(suite.flake_score, 100 * 1 / 3, places=1)

    def test_generic_json_status_words(self):
        from unflake.ingest import parse_generic_json
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "r.json"
            p.write_text(json.dumps({"tests": [
                {"id": "a", "status": "passed"},
                {"id": "b", "status": "failed"},
                {"id": "c", "status": "failure"},
                {"id": "d", "status": "skipped"},
            ]}))
            got = parse_generic_json(p)
        self.assertEqual(got, {"a": "passed", "b": "failed",
                               "c": "failed", "d": "skipped"})


class TestPatterns(unittest.TestCase):
    def test_detects_sleep_random_and_network(self):
        with tempfile.TemporaryDirectory() as d:
            f = Path(d) / "test_shop.py"
            f.write_text(
                "import time, random, requests\n"
                "def test_price():\n"
                "    time.sleep(2)\n"
                "    assert random.randint(0, 10) < 9\n"
                "    requests.get('http://localhost:9999/x')\n"
            )
            rules = {x.rule for x in scan_file(f)}
        self.assertTrue({"FLK001", "FLK003", "FLK004"} <= rules)

    def test_code_fence_in_markdown_is_not_flagged(self):
        with tempfile.TemporaryDirectory() as d:
            f = Path(d) / "test_docs.md"
            f.write_text("```python\ntime.sleep(1)\n```\n")
            self.assertEqual(scan_file(f), [])

    def test_non_test_source_files_are_skipped(self):
        with tempfile.TemporaryDirectory() as d:
            f = Path(d) / "server.py"
            f.write_text("import time\ntime.sleep(1)\n")
            self.assertEqual(scan_file(f), [])


class TestQuarantine(unittest.TestCase):
    def test_pytest_emitter_lists_every_id(self):
        out = emit("pytest", ["test_cart::test_discount", "test_cart::test_checkout"])
        self.assertIn("test_discount", out)
        self.assertIn("test_checkout", out)
        self.assertIn("-k", out)

    def test_unknown_framework_rejected(self):
        with self.assertRaises(ValueError):
            emit("cobol", ["a::b"])


class TestCLI(unittest.TestCase):
    def _run(self, *args: str) -> subprocess.CompletedProcess:
        return subprocess.run(
            [sys.executable, "-m", "unflake", *args],
            capture_output=True, text=True, cwd=ROOT,
            env={"PYTHONPATH": str(SRC), "PATH": "/usr/bin:/bin"},
        )

    def test_scan_fixture_finds_flakes_and_fails(self):
        p = self._run("scan", "examples/flaky-pytest")
        self.assertEqual(p.returncode, 1, p.stderr)
        self.assertIn("FLK001", p.stdout)

    def test_scan_clean_package_passes(self):
        p = self._run("scan", "src/unflake", "--fail-on", "error")
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)

    def test_scan_accepts_multiple_targets(self):
        p = self._run("scan", "src/unflake", "fixtures", "--fail-on", "error")
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        p2 = self._run("scan", "examples/flaky-pytest", "examples/flaky-js")
        self.assertEqual(p2.returncode, 1, p2.stderr)
        self.assertIn("FLK001", p2.stdout)
        self.assertIn("FLK009", p2.stdout)

    def test_analyze_scores_fixtures(self):
        p = self._run("analyze", "fixtures/runs/run1.xml", "fixtures/runs/run2.xml")
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertIn("FlakeScore", p.stdout)
        self.assertIn("FLAKY", p.stdout)

    def test_quarantine_emits_pytest(self):
        p = self._run("quarantine", "fixtures/runs/run1.xml",
                      "fixtures/runs/run2.xml", "--framework", "pytest")
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertIn("pytest -k", p.stdout)


class TestRegressionAndNew(unittest.TestCase):
    def _score(self, runs):
        with tempfile.TemporaryDirectory() as d:
            paths = []
            for i, statuses in enumerate(runs):
                cases = "".join(
                    f'<testcase classname="t" name="{name}">' +
                    ("" if st == "passed" else '<failure message="x"/>') +
                    "</testcase>"
                    for name, st in statuses.items()
                )
                p = Path(d) / f"r{i}.xml"
                p.write_text(f'<?xml version="1.0"?><testsuite name="s">{cases}</testsuite>')
                paths.append(p)
            return score_runs(load_runs(paths))

    def test_clean_break_is_regression(self):
        suite = self._score([
            {"a": "passed", "b": "passed"},
            {"a": "passed", "b": "passed"},
            {"a": "failed", "b": "passed"},
            {"a": "failed", "b": "passed"},
        ])
        by_id = {t.id: t for t in suite.tests}
        self.assertEqual(by_id["t::a"].verdict, "regression")
        self.assertEqual(by_id["t::a"].change_point, 3)
        self.assertEqual(by_id["t::b"].verdict, "stable-pass")
        self.assertEqual(suite.regression_count, 1)

    def test_two_runs_cannot_call_regression(self):
        suite = self._score([{"a": "passed"}, {"a": "failed"}])
        by_id = {t.id: t for t in suite.tests}
        self.assertEqual(by_id["t::a"].verdict, "flaky")

    def test_pass_fail_pass_is_flaky_not_regression(self):
        suite = self._score([
            {"a": "passed"}, {"a": "failed"}, {"a": "passed"},
        ])
        self.assertEqual({t.id: t for t in suite.tests}["t::a"].verdict, "flaky")

    def test_latest_only_test_is_new(self):
        suite = self._score([
            {"a": "passed"}, {"a": "passed", "b": "passed"},
        ])
        self.assertEqual({t.id: t for t in suite.tests}["t::b"].verdict, "new")


class TestWaitRules(unittest.TestCase):
    def test_cypress_and_playwright_waits_flagged(self):
        with tempfile.TemporaryDirectory() as d:
            f = Path(d) / "login.spec.ts"
            f.write_text("it('x', () => {\n  cy.wait(3000);\n  await page.waitForTimeout(500);\n});\n")
            rules = {x.rule for x in scan_file(f)}
        self.assertTrue({"FLK009", "FLK010"} <= rules)

    def test_wait_rules_do_not_fire_in_python(self):
        with tempfile.TemporaryDirectory() as d:
            f = Path(d) / "test_x.py"
            f.write_text("def test_x():\n    cy.wait(3000)\n")
            rules = {x.rule for x in scan_file(f)}
        self.assertNotIn("FLK009", rules)


class TestRunAndInit(unittest.TestCase):
    def _run(self, *args: str, cwd=None) -> subprocess.CompletedProcess:
        return subprocess.run(
            [sys.executable, "-m", "unflake", *args],
            capture_output=True, text=True, cwd=cwd or ROOT,
            env={"PYTHONPATH": str(SRC), "PATH": "/usr/bin:/bin"},
        )

    def test_run_collects_and_scores_stable(self):
        with tempfile.TemporaryDirectory() as d:
            p = self._run("run", "--runs", "2", "--out-dir", f"{d}/runs",
                          "--", sys.executable, "-c", "import sys; sys.exit(0)")
            self.assertEqual(p.returncode, 0, p.stderr)
            self.assertIn("FlakeScore: 100", p.stdout)

    def test_run_detects_flapping_command(self):
        with tempfile.TemporaryDirectory() as d:
            counter = Path(d) / "n.txt"
            counter.write_text("0")
            code = ("import pathlib, sys; p = pathlib.Path(sys.argv[1]); "
                    "n = int(p.read_text()) + 1; p.write_text(str(n)); "
                    "sys.exit(0 if n % 2 else 1)")
            p = self._run("run", "--runs", "3", "--out-dir", f"{d}/runs",
                          "--", sys.executable, "-c", code, str(counter))
            self.assertEqual(p.returncode, 1, p.stderr)  # fail-on flaky (default)
            self.assertIn("FLAKY", p.stdout)

    def test_init_writes_pytest_conftest_idempotently(self):
        from unflake.scaffold import MARKER, init_framework
        with tempfile.TemporaryDirectory() as d:
            first = init_framework("pytest", root=d, write=True)
            second = init_framework("pytest", root=d, write=True)
            content = (Path(d) / "tests" / "conftest.py").read_text()
            self.assertIn("conftest.py: created", first)
            self.assertIn("left untouched", second)
            self.assertEqual(content.count(MARKER), 1)
            self.assertIn("UNFLAKE_SEED", content)

    def test_init_prints_without_write(self):
        p = self._run("init", "--framework", "jest")
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertIn("UNFLAKE_SEED", p.stdout)


class TestPrecision(unittest.TestCase):
    def _scan_text(self, name: str, content: str):
        with tempfile.TemporaryDirectory() as d:
            f = Path(d) / name
            f.write_text(content)
            return scan_file(f)

    def test_flk004_localhost_downgraded(self):
        ext = self._scan_text("test_net.py",
                              "import requests\ndef test_a():\n    requests.get('https://api.example.com/x')\n")
        loc = self._scan_text("test_net.py",
                              "import requests\ndef test_a():\n    requests.get('http://localhost:9999/x')\n")
        self.assertEqual([f.severity for f in ext if f.rule == "FLK004"], ["warning"])
        sev = [f.severity for f in loc if f.rule == "FLK004"]
        self.assertEqual(sev, ["info"])
        self.assertIn("localhost", loc[0].message)

    def test_string_literals_not_executed(self):
        got = self._scan_text(
            "test_gen.py",
            'def test_gen():\n    code = "time.sleep(2); random.seed(1)"\n    write(code)\n')
        self.assertEqual([f.rule for f in got], [])
        real = self._scan_text(
            "test_gen.py",
            'import time\ndef test_gen():\n    time.sleep(2)\n')
        self.assertIn("FLK001", {f.rule for f in real})

    def test_unparseable_python_never_hides(self):
        got = self._scan_text("test_broken.py", "def broken(:\n    time.sleep(1)\n")
        self.assertIn("FLK001", {f.rule for f in got})

    def test_default_excludes_and_custom_flag(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / "node_modules").mkdir()
            (root / "node_modules" / "x.spec.js").write_text("it('x',()=>{cy.wait(9)})\n")
            (root / "tests").mkdir()
            (root / "tests" / "test_a.py").write_text("import time\ndef test_a():\n    time.sleep(1)\n")
            from unflake.patterns import scan_path
            all_rules = {f.rule for f in scan_path(root)}
            self.assertNotIn("FLK009", all_rules)  # node_modules skipped by default
            self.assertIn("FLK001", all_rules)
            custom = {f.rule for f in scan_path(root, exclude=["tests"])}
            self.assertNotIn("FLK001", custom)

    def test_sarif_carries_rule_metadata(self):
        import json
        from unflake.patterns import scan_path
        from unflake.report import format_sarif
        with tempfile.TemporaryDirectory() as d:
            f = Path(d) / "test_a.py"
            f.write_text("import time\ndef test_a():\n    time.sleep(1)\n")
            sarif = json.loads(format_sarif(scan_path(f)))
        rules = {r["id"] for r in sarif["runs"][0]["tool"]["driver"]["rules"]}
        self.assertIn("unflake/FLK001", rules)
        self.assertIn("unflake/FLAKY", rules)
        self.assertIn("unflake/REGRESSION", rules)

    def test_quarantine_warns_on_risky_names(self):
        out = emit("pytest", ["t::test_ok", "t::test with spaces"])
        self.assertIn("RISKY", out)
        self.assertIn("--deselect", out)


class TestVitestCompat(unittest.TestCase):
    def test_runner_args(self):
        from unflake.runner import runner_args, runner_env
        self.assertEqual(runner_args("vitest", "/tmp/x/run1.xml"),
                         ["--reporter=junit", "--outputFile=/tmp/x/run1.xml"])
        self.assertEqual(runner_args("pytest", "/tmp/x/run1.xml"),
                         ["--junitxml=/tmp/x/run1.xml"])
        self.assertEqual(runner_args("playwright", "/tmp/x/run1.xml"),
                         ["--reporter=junit"])
        self.assertEqual(runner_env("playwright", "/tmp/x/run1.xml"),
                         {"PLAYWRIGHT_JUNIT_OUTPUT_NAME": "/tmp/x/run1.xml"})
        self.assertEqual(runner_args("jest", "/tmp/x/run1.xml"),
                         ["--reporters", "jest-junit"])
        self.assertEqual(runner_env("jest", "/tmp/x/run1.xml"),
                         {"JEST_JUNIT_OUTPUT_FILE": "/tmp/x/run1.xml"})
        self.assertEqual(runner_env("pytest", "/tmp/x/run1.xml"), {})
        self.assertIsNone(runner_args(None, "/tmp/x/run1.xml"))
        with self.assertRaises(ValueError):
            from unflake.runner import collect
            collect(["true"], runs=2, out_dir="/tmp/nonexistent-should-fail",
                    runner="cobol")

    def test_real_vitest_junit_scores_flaky(self):
        # Captured from real `vitest run --reporter=junit` (see BENCH.md).
        root = Path(__file__).resolve().parents[1] / "fixtures" / "runs"
        suite = score_runs(load_runs([root / "vitest-pass.xml",
                                      root / "vitest-fail.xml"]))
        by_id = {t.id: t for t in suite.tests}
        flaky = [t for t in suite.tests if t.verdict == "flaky"]
        self.assertEqual(len(flaky), 1)
        self.assertIn("flaky counter", flaky[0].id)
        self.assertEqual(by_id["tests/flaky.test.js::stable"].verdict, "stable-pass")


class TestJsRunnerFixtures(unittest.TestCase):
    """Frozen outputs from real runs (vitest 4.x, playwright, jest 30.x).

    If a runner changes its JUnit shape, these fail loudly instead of
    rotting — that failure is the signal to re-verify the preset.
    """

    def _score(self, *names):
        root = Path(__file__).resolve().parents[1] / "fixtures" / "runs"
        return score_runs(load_runs([root / n for n in names]))

    def test_playwright_pair(self):
        suite = self._score("playwright-pass.xml", "playwright-fail.xml")
        flaky = [t for t in suite.tests if t.verdict == "flaky"]
        self.assertEqual(len(flaky), 1)
        self.assertIn("flaky counter", flaky[0].id)

    def test_jest_pair(self):
        suite = self._score("jest-pass.xml", "jest-fail.xml")
        flaky = [t for t in suite.tests if t.verdict == "flaky"]
        self.assertEqual(len(flaky), 1)
        self.assertIn("flaky counter", flaky[0].id)


if __name__ == "__main__":
    unittest.main()
