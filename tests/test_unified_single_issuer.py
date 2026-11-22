"""Deterministic whole-pipeline smoke; fixture is never labeled live."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts import unified_single_issuer as target


class OneIssuer(unittest.TestCase):
    def fixture(self, root):
        path = Path(root) / "sample.json"
        path.write_text(json.dumps({"AAPL": [
            {"date": "2026-09-%02d" % day, "close": 100 + day}
            for day in range(1, 31)
        ]}), encoding="utf-8")
        return str(path)

    def test_fixture_end_to_end_no_false_approval(self):
        with tempfile.TemporaryDirectory() as root:
            report = target.build("AAPL", fixture=self.fixture(root))
        self.assertEqual(report["source"], "fixture")
        self.assertEqual(report["summary"]["mode"], "historical_fixture")
        self.assertEqual(report["summary"]["status"], "test_verisi")
        self.assertEqual(report["gates"]["fundamentals"], "blocked_missing_filing_evidence")
        self.assertEqual(report["gates"]["participation"], "unknown")
        self.assertFalse(report["eligible_for_trade"])
        self.assertFalse(report["investment_advice"])
        self.assertEqual(report["llm"]["status"], "disabled")

    def test_mock_five_handoffs_and_one_price_fetch(self):
        calls = []
        def fake_provider(payload):
            calls.append(payload["model"])
            return {"choices": [{"message": {"content": "Kanıt eksik, yatırım önerisi yok."}}]}
        with tempfile.TemporaryDirectory() as root:
            with patch.object(target, "price_history", wraps=target.price_history) as prices:
                report = target.build(
                    "AAPL", fixture=self.fixture(root),
                    agent_transport=fake_provider, enable_llm=True)
                prices.assert_called_once()
        self.assertEqual(calls, ["openrouter/free"] * 5)
        self.assertEqual(report["llm"]["llm_calls"], 5)
        self.assertFalse(report["eligible_for_trade"])

    def test_missing_fixture_fails_closed(self):
        with tempfile.TemporaryDirectory() as root:
            with self.assertRaisesRegex(ValueError, "missing"):
                target.build("MSFT", fixture=self.fixture(root))

    def test_participation_wrong_issuer_is_rejected(self):
        with tempfile.TemporaryDirectory() as root:
            with self.assertRaisesRegex(ValueError, "symbol mismatch"):
                target.build(
                    "AAPL", fixture=self.fixture(root),
                    participation_evidence={"company": {"symbol": "MSFT"}})

    def test_existing_participation_engine_blocks_unverified_facts(self):
        with tempfile.TemporaryDirectory() as root:
            evidence = {
                "company": {"issuer_key": "SEC:0000320193", "symbol": "AAPL"},
                "rulebook": None,
            }
            result = target.build(
                "AAPL", fixture=self.fixture(root),
                participation_evidence=evidence)
        self.assertEqual(result["participation_research"]["status"], "bilinmiyor")
        self.assertIn("reviewed_standard_evidence_missing",
                      result["participation_research"]["review_reasons"])
        self.assertTrue(result["participation_research"]["no_live_source_verification"])
        self.assertFalse(result["eligible_for_trade"])
        self.assertFalse(result["investment_advice"])

    def test_sec_report_handoff_with_exact_identity(self):
        from datetime import datetime, timezone
        proof = {
            "as_of": "2026-11-20T11:00:00+00:00",
            "companies": [{"symbol": "AAPL", "issuer_id": "0000320193",
                           "accepted_fact_count": 9}],
            "pipeline": {"all_financial_references_archived": True},
        }
        with patch.object(target, "price_history", return_value=(
            [{"date": "2026-10-%02d" % i, "close": 100 + i} for i in range(1, 31)],
            "fixture")):
            result = target.build(
                "AAPL", financial_report=proof, financial_cik="0000320193")
        self.assertEqual(result["financial_research"]["accepted_fact_count"], 9)
        self.assertEqual(result["gates"]["fundamentals"], "facts_observed_review_required")
        self.assertEqual(result["gates"]["valuation"], "blocked_missing_fundamentals")
        self.assertFalse(result["eligible_for_trade"])

    def test_sec_handoff_rejects_mismatched_cik(self):
        proof = {"as_of": "2026-11-20T11:00:00+00:00",
                 "companies": [{"symbol": "AAPL", "issuer_id": "0000789019",
                                "accepted_fact_count": 9}]}
        with tempfile.TemporaryDirectory() as root:
            with self.assertRaisesRegex(ValueError, "issuer identity mismatch"):
                target.build("AAPL", fixture=self.fixture(root),
                             financial_report=proof, financial_cik="0000320193")

    def test_sec_handoff_does_not_approve_unarchived_sources(self):
        proof = {"as_of": "2026-11-20T11:00:00+00:00",
                 "companies": [{"symbol": "AAPL", "issuer_id": "0000320193",
                                "accepted_fact_count": 9}],
                 "pipeline": {"all_financial_references_archived": False}}
        with tempfile.TemporaryDirectory() as root:
            result = target.build("AAPL", fixture=self.fixture(root),
                                  financial_report=proof, financial_cik="0000320193")
        self.assertEqual(result["financial_research"]["status"], "incomplete_evidence")
        self.assertFalse(result["eligible_for_trade"])

    def test_sec_collection_wrapper_reuses_existing_mvp(self):
        from scripts import unified_sec_one_issuer as sec
        sample = {"companies": []}
        with patch.object(sec, "run_mvp", return_value=sample) as collector:
            output = sec.collect_one(state_dir="tmp/test-sec", user_agent="Research Team contact: example@example.org")
        self.assertIs(output, sample)
        self.assertEqual(collector.call_args.args[0]["companies"], [
            {"symbol": "AAPL", "issuer_id": "0000320193"}])
        with self.assertRaisesRegex(ValueError, "exact reviewed AAPL"):
            sec.collect_one(symbol="MSFT", state_dir="tmp/test-sec",
                            user_agent="Research Team contact: example@example.org")

    def test_existing_financial_calculation_count_and_risk_gate(self):
        proof = {
            "as_of": "2026-11-20T11:00:00+00:00",
            "companies": [{
                "symbol": "AAPL", "issuer_id": "0000320193",
                "accepted_fact_count": 11,
                "financial_assessment": {"quantitative_gate": "no_screen_trigger"},
                "calculations": [{"value": "1.25"}, {"value": None}, {"value": "2.4"}],
            }],
            "pipeline": {"all_financial_references_archived": True},
        }
        with tempfile.TemporaryDirectory() as root:
            result = target.build("AAPL", fixture=self.fixture(root),
                                  financial_report=proof, financial_cik="0000320193")
        self.assertEqual(result["financial_research"]["existing_calculation_count"], 2)
        self.assertEqual(result["financial_research"]["financial_risk_gate"], "no_screen_trigger")
        text = target.turkish_issuer_report(result)
        self.assertIn("11", text)
        self.assertIn("Hesaplanmadı", text)
        self.assertIn("Yatırım kararı: KAPALI", text)
        self.assertIn("\n- Katılım", text)
        self.assertFalse(result["eligible_for_trade"])

    def test_financial_details_are_not_forwarded_to_llm(self):
        import json as _json
        from scripts import llm_team
        proof = {
            "as_of": "2026-11-20T11:00:00+00:00",
            "companies": [{
                "symbol": "AAPL", "issuer_id": "0000320193",
                "accepted_fact_count": 11,
                "financial_assessment": {"quantitative_gate": "no_screen_trigger"},
                "calculations": [{"value": "1.25", "private": "SHOULD_NOT_LEAK"}],
            }],
            "pipeline": {"all_financial_references_archived": True},
        }
        captured = []
        def fake(request):
            captured.append(request)
            return {"choices": [{"message": {"content": "research only"}}]}
        with tempfile.TemporaryDirectory() as root:
            result = target.build(
                "AAPL", fixture=self.fixture(root),
                financial_report=proof, financial_cik="0000320193",
                enable_llm=True, agent_transport=fake)
        contents = _json.dumps(captured)
        self.assertNotIn("SHOULD_NOT_LEAK", contents)
        self.assertNotIn("1.25", contents)
        self.assertIn("no_screen_trigger", contents)
        self.assertEqual(result["llm"]["llm_calls"], 5)

    def test_live_price_source_failure_fails_closed(self):
        with patch.object(target.pilot, "fetch_yfinance", side_effect=OSError("offline")), \
             patch.object(target.pilot, "fetch_yahoo_chart", side_effect=OSError("offline")), \
             patch.object(target.pilot, "fetch_prices", side_effect=OSError("offline")):
            with self.assertRaisesRegex(RuntimeError, "no verified price history"):
                target.build("AAPL")


if __name__ == "__main__":
    unittest.main()
