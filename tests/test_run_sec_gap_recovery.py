"""Bounded SEC source-worker and SQLite checkpoint regression tests."""
import json
import tempfile
import unittest
from datetime import datetime,timezone
from pathlib import Path
from scripts.run_sec_gap_recovery import recover
from equity_research.transport import Response

def task(cik="0001045810",field="assets",period="2026-01-25"):
    return {"task_id":"a"*64,"market":"US","symbol":"NVDA","issuer_id":cik,
      "field":field,"period_end":period,
      "required_concept":"us-gaap:Assets" if field=="assets" else "us-gaap:Revenues",
      "route":"source_discovery","approved_value":None,"automatic_substitution":False}

class Fetcher:
    def __init__(self, payload):
        self.calls=0;self.payload=payload
    def snapshot(self,cik):
        self.calls+=1
        body=json.dumps(self.payload).encode()
        return Response("https://data.sec.gov/api/xbrl/companyfacts/CIK"+cik+".json",
                        body,datetime(2026,11,23,tzinfo=timezone.utc)),self.payload

class RecoveryTests(unittest.TestCase):
    def test_exact_filing_evidence_and_restart_do_not_score_or_refetch(self):
        payload={"cik":1045810,"entityName":"NVIDIA","facts":{"us-gaap":{"Assets":{"units":{"USD":[
          {"end":"2026-01-25","val":100,"form":"10-K","filed":"2026-02-25",
           "accn":"0001045810-26-000021"}]}}}}}
        fetcher=Fetcher(payload);jobs={"tasks":[task()]}
        with tempfile.TemporaryDirectory() as root:
            db=str(Path(root)/"worker.sqlite")
            result=recover(jobs,db_path=db,fetcher=fetcher,max_issuers=1)
            self.assertEqual(result["observations"][0]["status"],"exact_candidate")
            self.assertEqual(result["observations"][0]["value"],"100")
            self.assertEqual(result["scores_generated"],0)
            self.assertFalse(result["investment_approved"])
            self.assertEqual(result["network_fetches"],1)
            again=recover(jobs,db_path=db,fetcher=fetcher,max_issuers=1)
            self.assertEqual(fetcher.calls,1)
            self.assertEqual(again["network_fetches"],0)

    def test_missing_concept_never_promotes_value(self):
        fetcher=Fetcher({"cik":1045810,"entityName":"NVIDIA","facts":{"us-gaap":{}}})
        with tempfile.TemporaryDirectory() as root:
            out=recover({"tasks":[task()]},db_path=str(Path(root)/"checkpoint.db"),
                        fetcher=fetcher,max_issuers=1)
            self.assertEqual(out["observations"][0]["status"],"concept_not_disclosed")
            self.assertIsNone(out["observations"][0]["value"])

    def test_other_issuer_payload_rejected(self):
        fetcher=Fetcher({"cik":1018724,"entityName":"wrong","facts":{"us-gaap":{}}})
        with tempfile.TemporaryDirectory() as root:
            out=recover({"tasks":[task()]},db_path=str(Path(root)/"checkpoint.db"),
                        fetcher=fetcher,max_issuers=1)
            self.assertEqual(out["observations"][0]["status"],"source_identity_mismatch")
            self.assertEqual(out["network_fetches"],1)

    def test_scope_change_is_not_an_exact_candidate(self):
        payload={"cik":1045810,"entityName":"NVIDIA","facts":{"us-gaap":{"Revenues":{"units":{"USD":[
          {"start":"2025-01-26","end":"2026-01-25","val":123,"form":"10-K",
           "filed":"2026-02-25","accn":"0001045810-26-000021"}]}}}}}
        t=task(field="revenue")
        with tempfile.TemporaryDirectory() as root:
            out=recover({"tasks":[t]},db_path=str(Path(root)/"checkpoint.db"),
                        fetcher=Fetcher(payload),max_issuers=1)
            self.assertEqual(out["observations"][0]["status"],"scope_review_required")
            self.assertFalse(out["observations"][0]["approved_for_scoring"])

    def test_budget_is_per_issuer_not_per_missing_field(self):
        t=task();other=dict(t,task_id="b"*64,field="liabilities",required_concept="us-gaap:Liabilities")
        fetcher=Fetcher({"cik":1045810,"entityName":"NVIDIA","facts":{"us-gaap":{}}})
        with tempfile.TemporaryDirectory() as root:
            out=recover({"tasks":[t,other]},db_path=str(Path(root)/"checkpoint.db"),
                        fetcher=fetcher,max_issuers=1)
            self.assertEqual(fetcher.calls,1)
            self.assertEqual(len(out["observations"]),2)

if __name__=="__main__": unittest.main()
