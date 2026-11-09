"""Score-to-market-source gap tracing; fixtures do not represent live stocks."""
import copy
import json
import unittest
from datetime import datetime, timezone
from scripts.audit_score_valuation_gaps import diagnose


def fixtures():
    ids=[dict(symbol=f"T{i}",issuer_id=f"{i+1:010d}") for i in range(100)]
    score=dict(as_of="2026-11-09T12:00:00+00:00",
               companies=[dict(**row,blockers=[("valuation_source_evidence_required"
                        if i in (0,1) else "specialized_or_unmodeled_sector")])
                        for i,row in enumerate(ids)],
               summary=dict(candidates=100,scored_companies=0))
    source=dict(as_of="2026-11-09T11:00:00+00:00",
                report_kind="valuation_source_collection_scope_pending",
                companies=[dict(**row,identity_status="exact_match",
                    share_check=dict(status="verified_dated_share_class"),
                    price_check=dict(status="valid"),
                    history_check=dict(status="valid"),attempts=[]) for row in ids],
                summary=dict(candidates=100))
    source["companies"][0]["share_check"]=dict(status="pending_source_collection")
    source["companies"][0]["history_check"]=dict(status="not_started",deferred_reason="share_class_unverified")
    source["companies"][0]["attempts"]=[dict(stage="companyfacts",status="not_started",
        http_requested=False,deferred_reason="request_budget")]
    source["companies"][1]["price_check"]=dict(status="invalid_data")
    source["companies"][1]["attempts"]=[dict(stage="price",status="invalid_data",
        http_requested=True)]
    return score,source


class SourceGapTraceTests(unittest.TestCase):
    def test_real_source_statuses_are_not_approved_or_zero_filled(self):
        score,source=fixtures()
        result=diagnose(score,source)
        self.assertEqual(result["valuation_source_blockers"],2)
        self.assertEqual(result["source_stage_counts"],{
            "history_check:not_started":1,
            "price_check:invalid_data":1,
            "share_check:pending_source_collection":1})
        self.assertEqual([x["new_gets"] for x in result["companies"]],[0,1])
        self.assertTrue(all(x["score"] is None for x in result["companies"]))
        self.assertFalse(result["mvp_accepted"])
        json.dumps(result)

    def test_failed_identity_and_duplicate_rejected(self):
        score,source=fixtures()
        source["companies"][0]["issuer_id"]="0000000999"
        with self.assertRaisesRegex(ValueError,"kimlik"):
            diagnose(score,source)
        score,source=fixtures()
        score["companies"][1]["symbol"]=score["companies"][0]["symbol"]
        score["companies"][1]["issuer_id"]=score["companies"][0]["issuer_id"]
        with self.assertRaisesRegex(ValueError,"tekrarlı"):
            diagnose(score,source)

    def test_cutoff_and_full_cohort_enforced(self):
        score,source=fixtures()
        source["as_of"]="2026-11-10T00:00:00+00:00"
        with self.assertRaisesRegex(ValueError,"kesimi"):
            diagnose(score,source)
        score,source=fixtures()
        source["companies"].pop()
        with self.assertRaisesRegex(ValueError,"100"):
            diagnose(score,source)

    def test_missing_stage_or_invalid_broken_input_rejected(self):
        score,source=fixtures()
        source["companies"][1]["history_check"].pop("status")
        with self.assertRaisesRegex(ValueError,"bacağı"):
            diagnose(score,source)
        score,source=fixtures()
        source["companies"][1]["attempts"]=[dict(status="invalid_data")]
        with self.assertRaisesRegex(ValueError,"denemesi"):
            diagnose(score,source)

    def test_supported_company_without_market_blocker_never_added(self):
        score,source=fixtures()
        score["companies"][0]["blockers"]=[]
        result=diagnose(score,source)
        self.assertEqual(result["valuation_source_blockers"],1)
        self.assertEqual(result["companies"][0]["symbol"],"T1")


if __name__=="__main__":
    unittest.main()
