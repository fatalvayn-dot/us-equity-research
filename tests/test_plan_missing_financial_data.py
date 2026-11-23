"""Contract-first tests for scalable source recovery planning."""
import unittest
from scripts.plan_missing_financial_data import plan

def issuer(i, missing):
    return {"symbol": "S"+str(i), "issuer_id": str(i).zfill(10), "market":"US",
            "missing_required_facts": [{"field":field, "required_concept":"us-gaap:Liabilities",
                "source_attempts":[{"source":"SEC","status":"not_found"}]} for field in missing]}

class RecoveryPlanTests(unittest.TestCase):
    def test_1000_companies_are_deduplicated_and_bounded(self):
        companies=[issuer(i,["liabilities","liabilities"]) for i in range(1,1001)]
        result=plan({"companies":companies},max_tasks=75)
        self.assertEqual(result["total_unique_gaps"],1000)
        self.assertEqual(len(result["tasks"]),75)
        self.assertEqual(result["deferred_count"],925)
        self.assertEqual(result["network_requests"],0)
        self.assertFalse(result["investment_approved"])
        self.assertEqual(len(set(x["task_id"] for x in result["tasks"])),75)

    def test_new_period_gets_new_key(self):
        a=issuer(1,["liabilities"])
        a["period_end"]="2025-12-31"
        b=plan({"companies":[a]})["tasks"][0]["task_id"]
        a["period_end"]="2026-03-31"
        self.assertNotEqual(b,plan({"companies":[a]})["tasks"][0]["task_id"])

    def test_change_in_accounting_definition_invalidates_recovery_cache(self):
        a=issuer(1,["liabilities"])
        before=plan({"companies":[a]})["tasks"][0]["task_id"]
        a["missing_required_facts"][0]["required_concept"]="us-gaap:LiabilitiesAndStockholdersEquity"
        self.assertNotEqual(before,plan({"companies":[a]})["tasks"][0]["task_id"])

    def test_verified_cache_skips_unneeded_research_but_never_fills_score(self):
        source={"companies":[issuer(1,["liabilities"])]}
        first=plan(source)["tasks"][0]
        result=plan(source,previous={"tasks":[{"task_id":first["task_id"],
            "status":"verified_exact","evidence_sha256":"a"*64}]})
        self.assertEqual(len(result["tasks"]),0)
        self.assertEqual(result["cached_verified"],1)
        self.assertEqual(result["scores_generated"],0)

    def test_rate_limited_provider_has_cooldown_not_unlimited_retry(self):
        a=issuer(1,["liabilities"])
        a["missing_required_facts"][0]["source_attempts"]=[{"source":"SEC","status":"rate_limited"}]
        r=plan({"companies":[a]})
        self.assertEqual(r["tasks"][0]["route"],"provider_cooldown")
        self.assertEqual(r["tasks"][0]["automatic_substitution"],False)

    def test_conflicting_company_identity_rejected(self):
        x=issuer(1,["liabilities"])
        y=issuer(1,["assets"])
        y["symbol"]="OTHER"
        with self.assertRaisesRegex(ValueError,"issuer identity"):
            plan({"companies":[x,y]})

    def test_ambiguous_candidate_never_approved(self):
        r=plan({"companies":[issuer(1,["capital_expenditure"])]})
        self.assertEqual(r["tasks"][0]["route"],"accounting_scope_review")
        self.assertIsNone(r["tasks"][0]["approved_value"])

    def test_invalid_market_rejected(self):
        a=issuer(1,["liabilities"]);a["market"]="UNKNOWN"
        with self.assertRaises(ValueError):
            plan({"companies":[a]})

if __name__=="__main__": unittest.main()
