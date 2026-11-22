"""Deterministic five-issuer SEC/price/participation pipeline acceptance tests."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts import unified_us_five as cohort


def market(symbol, fixture=None):
    return {"symbol": symbol, "eligible_for_trade": False, "investment_advice": False,
            "gates": {"market_price": "source_observed"},
            "as_of": "2026-11-20", "source": "yfinance_daily",
            "forecast": {"direction": "yukari"}}


def sec(payload, **kwargs):
    return {"companies": [
        {"symbol": row["symbol"], "issuer_id": row["issuer_id"],
         "accepted_fact_count": 11}
        for row in payload["companies"]],
        "pipeline": {"all_financial_references_archived": True}}


class FiveIssuerTests(unittest.TestCase):
    def test_real_cik_one_sec_batch_and_one_market_orchestration(self):
        from unittest.mock import Mock
        sec_runner = Mock(side_effect=sec)
        market_runner = Mock(side_effect=market)
        result = cohort.research_five(
            user_agent="Official research contact analyst@example.org",
            state_dir="never_written_by_mock", market_runner=market_runner,
            sec_collector=sec_runner)
        self.assertEqual(result["requested"], 5)
        self.assertEqual(result["sec_archived"], 5)
        self.assertEqual(result["market_verified"], 5)
        self.assertEqual(result["fully_scored"], 0)
        self.assertEqual(sec_runner.call_count, 1)
        self.assertEqual(market_runner.call_count, 5)
        self.assertEqual(
            [(x["symbol"], x["issuer_id"]) for x in sec_runner.call_args.args[0]["companies"]],
            list(cohort.COHORT))
        self.assertFalse(result["investment_approved"])
        for item in result["companies"]:
            self.assertIsNone(item["score"])
            self.assertFalse(item["eligible_for_trade"])
            self.assertEqual(item["participation"], "bilinmiyor")
            self.assertIn("reviewed_standard_evidence_missing",
                          item["participation_review_reasons"])
            self.assertIn("five_company_valuation_comparison_not_run", item["blockers"])
        self.assertIn("MSFT", cohort.render_markdown(result))

    def test_exact_cik_or_duplicate_rejected(self):
        good = [{"symbol": s, "issuer_id": c} for s, c in cohort.COHORT]
        bad = [dict(x) for x in good]
        bad[1]["issuer_id"] = bad[0]["issuer_id"]
        with self.assertRaisesRegex(ValueError, "mismatch"):
            cohort.validate_cohort(bad)
        with self.assertRaisesRegex(ValueError, "exactly five"):
            cohort.validate_cohort(good[:4])

    def test_cross_issuer_sec_output_never_accepted(self):
        def wrong(payload, **kwargs):
            r = sec(payload, **kwargs)
            r["companies"][1]["issuer_id"] = "0000009999"
            return r
        result = cohort.research_five(
            user_agent="contact@example.org", state_dir="unused",
            market_runner=market, sec_collector=wrong)
        self.assertEqual(result["sec_archived"], 0)
        self.assertTrue(all("sec_batch_ValueError" in r["blockers"] for r in result["companies"]))
        self.assertEqual(result["market_verified"], 5)

    def test_market_failure_isolated_to_one_company(self):
        def fail_one(symbol, fixture=None):
            if symbol == "NVDA":
                raise OSError("temporary")
            return market(symbol)
        result = cohort.research_five(
            user_agent="contact@example.org", state_dir="unused",
            market_runner=fail_one, sec_collector=sec)
        self.assertEqual(result["market_verified"], 4)
        failed = result["companies"][2]
        self.assertEqual(failed["symbol"], "NVDA")
        self.assertIn("market_OSError", failed["blockers"])

    def test_sec_failure_isolated_from_market(self):
        def outage(*args, **kwargs):
            raise OSError("public endpoint unavailable")
        result = cohort.research_five(
            user_agent="contact@example.org", state_dir="unused",
            market_runner=market, sec_collector=outage)
        self.assertEqual(result["market_verified"], 5)
        self.assertEqual(result["sec_archived"], 0)
        self.assertTrue(all(r["score"] is None for r in result["companies"]))

    def test_budget_and_user_agent_required(self):
        with self.assertRaisesRegex(ValueError, "budget"):
            cohort.research_five(user_agent="contact@example.org", state_dir="unused",
                                max_new_fields=71)
        with self.assertRaisesRegex(ValueError, "SEC identifying"):
            cohort.research_five(user_agent="", state_dir="unused")

    def test_no_market_buy_permission_even_if_runner_claims_it(self):
        def unsafe(symbol, fixture=None):
            return dict(market(symbol), eligible_for_trade=True)
        result = cohort.research_five(
            user_agent="contact@example.org", state_dir="unused",
            market_runner=unsafe, sec_collector=sec)
        self.assertEqual(result["market_verified"], 0)
        self.assertTrue(all(r["eligible_for_trade"] is False for r in result["companies"]))


if __name__ == "__main__":
    unittest.main()
