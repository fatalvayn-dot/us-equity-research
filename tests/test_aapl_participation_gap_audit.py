import unittest
from datetime import datetime, timezone

from scripts.aapl_participation_gap_audit import audit, markdown

PACKET = {"company": {"issuer_key": "SEC:0000320193", "symbol": "AAPL",
                      "instrument_type": "not_verified", "sector": {},
                      "activities": {}, "ratios": {}}, "rulebook": None}


class AaplGapAuditTests(unittest.TestCase):
    def test_missing_rulebook_also_exposes_uncomputed_ratio_work(self):
        result = audit(PACKET, datetime.now(timezone.utc).isoformat())
        self.assertEqual(result["screen_status"], "bilinmiyor")
        ids = {task["id"] for task in result["tasks"]}
        self.assertIn("official_methodology", ids)
        self.assertIn("interest_bearing_debt", ids)
        self.assertIn("nonpermitted_revenue", ids)
        self.assertIn("business_segments", ids)
        self.assertIn("instrument_class", ids)
        self.assertFalse(result["investment_approved"])
        self.assertFalse(result["all_evidence_completed"])
        self.assertNotIn("Alım onayı: EVET", markdown(result))

    def test_cross_issuer_never_runs(self):
        for issuer in ("SEC:0000789019", "SEC:0000320193"):
            packet = {"company": dict(PACKET["company"],
                                      issuer_key=issuer,
                                      symbol="MSFT")}
            with self.assertRaisesRegex(ValueError, "exact AAPL"):
                audit(packet, datetime.now(timezone.utc).isoformat())

    def test_no_future_as_of(self):
        with self.assertRaises(ValueError):
            audit(PACKET, "2026-11-22T00:00:00")

    def test_nothing_about_partial_evidence_claims_approval(self):
        enriched = {"company": dict(PACKET["company"], instrument_type="common_share")}
        result = audit(enriched, datetime.now(timezone.utc).isoformat())
        self.assertEqual(result["screen_status"], "bilinmiyor")
        self.assertFalse(result["eligible_for_trade"])
        self.assertEqual(result["source_verification"], "not_independently_verified")


if __name__ == "__main__":
    unittest.main()
