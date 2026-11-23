import unittest
from scripts.audit_us_five_live_run import audit

SYMS=("AAPL","MSFT","NVDA","AMZN","GOOGL")

def inputs():
    sec={"companies":[{"symbol":s,"issuer_id":str(i+1).zfill(10),"fields":[]} for i,s in enumerate(SYMS)]}
    scored={"companies":[{"symbol":s,"score":"60","score_status":"scored_research_hypothesis"} for s in SYMS],"fully_scored":5}
    gaps={"companies":[{"symbol":s,"gaps":[]} for s in SYMS]}
    verdict={"companies":[{"symbol":s,"remaining_gaps":[]} for s in SYMS],
             "scores_generated":5,"full_cohort_research_accepted":True}
    recovery={"observations":[],"network_fetches":1}
    return {"sec":sec,"scored":scored,"gaps":gaps,"verdict":verdict,"recovery":recovery}

class LiveStageAuditTests(unittest.TestCase):
    def test_complete_five_carries_stage_proof(self):
        r=audit(inputs())
        self.assertTrue(r["technical_research_accepted"])
        self.assertFalse(r["investment_approved"])
        self.assertEqual(len(r["critical_blockers"]),0)

    def test_missing_scoring_artifact_is_not_success(self):
        x=inputs();x["scored"]=None
        r=audit(x)
        self.assertFalse(r["technical_research_accepted"])
        self.assertIn("scoring_artifact_missing",r["critical_blockers"])

    def test_scored_count_two_is_blocker_not_fake_five(self):
        x=inputs();x["scored"]["fully_scored"]=2
        x["scored"]["companies"][2]["score"]=None
        x["scored"]["companies"][3]["score"]=None
        x["scored"]["companies"][4]["score"]=None
        x["verdict"]["scores_generated"]=2;x["verdict"]["full_cohort_research_accepted"]=False
        r=audit(x)
        self.assertFalse(r["technical_research_accepted"])
        self.assertIn("only_2_of_5_scored",r["critical_blockers"])

    def test_missing_live_sec_is_not_masked_by_offline_verdict(self):
        x=inputs();x["sec"]=None
        r=audit(x)
        self.assertIn("sec_evidence_missing",r["critical_blockers"])

    def test_recovery_is_not_counted_as_score(self):
        x=inputs();x["recovery"]={"observations":[{"status":"exact_candidate"}],"network_fetches":3}
        x["scored"]["fully_scored"]=2
        x["verdict"]["scores_generated"]=2;x["verdict"]["full_cohort_research_accepted"]=False
        r=audit(x)
        self.assertEqual(r["scored"],2)
        self.assertEqual(r["recovery_candidates"],1)

if __name__=="__main__":unittest.main()
