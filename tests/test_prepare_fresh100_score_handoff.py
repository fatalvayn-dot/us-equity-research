import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from scripts.prepare_fresh100_score_handoff import prepare


class Fresh100ScoreHandoffTests(unittest.TestCase):
    def test_direct_script_entrypoint_loads_sibling_module(self):
        script = Path(__file__).parents[1] / "scripts/prepare_fresh100_score_handoff.py"
        result = subprocess.run(
            [sys.executable, str(script), "--help"],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("--run-id", result.stdout)

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.candidates = self.root / "candidates.json"
        self.financial = self.root / "financial"
        self.sources = self.root / "sources"
        self.valuation = self.root / "valuation"
        for path in (self.financial / "companyfacts", self.sources,
                     self.valuation / "source-bundle"):
            path.mkdir(parents=True)
        rows = [{"issuer_id": str(i).zfill(10), "symbol": f"S{i}"}
                for i in range(1, 101)]
        self.candidates.write_text(json.dumps(rows))
        (self.financial / "batch.json").write_text(json.dumps({"companies": rows}))
        (self.financial / "metadata.json").write_text(json.dumps({"companies": rows}))
        (self.financial / "companyfacts/0000000001.json").write_text("{}")
        (self.sources / "manifest.json").write_text("{}")
        (self.valuation / "report.json").write_text(json.dumps({"companies": rows}))
        (self.valuation / "source-bundle/manifest.json").write_text("{}")

    def tearDown(self):
        self.temp.cleanup()

    def test_same_run_handoff_is_minimal_and_cohort_locked(self):
        out = self.root / "out"
        receipt = prepare(candidates=self.candidates, financial=self.financial,
                          financial_sources=self.sources, valuation=self.valuation,
                          output=out, run_id=123)
        self.assertEqual(receipt["companies"], 100)
        self.assertTrue(receipt["cohort_match"])
        self.assertFalse(receipt["investment_approved"])
        self.assertTrue((out / "financial/batch.json").is_file())
        self.assertTrue((out / "financial/companyfacts/0000000001.json").is_file())
        self.assertTrue((out / "financial-evidence/live-sources/manifest.json").is_file())
        marker = json.loads((out / "valuation/financial-source-run.json").read_text())
        self.assertEqual(marker, {"run_id": 123})

    def test_mismatched_candidate_is_rejected_before_copy(self):
        rows = json.loads(self.candidates.read_text())
        rows[0]["symbol"] = "WRONG"
        self.candidates.write_text(json.dumps(rows))
        out = self.root / "out"
        with self.assertRaisesRegex(ValueError, "aday dosyası"):
            prepare(candidates=self.candidates, financial=self.financial,
                    financial_sources=self.sources, valuation=self.valuation,
                    output=out, run_id=123)
        self.assertFalse(out.exists())


if __name__ == "__main__":
    unittest.main()
