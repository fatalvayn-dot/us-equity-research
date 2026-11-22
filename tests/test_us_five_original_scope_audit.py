"""Offline acceptance for original SEC 10-K accounting disclosure audit."""
import copy
import json
import tempfile
import unittest
from pathlib import Path

from scripts.us_five_original_scope_audit import original_review, markdown

ROOT = Path(__file__).resolve().parents[1]


class OriginalScopeAuditTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.result = original_review(root=ROOT)
        cls.by = {row["symbol"]: row for row in cls.result["issuer_reviews"]}

    def test_all_three_original_hashes_and_sec_ciks(self):
        self.assertEqual(list(self.by), ["NVDA", "AMZN", "GOOGL"])
        self.assertEqual(self.result["network_requests"], 0)
        self.assertEqual(self.result["scores_generated"], 0)
        self.assertTrue(all(row["source_hash_reverified"] for row in self.by.values()))
        self.assertEqual(len({row["original_source_sha256"] for row in self.by.values()}), 3)
        self.assertFalse(self.result["investment_approved"])

    def test_alternate_concepts_are_not_silent_aliases(self):
        expected = {
            "NVDA": {"us-gaap:Revenues", "us-gaap:PaymentsToAcquireProductiveAssets"},
            "AMZN": {"us-gaap:PaymentsToAcquireProductiveAssets"},
            "GOOGL": {"us-gaap:Revenues"},
        }
        for sym, concepts in expected.items():
            verified = {c["concept"] for c in self.by[sym]["disclosed_concepts"]
                        if c["status"] == "exact_original_value"}
            self.assertTrue(concepts <= verified)
            self.assertFalse(self.by[sym]["automatic_substitution"])
            self.assertFalse(self.by[sym]["score_eligible"])

    def test_amzn_liabilities_candidate_never_passes_literal(self):
        proof = self.by["AMZN"]["liabilities_equation"]
        self.assertIn(proof["status"], ("verified_derived_not_literal", "not_verified"))
        self.assertFalse(proof["scope_approved"])
        self.assertIn("AMZN", markdown(self.result))

    def test_googl_class_a_b_c_require_separate_model(self):
        review = self.by["GOOGL"]["security_class"]
        self.assertEqual(tuple(review["classes"]), ("A", "B", "C"))
        self.assertFalse(review["shares_approved"])
        self.assertIn("multi", review["status"])

    def test_missing_original_archive_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(OSError):
                original_review(root=tmp)

    def test_source_hash_mismatch_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp)
            src = json.loads(
                (ROOT / "docs/evidence/annual-document-resume.json").read_text(encoding="utf-8"))
            subset = [c for c in src["companies"] if c.get("symbol") in ("NVDA", "AMZN", "GOOGL")]
            for row in subset:
                row["source_evidence"]["fixture"] = "tests/fixtures/fake.html.gz"
            (dest / "docs/evidence").mkdir(parents=True)
            (dest / "tests/fixtures").mkdir(parents=True)
            (dest / "docs/evidence/annual-document-resume.json").write_text(
                json.dumps({"companies": subset}), encoding="utf-8")
            import gzip
            (dest / "tests/fixtures/fake.html.gz").write_bytes(gzip.compress(b"<html>bad source</html>"))
            with self.assertRaisesRegex(ValueError, "original SEC SHA mismatch"):
                original_review(root=dest)


if __name__ == "__main__":
    unittest.main()
