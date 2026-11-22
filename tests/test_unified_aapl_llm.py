import json
import unittest
from unittest.mock import patch
from scripts import unified_aapl_llm as team


def packet():
    return {"schema_version": 1, "symbol": "AAPL",
            "eligible_for_trade": False, "investment_advice": False,
            "summary": {"status": "ok", "current_forecasts": 1},
            "research": {"forecasts": [{"symbol": "AAPL",
                                       "as_of": "2026-11-20",
                                       "direction": "yukari"}]},
            "private_portfolio": "DO_NOT_SHARE"}


class LLMReadinessTests(unittest.TestCase):
    def test_missing_key_and_enabled_flag_is_not_success(self):
        result = team.process(packet(), enabled="false", key_present=False)
        self.assertEqual(result["status"], "blocked_missing_configuration")
        self.assertFalse(result["real_api_tested"])
        self.assertEqual(set(result["missing_configuration"]),
                         {"RADAR_FREE_LLM_ENABLED", "OPENROUTER_API_KEY"})

    def test_enabled_mock_does_not_leak_portfolio(self):
        sent = []
        def fake(payload):
            sent.append(payload)
            return {"choices": [{"message": {"content": "Araştırma tamamlandı; alım yok."}}]}
        result = team.process(packet(), enabled="true",
                              key_present=False, transport=fake)
        self.assertEqual(result["llm_calls"], 5)
        self.assertEqual(result["provider"], "mock_only")
        self.assertFalse(result["real_api_tested"])
        self.assertEqual([p["model"] for p in sent], ["openrouter/free"] * 5)
        self.assertNotIn("DO_NOT_SHARE", json.dumps(sent))

    def test_free_quota_failure_is_explicit_incomplete_not_paid_fallback(self):
        with patch.object(team.llm_team, "orchestrate",
                          side_effect=RuntimeError("LLM API HTTP status: 429")):
            result = team.process(packet(), enabled="true", key_present=True)
        self.assertEqual(result["status"], "blocked_free_provider_rate_limit")
        self.assertEqual(result["reason"], "HTTP_429")
        self.assertIsNone(result["llm_calls"])
        self.assertFalse(result["paid_fallback"])
        self.assertFalse(result["investment_approved"])

    def test_user_portfolio_or_order_prematurely_enabled_is_rejected(self):
        bad = dict(packet(), eligible_for_trade=True)
        with self.assertRaisesRegex(ValueError, "research-only"):
            team.process(bad, enabled="false", key_present=False)


if __name__ == "__main__":
    unittest.main()
