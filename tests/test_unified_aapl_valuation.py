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
