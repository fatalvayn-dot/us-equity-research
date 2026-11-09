import json
import tempfile
import unittest
from pathlib import Path

from scripts.live_checkpoint import digest
from scripts.verify_production_score_replay import verify_score_provenance
from scripts.write_score_run_provenance import write


class ScoreRunProvenanceTests(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.data = Path(folder.name)
        self.record = self.data / "first-score-work/run-provenance.json"
        self.market = self.file("valuation/source-bundle/manifest.json", {"parts": []})
        self.finance = self.file("financial-evidence/live-sources/manifest.json", {"parts": [1]})
        self.file("valuation/financial-source-run.json", {"run_id": 3})
        self.file("valuation/report.json", {})
        self.file("financial/batch.json", {})
        self.file("first-score-work/current.json", {})
        self.file("first-score-work/prior.json", {})
        self.output = self.file("first-score-work/output/manifest.json", {
            "source_bundle_manifest_sha256": digest(self.market),
            "additional_financial_source_bundles": [{"manifest_sha256": digest(self.finance)}],
        })

    def file(self, path, data):
        target = self.data / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(data))
        return target

    def test_record_binds_runs_and_exact_files(self):
        record = write(self.data, score_run=1, valuation_run=2, financial_run=3,
                       commit="a" * 40)
        self.assertEqual(json.loads(self.record.read_text()), record)
        self.assertEqual(record["score_run_id"], 1)
        self.assertEqual(record["valuation_run_id"], 2)
        self.assertEqual(record["financial_run_id"], 3)
        self.assertEqual(record["sha256"]["score_manifest"], digest(self.output))
        self.assertEqual(record["sha256"]["valuation_source_manifest"], digest(self.market))

    def test_financial_run_must_match_valuation_marker(self):
        with self.assertRaisesRegex(ValueError, "run ID değerleri uyuşmuyor"):
            write(self.data, score_run=1, valuation_run=2, financial_run=4, commit="a" * 40)
        self.assertFalse(self.record.exists())

    def test_changed_source_manifest_prevents_receipt(self):
        self.finance.write_text("{}")
        with self.assertRaisesRegex(ValueError, "paket özetleri uyuşmuyor"):
            write(self.data, score_run=1, valuation_run=2, financial_run=3, commit="a" * 40)
        self.assertFalse(self.record.exists())


    def verify(self, **expected):
        return verify_score_provenance(financial=self.data / "financial",
                                       valuation=self.data / "valuation",
                                       financial_sources=[self.finance.parent],
                                       score=self.record.parent, financial_run=3,
                                       **expected)

    def test_replay_rebuilds_and_verifies_receipt(self):
        expected = dict(score_run=1, valuation_run=2, commit="a" * 40)
        receipt = write(self.data, financial_run=3, **expected)
        self.assertEqual(self.verify(**expected), receipt)

    def test_replay_rejects_wrong_run_commit_or_input_bytes(self):
        expected = dict(score_run=1, valuation_run=2, commit="a" * 40)
        write(self.data, financial_run=3, **expected)
        for field, bad in (("score_run", 10), ("valuation_run", 20), ("commit", "b" * 40)):
            with self.subTest(field=field), self.assertRaisesRegex(ValueError, "provenance mismatch"):
                self.verify(**(expected | {field: bad}))
        self.file("valuation/report.json", {"changed": True})
        with self.assertRaisesRegex(ValueError, "provenance mismatch"):
            self.verify(**expected)

    def test_replay_distinguishes_legacy_and_missing_required_receipt(self):
        self.assertIsNone(self.verify())
        with self.assertRaisesRegex(ValueError, "provenance missing"):
            self.verify(score_run=1, valuation_run=2, commit="a" * 40)
        write(self.data, financial_run=3, score_run=1, valuation_run=2, commit="a" * 40)
        with self.assertRaisesRegex(ValueError, "exact score run"):
            self.verify()
