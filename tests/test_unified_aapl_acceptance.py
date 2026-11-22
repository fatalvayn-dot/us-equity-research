import json
import unittest

from scripts.llm_team import sanitize
from scripts.unified_aapl_acceptance import assess, markdown


def research():
    return {
        "schema_version": 1, "symbol": "AAPL", "as_of": "2026-11-22",
        "source": "yfinance_daily", "eligible_for_trade": False,
        "investment_advice": False,
        "gates": {"market_price": "source_observed",
                  "news_event_model": "rss_headlines_only_no_causal_model"},
        "financial_research": {"status": "facts_observed_review_required",
                               "all_financial_references_archived": True,
                               "accepted_fact_count": 11},
        "valuation_research": {"status": "source_gates_observed_not_valued",
                               "blockers": []},
        "scoring_research": {"status": "scored_research_hypothesis",
                             "score": "67.5", "model_version": "test-score-v1"},
        "historical_prediction_check": {
            "performance_gate": "not_better_than_naive_up",
            "direction_hit_rate": 0.5315, "benchmark_up_hit_rate": 0.5874,
            "eligible_samples": 143, "predictive_approved": False,
            "adaptive_optimization_verified": False},
        "research": {"forecasts": [], "news": {"status": "ok",
                    "items": [{"title": "private raw title"}], "risk_count": 2}},
        "summary": {"status": "live_attempt", "current_forecasts": 1},
        "participation_research": {"status": "bilinmiyor",
                                   "no_live_source_verification": True},
        "private_portfolio": "DO_NOT_SEND_PORTFOLIO",
    }


def llm():
    return {"status": "completed", "real_api_tested": True,
            "provider": "openrouter/free", "paid_fallback": False,
            "llm_calls": 5,
            "agents": {role: "Yatırım önerisi yok; kanıt incelemesi."
                       for role in ("manager", "researcher", "developer",
                                    "auditor", "manager_report")}}


class AcceptanceTests(unittest.TestCase):
    def test_completed_data_and_llm_do_not_overrule_participation(self):
        result = assess(research(), llm())
        self.assertEqual(result["status"], "research_chain_operational")
        self.assertEqual(result["score"], "67.5")
        self.assertFalse(result["all_user_requested_stages_accepted"])
        self.assertEqual(result["missing_acceptance"],
                         ["independent_participation",
                          "predictive_edge_validated", "news_effect_validated"])
        self.assertFalse(result["eligible_for_trade"])
        self.assertIn("EKSİK: independent_participation", markdown(result))

    def test_missing_llm_is_blocker_not_false_success(self):
        result = assess(research())
        self.assertEqual(result["status"], "research_chain_incomplete")
        self.assertIsNone(result["advisor_verdict"])
        self.assertIn("llm_five_real_calls", result["missing_acceptance"])

    def test_mock_response_and_paid_provider_dont_pass(self):
        bad = llm()
        bad["real_api_tested"] = False
        self.assertFalse(assess(research(), bad)["evidence_gates"]["llm_five_real_calls"])
        bad["real_api_tested"] = True
        bad["provider"] = "paid/provider"
        self.assertFalse(assess(research(), bad)["evidence_gates"]["llm_five_real_calls"])

    def test_issuer_and_trade_prohibitions(self):
        for update in ({"symbol": "MSFT"}, {"eligible_for_trade": True},
                       {"investment_advice": True}):
            bad = dict(research(), **update)
            with self.assertRaises(ValueError):
                assess(bad, llm())

    def test_score_and_backtest_are_shared_without_private_fields(self):
        clean = sanitize(research())
        self.assertEqual(clean["scoring_research"]["research_score_0_100"], 67.5)
        self.assertEqual(clean["prediction_validation"]["eligible_samples"], 143)
        self.assertEqual(clean["prediction_validation"]["predictive_approved"], False)
        self.assertNotIn("DO_NOT_SEND_PORTFOLIO", json.dumps(clean))
        self.assertNotIn("private raw title", json.dumps(clean))

    def test_malformed_score_and_rate_not_shared(self):
        bad = research()
        bad["scoring_research"]["score"] = "PRIVATE_FIELD_999"
        bad["historical_prediction_check"]["direction_hit_rate"] = 1.5
        clean = sanitize(bad)
        self.assertIsNone(clean["scoring_research"]["research_score_0_100"])
        self.assertIsNone(clean["prediction_validation"]["observed_hit_rate"])
        self.assertNotIn("PRIVATE_FIELD_999", json.dumps(clean))


if __name__ == "__main__":
    unittest.main()
