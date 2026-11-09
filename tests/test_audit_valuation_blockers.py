"""Synthetic 100-company valuation blocker audit regression tests."""
import copy
import json
import tempfile
import unittest
from pathlib import Path

from scripts.audit_valuation_blockers import audit


def fixture():
    rows=[]
    for i in range(100):
        rows.append(dict(symbol="SYM"+str(i),issuer_id=f"{i+1:010d}",
                         identity_status="exact_match",
                         share_check=dict(status="verified_dated_share_class"),
                         price_check=dict(status="valid"),
                         history_check=dict(status="valid"),
                         attempts=[]))
    rows[0]["share_check"]=dict(status="pending_source_collection")
    rows[0]["price_check"]=dict(status="pending_source_collection")
    rows[0]["history_check"]=dict(status="not_started",deferred_reason="share_class_unverified")
    rows[0]["attempts"]=[dict(stage="companyfacts",http_requested=True),
                        dict(stage="price",http_requested=False)]
    rows[1]["share_check"]=dict(status="invalid_data")
    rows[1]["history_check"]=dict(status="not_started")
    return dict(report_kind="valuation_source_collection_scope_pending",
                as_of="2026-11-09T10:00:00+00:00",companies=rows,
                summary=dict(candidates=100)),dict(companies=[
                    dict(symbol=rows[i]["symbol"],issuer_id=rows[i]["issuer_id"])
                    for i in (0,1,2)])


class AuditBlockerTests(unittest.TestCase):
    def test_complete_and_failed_legs_are_separate(self):
        report,plan=fixture()
        result=audit(report,plan)
        self.assertEqual(result["candidates"],100)
        self.assertEqual(result["priority_candidates"],3)
        self.assertEqual(result["priority_complete"],1)
        self.assertEqual(result["all_complete"],98)
        self.assertEqual(result["priority_gets"],1)
        self.assertEqual(result["blocker_counts"]["share_check:pending_source_collection"],1)
        self.assertEqual(result["blocker_counts"]["share_check:invalid_data"],1)
        self.assertEqual(result["priority"][0]["blockers"][2]["deferred_reason"],"share_class_unverified")
        self.assertFalse(result["mvp_accepted"])
        json.dumps(result)

    def test_prioritized_output_keeps_plan_order(self):
        report,plan=fixture()
        plan["companies"].reverse()
        result=audit(report,plan)
        self.assertEqual([x["symbol"] for x in result["priority"]],["SYM2","SYM1","SYM0"])
        self.assertEqual(len(result["other_companies"]),97)

    def test_identity_mismatch_and_duplicates_fail_closed(self):
        report,plan=fixture()
        plan["companies"][0]["issuer_id"]="0000009999"
        with self.assertRaises(ValueError):
            audit(report,plan)
        report,plan=fixture()
        plan["companies"].append(plan["companies"][0].copy())
        with self.assertRaises(ValueError):
            audit(report,plan)
        report,plan=fixture()
        report["companies"].append(report["companies"][0].copy())
        report["summary"]["candidates"]=101
        with self.assertRaises(ValueError):
            audit(report,plan)

    def test_missing_or_invalid_leg_is_never_accepted(self):
        report,plan=fixture()
        report["companies"][2]["share_check"]={}
        with self.assertRaises(ValueError):
            audit(report,plan)
        report,plan=fixture()
        report["companies"][2]["identity_status"]="symbol_mismatch"
        result=audit(report,plan)
        self.assertEqual(result["priority_complete"],0)
        self.assertFalse(result["priority"][2]["market_evidence_complete"])

    def test_no_new_source_requests_not_implied_as_progress(self):
        report,plan=fixture()
        report["companies"][0]["attempts"]=[]
        result=audit(report,plan)
        self.assertEqual(result["priority_gets"],0)
        self.assertFalse(result["priority"][0]["market_evidence_complete"])


if __name__=="__main__":
    unittest.main()
