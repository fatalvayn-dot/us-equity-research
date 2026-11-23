"""Tests for the read-only missing-data research worker."""
import unittest
from scripts.us_five_missing_data_agent import build_queue

CIKS = {"AAPL":"0000320193","MSFT":"0000789019","NVDA":"0001045810","AMZN":"0001018724","GOOGL":"0001652044"}

def sample():
    gaps={"cohort":"US_FIVE_V1","investment_approved":False,"companies":[]}
    original={"investment_approved":False,"issuer_reviews":[]}
    for s,c in CIKS.items():
        missing = {"NVDA":["revenue","capital_expenditure"],
                   "AMZN":["liabilities","capital_expenditure"]}.get(s,[])
        g = list(missing) + (["dated_exact_share_class"] if s=="GOOGL" else [])
        gaps["companies"].append({"symbol":s,"issuer_id":c,"gaps":g,
            "missing_required_facts":[{"field":f,"required_concept":"exact annual GAAP",
                "source_attempts":[{"source":"SEC","status":"not_found"}]} for f in missing],
            "share_class_status":"multiple_class_review" if s=="GOOGL" else "verified_dated_share_class"})
        if s in ("NVDA","AMZN","GOOGL"):
            original["issuer_reviews"].append({"symbol":s,"issuer_id":c,
                "original_source_url":"https://www.sec.gov/Archives/edgar/data/"+c+"/filing.htm",
                "original_source_sha256":"a"*64,"source_hash_reverified":True,
                "automatic_substitution":False,"score_eligible":False,
                "disclosed_concepts":[{"concept":"us-gaap:Revenues","status":"exact_original_value"}],
                "security_class":{"status":"multiple_class_counts_verified_valuation_model_still_required",
                  "cover_as_of":"2026-01-28","reported_class_counts_million":{"A":5822,"B":837,"C":5438}} if s=="GOOGL" else None})
    return gaps, original

class ResearchQueueTests(unittest.TestCase):
    def test_creates_exact_field_tasks_without_scoring(self):
        doc=build_queue(*sample())
        self.assertEqual(len(doc["tasks"]),5)
        self.assertEqual({t["symbol"] for t in doc["tasks"]},{"NVDA","AMZN","GOOGL"})
        self.assertFalse(doc["investment_approved"])
        self.assertFalse(doc["automatic_substitution"])
        self.assertEqual(doc["network_requests"],0)
        self.assertTrue(all(t["verification_state"]=="requires_accounting_review" for t in doc["tasks"]))
        self.assertTrue(all(t["original_source_sha256"]=="a"*64 for t in doc["tasks"]))

    def test_cross_issuer_original_rejected(self):
        g,o=sample()
        o["issuer_reviews"][0]["issuer_id"]="0000320193"
        with self.assertRaisesRegex(ValueError,"original issuer mismatch"):
            build_queue(g,o)

    def test_missing_verified_filing_does_not_claim_evidence(self):
        g,o=sample()
        o["issuer_reviews"][0]["source_hash_reverified"]=False
        with self.assertRaisesRegex(ValueError,"unverified original"):
            build_queue(g,o)

    def test_gap_with_no_field_record_never_silently_disappears(self):
        g,o=sample()
        g["companies"][2]["missing_required_facts"]=[]
        with self.assertRaisesRegex(ValueError,"field evidence mismatch"):
            build_queue(g,o)

if __name__=="__main__":
    unittest.main()
