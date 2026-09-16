"""Study harness tests: schema + driver smoke. No network, no cloning."""

import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STUDY = ROOT / "benchmarks" / "study_v2"

REQUIRED = {"name", "repo", "test_files", "targets"}


class TestStudyHarness(unittest.TestCase):
    def test_subjects_schema(self):
        subjects = json.loads((STUDY / "subjects.json").read_text(encoding="utf-8"))
        self.assertGreaterEqual(len(subjects), 1)
        for s in subjects:
            self.assertTrue(REQUIRED <= set(s), f"subject missing keys: {s}")
            self.assertTrue(s["repo"].startswith("https://"))

    def test_driver_help(self):
        p = subprocess.run([sys.executable, "benchmarks/study_v2/run_study.py", "--help"],
                           capture_output=True, text=True, cwd=ROOT)
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertIn("--subjects", p.stdout)

    def test_workflow_exists_and_scheduled(self):
        wf = (ROOT / ".github" / "workflows" / "study.yml").read_text(encoding="utf-8")
        self.assertIn("cron", wf)
        self.assertIn("run_study.py", wf)


if __name__ == "__main__":
    unittest.main()
