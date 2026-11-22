"""Five-issuer score and participation read-only guards, deterministic offline."""
import unittest
from decimal import Decimal
from scripts import unified_us_five_scoring as stage
from scripts import unified_us_five as cohort


def base():
    return {"companies": [{
        "symbol": symbol, "issuer_id": cik,
        "blockers": ["five_company_valuation_comparison_not_run",
                     "reviewed_sharia_source_and_ratio_evidence_missing"],
        "score": None, "eligible_for_trade": False
    } for symbol, cik in cohort.COHORT]}


def valuation():
    return {"companies": [{
        "symbol": symbol, "issuer_id": cik, "identity_status": "exact_match",
        "share_check": {"status": "verified_dated_share_class"},
        "price_check": {"status": "valid"}, "history_check": {"status": "valid"}
    } for symbol, cik in cohort.COHORT]}


def plan():
    return {"selected": 2,
            "excluded": [{"symbol": "GOOGL", "issuer_id": "0001652044",
                          "reason": "unsupported_sector_or_entity_type"}]}


class FiveScoreTests(unittest.TestCase):
    def test_real_5_company_status_and_missing_scores(self):
        r = stage.summarize(base(), valuation(), plan())
        self.assertEqual(r["valuation_sources_verified"], 5)
        self.assertEqual(r["fully_scored"], 0)
        self.assertTrue(all(x["score"] is None for x in r["companies"]))
        self.assertFalse(r["investment_approved"])
        self.assertEqual(r["companies"][-1]["score_plan_exclusion"],
                         "unsupported_sector_or_entity_type")

    def test_partial_scoring_keeps_unselected_unknown(self):
        scoring = {"companies": [
            {"symbol": "AAPL", "issuer_id": "0000320193",
             "status": "scored_research_hypothesis", "total_score": Decimal("67.5"),
             "components": {
                 name: {"weight": cap, "score": value}
                 for name, cap, value in (
                     ("financial_strength", 20, Decimal("7.5")),
                     ("valuation", 20, Decimal("5")),
                     ("growth", 20, Decimal("15")),
                     ("profitability", 15, Decimal("15")),
                     ("cash_flow", 15, Decimal("15")),
                     ("risk", 10, Decimal("10"))) }},
            {"symbol": "MSFT", "issuer_id": "0000789019",
             "status": "review_required", "total_score": None},
        ]}
        r = stage.summarize(base(), valuation(), plan(), scoring=scoring)
        self.assertEqual(r["fully_scored"], 1)
        self.assertEqual(r["companies"][0]["score"], "67.5")
        self.assertEqual(r["companies"][0]["score_components"]["valuation"]["score"], "5")
        self.assertNotIn("five_company_valuation_comparison_not_run",
                         r["companies"][0]["blockers"])
        for c in r["companies"]:
            self.assertEqual(c["participation"], "bilinmiyor")
            self.assertFalse(c["eligible_for_trade"])

    def test_scoring_components_must_reconcile(self):
        scored = {"companies": [{
            "symbol": "AAPL", "issuer_id": "0000320193",
            "status": "scored_research_hypothesis", "total_score": Decimal("67.5"),
            "components": {
                name: {"weight": cap, "score": 0}
                for name, cap in (("financial_strength", 20), ("valuation", 20),
                    ("growth", 20), ("profitability", 15), ("cash_flow", 15),
                    ("risk", 10))}}]}
        with self.assertRaisesRegex(ValueError, "do not reconcile"):
            stage.summarize(base(), valuation(), plan(), scoring=scored)

    def test_reject_valuer_wrong_cik(self):
        v = valuation()
        v["companies"][1]["issuer_id"] = "0000320193"
        with self.assertRaisesRegex(ValueError, "valuation issuer"):
            stage.summarize(base(), v, plan())

    def test_reject_scorer_wrong_issuer(self):
        scored = {"companies": [{"symbol": "MSFT", "issuer_id": "0000320193",
                                 "total_score": 84, "status": "scored_research_hypothesis"}]}
        with self.assertRaisesRegex(ValueError, "scoring issuer"):
            stage.summarize(base(), valuation(), plan(), scoring=scored)

    def test_no_boolean_or_fake_numeric_score(self):
        for value in (True, [], {}):
            scored = {"companies": [{"symbol": "AAPL", "issuer_id": "0000320193",
                                     "total_score": value,
                                     "status": "scored_research_hypothesis"}]}
            with self.assertRaisesRegex(ValueError, "score value malformed"):
                stage.summarize(base(), valuation(), plan(), scoring=scored)

    def test_source_blockers_preserved(self):
        v = valuation()
        v["companies"][2]["share_check"] = {"status": "pending_source_collection"}
        result = stage.summarize(base(), v, plan())
        self.assertEqual(result["valuation_sources_verified"], 4)
        self.assertIn("valuation_source_confirmation_incomplete",
                      result["companies"][2]["blockers"])


if __name__ == "__main__":
    unittest.main()
