import copy
import unittest
from scripts.adaptive_investment_assistant import evidence_packet, analyst_prompt

BASE = {"schema_version": 1, "created_at": "2026-11-12T18:00:00+00:00",
        "portfolio_positions_included": False, "markets": {
            "ABD": [{"symbol": "MSFT", "status": "observed", "price": 500.0,
                     "change_1d_pct": -4.2, "market_at": "2026-11-12T17:00:00+00:00",
                     "currency": "USD", "source_url": "https://example.org/msft"}],
            "BIST": [{"symbol": "ASELS.IS", "status": "source_unavailable", "price": None,
                      "change_1d_pct": None, "market_at": None, "currency": "TRY"}],
            "AVRUPA": [{"symbol": "DTE.DE", "status": "observed", "price": 25,
                        "change_1d_pct": 0.3, "market_at": "2026-11-12T12:00:00+00:00",
                        "currency": "EUR"}]}}


class ResearchPacketTests(unittest.TestCase):
    def test_separate_markets_and_no_fabricated_scores_or_compliance(self):
        packet = evidence_packet(BASE)
        self.assertEqual(len(packet["work_queue"]), 2)
        self.assertEqual(packet["work_queue"][0]["symbol"], "ASELS.IS")
        self.assertEqual(packet["markets"]["ABD"][0]["participation_status"], "unknown")
        self.assertIsNone(packet["markets"]["ABD"][0]["score"])
        self.assertIsNone(packet["markets"]["ABD"][0]["investment_action"])
        self.assertFalse(packet["investment_decisions_generated"])
        self.assertFalse(packet["personal_portfolio_included"])
        self.assertIn("işlem", analyst_prompt(packet).lower())

    def test_no_price_failure_becomes_market_signal(self):
        packet = evidence_packet(BASE)
        row = packet["markets"]["BIST"][0]
        self.assertIsNone(row["price"])
        self.assertEqual(row["attention_reasons"], ["missing_price_source"])

    def test_reject_future_stale_and_invalid_quote(self):
        for field, value in (("price", -10), ("market_at", "2026-11-13T18:00:00+00:00"),
                             ("change_1d_pct", float("nan"))):
            bad = copy.deepcopy(BASE)
            bad["markets"]["ABD"][0][field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                evidence_packet(bad)
        stale = copy.deepcopy(BASE)
        stale["markets"]["ABD"][0]["market_at"] = "2026-11-01T17:00:00+00:00"
        self.assertIn("stale_price", evidence_packet(stale)["markets"]["ABD"][0]["attention_reasons"])

    def test_public_artifact_must_not_claim_personal_positions(self):
        bad = copy.deepcopy(BASE)
        bad["portfolio_positions_included"] = True
        with self.assertRaises(ValueError):
            evidence_packet(bad)

    def test_no_overlapping_ticker(self):
        bad = copy.deepcopy(BASE)
        bad["markets"]["BIST"][0]["symbol"] = "MSFT"
        with self.assertRaises(ValueError):
            evidence_packet(bad)


if __name__ == "__main__":
    unittest.main()
