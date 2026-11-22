import copy
import unittest

from scripts.us_five_final_verdict import verdict, markdown
from scripts.unified_us_five import COHORT


def evidence():
    scored = {"cohort": "US_FIVE_V1", "as_of": "2026-11-22T15:00:00+00:00",
              "market_verified": 5, "sec_archived": 5,
              "valuation_sources_verified": 4, "investment_approved": False,
              "companies": []}
    gaps = {"cohort": "US_FIVE_V1", "investment_approved": False, "companies": []}
    original = {
        "network_requests": 0, "investment_approved": False,
        "accounting_substitutions_approved": False,
        "multi_class_valuation_approved": False, "issuer_reviews": [],
    }
    for i, (symbol, cik) in enumerate(COHORT):
        score = "67.5" if i == 0 else "66.5" if i == 1 else None
        issue = [] if score is not None else ["revenue"] if symbol == "NVDA" else [
            "liabilities"] if symbol == "AMZN" else ["dated_exact_share_class"]
        scored["companies"].append({
            "symbol": symbol, "issuer_id": cik, "score": score,
            "score_status": ("scored_research_hypothesis" if score is not None
                             else "blocked_source_or_comparison_evidence"),
            "participation": "bilinmiyor",
            "eligible_for_trade": False, "investment_approved": False,
        })
        gaps["companies"].append({
            "symbol": symbol, "issuer_id": cik, "investment_approved": False,
            "gaps": issue, "share_class_status": "missing_disclosed_shares"
            if symbol == "GOOGL" else "verified_dated_share_class",
            "risk_screen": "unresolved" if symbol == "AMZN" else "no_screen_trigger",
            "missing_required_facts": [{"field": e} for e in issue if e != "dated_exact_share_class"],
        })
        if score is None:
            original["issuer_reviews"].append({
                "symbol": symbol, "issuer_id": cik,
                "original_source_sha256": "a" * 64,
                "source_hash_reverified": True,
                "automatic_substitution": False, "score_eligible": False,
                "disclosed_concepts": [
                    {"concept": "us-gaap:Revenues", "status": "exact_original_value"}],
            })
    return scored, gaps, original


class FiveVerdictTests(unittest.TestCase):
    def test_one_decision_for_both_scored_and_all_missing(self):
        doc = verdict(*evidence())
        self.assertEqual(doc["scores_generated"], 2)
        self.assertEqual(doc["root_cause_checked"], 3)
        self.assertTrue(doc["research_data_collection_operational"])
        self.assertFalse(doc["full_cohort_research_accepted"])
        self.assertFalse(doc["expansion_to_25_approved"])
        self.assertEqual(doc["decision"], "BES_SIRKET_TAM_KABUL_YOK")
        self.assertIn("GOOGL", markdown(doc))
        self.assertFalse(doc["investment_approved"])

    def test_cross_issuer_source_never_accepted(self):
        scored, gaps, original = evidence()
        original["issuer_reviews"][1]["issuer_id"] = "0000320193"
        with self.assertRaisesRegex(ValueError, "issuer identity mismatch"):
            verdict(scored, gaps, original)

    def test_unsafe_alt_alias_cannot_clear_company(self):
        scored, gaps, original = evidence()
        original["issuer_reviews"][0]["automatic_substitution"] = True
        with self.assertRaisesRegex(ValueError, "proof missing or unsafe"):
            verdict(scored, gaps, original)

    def test_not_scored_cannot_claim_success(self):
        scored, gaps, original = evidence()
        scored["companies"][2]["score_status"] = "scored_research_hypothesis"
        with self.assertRaisesRegex(ValueError, "missing score"):
            verdict(scored, gaps, original)

    def test_score_with_unresolved_original_gaps_never_accepted(self):
        scored, gaps, original = evidence()
        scored["companies"][2]["score"] = "99.9"
        scored["companies"][2]["score_status"] = "scored_research_hypothesis"
        with self.assertRaisesRegex(ValueError, "contradicts source gaps"):
            verdict(scored, gaps, original)

    def test_missing_source_document_never_accepted(self):
        scored, gaps, original = evidence()
        original["issuer_reviews"].pop()
        with self.assertRaisesRegex(ValueError, "incomplete"):
            verdict(scored, gaps, original)


if __name__ == "__main__":
    unittest.main()
