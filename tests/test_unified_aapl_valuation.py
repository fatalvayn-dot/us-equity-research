"""No fabricated valuation: one-issuer source states and score-plan diagnosis tests."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from scripts import unified_aapl_valuation as bridge


def report(identity="exact_match", shares="verified_dated_share_class",
           price="valid", history="valid", cik=bridge.CIK):
    return {"as_of": "2026-11-22T11:00:00+00:00",
            "companies": [{
                "symbol": "AAPL", "issuer_id": cik,
                "identity_status": identity,
                "share_check": {"status": shares},
                "price_check": {"status": price},
                "history_check": {"status": history},
            }]}


class ValuationBridgeTests(unittest.TestCase):
    def test_four_source_gates_without_score(self):
        out = bridge.summarize(report())
        self.assertTrue(out["market_source_complete"])
        self.assertEqual(out["blockers"], [])
        self.assertIsNone(out["score"])
        self.assertFalse(out["eligible_for_trade"])

    def test_missing_shares_is_explicit_not_zero(self):
        out = bridge.summarize(report(shares="missing_disclosed_shares",
                                      history="not_started"))
        self.assertEqual([x["stage"] for x in out["blockers"]], ["share", "history"])
        self.assertFalse(out["market_source_complete"])

    def test_cik_mismatch_fails_closed(self):
        with self.assertRaisesRegex(ValueError, "identity mismatch"):
            bridge.summarize(report(cik="0000789019"))

    def test_reuses_collector_only_once(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "seed"
            p.mkdir()
            (p / "manifest.json").write_text("{}")
            with patch.object(bridge, "run_collection", return_value=report()) as fn:
                result, summary = bridge.collect(
                    state_dir=Path(tmp) / "valuation", user_agent="Verified contact example@example.com",
                    source_bundle=p)
            self.assertTrue(summary["market_source_complete"])
            fn.assert_called_once()
            self.assertEqual(fn.call_args.kwargs["max_new_requests"], 8)
            self.assertEqual(fn.call_args.kwargs["seed_bundles"], (str(p),))

    def test_combined_radar_rejects_invented_valuation_score(self):
        import json
        from scripts import unified_single_issuer as radar
        with tempfile.TemporaryDirectory() as tmp:
            fixture = Path(tmp) / "aapl.json"
            fixture.write_text(json.dumps({
                "AAPL": [
                    {"date": "2026-09-%02d" % day, "close": 100 + day}
                    for day in range(1, 31)]
            }))
            summary = bridge.summarize(report(shares="pending_source_collection"))
            with self.assertRaisesRegex(ValueError, "invent a score"):
                radar.build("AAPL", fixture=str(fixture), financial_cik=bridge.CIK,
                            valuation_summary=dict(summary, score=42))
            result = radar.build("AAPL", fixture=str(fixture), financial_cik=bridge.CIK,
                                 valuation_summary=summary)
            self.assertEqual(result["valuation_research"]["status"], "incomplete_market_evidence")
            self.assertIn("Değerleme kaynak durumu", radar.turkish_issuer_report(result))
            self.assertFalse(result["eligible_for_trade"])

    def test_score_summary_blocks_unverified_and_keeps_score_null(self):
        from scripts.unified_aapl_score_summary import summarize_score
        sample = {"as_of": "2026-11-22T12:00:00+00:00",
                  "companies": [{"symbol": "AAPL", "issuer_id": bridge.CIK,
                                 "status": "review_required",
                                 "total_score": None,
                                 "blockers": ["comparison_evidence_missing"]}]}
        out = summarize_score(sample)
        self.assertIsNone(out["score"])
        self.assertEqual(out["blockers"], ["comparison_evidence_missing"])
        self.assertFalse(out["eligible_for_trade"])

    def test_scored_hypothesis_remains_not_approved(self):
        from scripts.unified_aapl_score_summary import summarize_score
        sample = {"as_of": "2026-11-22T12:00:00+00:00",
                  "companies": [{"symbol": "AAPL", "issuer_id": bridge.CIK,
                                 "status": "scored_research_hypothesis",
                                 "total_score": 72,
                                 "model_version": "operating-sector-research-batch-v2",
                                 "blockers": []}]}
        out = summarize_score(sample)
        self.assertEqual(out["score"], 72)
        self.assertFalse(out["investment_approved"])

    def test_score_summary_must_reject_cross_issuer_and_fabricated(self):
        from scripts.unified_aapl_score_summary import summarize_score
        sample = {"companies": [{"symbol": "MSFT", "issuer_id": bridge.CIK,
                                 "status": "scored_research_hypothesis",
                                 "total_score": 73}]}
        with self.assertRaisesRegex(ValueError, "issuer mismatch"):
            summarize_score(sample)
        sample["companies"][0]["symbol"] = "AAPL"
        sample["companies"][0]["status"] = "review_required"
        with self.assertRaisesRegex(ValueError, "unsupported score"):
            summarize_score(sample)

    def test_request_budget_hard_limit(self):
        with self.assertRaisesRegex(ValueError, "budget"):
            bridge.collect(state_dir="/tmp/x", user_agent="contact@example.com",
                           source_bundle="/tmp/missing", max_new_requests=501)

    def test_plan_diagnostic_delegates_to_existing_planner(self):
        import json
        with tempfile.TemporaryDirectory() as tmp:
            for key in ("financial", "metadata"):
                (Path(tmp) / (key + ".json")).write_text(
                    json.dumps({"companies": []}), encoding="utf-8")
            expected = ({"companies": []}, {"companies": []},
                        {"evaluated": 1, "selected": 0,
                         "excluded_reasons": {"market_or_original_share_evidence_incomplete": 1}})
            with patch.object(bridge, "plans", return_value=expected) as planner:
                result = bridge.plan_review(
                    financial_batch=Path(tmp) / "financial.json",
                    metadata=Path(tmp) / "metadata.json",
                    valuation_report=report(),
                    companyfacts_dir=tmp)
            self.assertEqual(result[2]["selected"], 0)
            planner.assert_called_once()


if __name__ == "__main__":
    unittest.main()
