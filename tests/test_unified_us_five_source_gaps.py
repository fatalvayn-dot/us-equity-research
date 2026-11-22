import unittest

from scripts.unified_us_five_source_gaps import analyze, markdown
from scripts.unified_us_five import COHORT


def inputs():
    sec = {"companies": []}
    val = {"companies": []}
    plan = {"excluded": [
        {"symbol": "NVDA", "issuer_id": "0001045810", "reason": "nine_model_financial_facts_incomplete"},
        {"symbol": "AMZN", "issuer_id": "0001018724", "reason": "financial_review_required"},
        {"symbol": "GOOGL", "issuer_id": "0001652044", "reason": "nine_model_financial_facts_incomplete"},
    ]}
    required = (
        "assets", "liabilities", "current_assets", "current_liabilities",
        "net_income", "operating_income", "operating_cash_flow",
        "capital_expenditure", "revenue")
    missing = {"NVDA": ("capital_expenditure", "revenue"),
               "AMZN": ("capital_expenditure", "liabilities"),
               "GOOGL": ("revenue",)}
    for symbol, cik in COHORT:
        fields = []
        for name in required:
            absent = name in missing.get(symbol, ())
            fields.append({"query": {"field": name},
                           "fact": None if absent else {"value": "100"},
                           "attempts": [{"source": "SEC", "status": "missing"}] if absent else []})
        sec["companies"].append({"symbol": symbol, "issuer_id": cik,
                                 "fields": fields,
                                 "financial_assessment": {
                                     "quantitative_gate": "unresolved" if symbol == "AMZN" else "no_screen_trigger",
                                     "unresolved_checks": ["balance_deficit"] if symbol == "AMZN" else []}})
        val["companies"].append({
            "symbol": symbol, "issuer_id": cik,
            "share_check": {"status": "missing_disclosed_shares" if symbol == "GOOGL" else
                                      "verified_dated_share_class"}})
    return sec, val, plan


class SourceGapTests(unittest.TestCase):
    def test_missing_fields_and_review_explanations(self):
        report = analyze(*inputs())
        by = {c["symbol"]: c for c in report["companies"]}
        self.assertEqual(report["source_network_requests"], 0)
        self.assertEqual(report["with_missing_required_gaap"], 3)
        self.assertEqual(report["requires_manual_share_class_review"], 1)
        self.assertEqual({v["field"] for v in by["NVDA"]["missing_required_facts"]},
                         {"revenue", "capital_expenditure"})
        self.assertIn("financial_risk_assessment", by["AMZN"]["gaps"])
        self.assertIn("dated_exact_share_class", by["GOOGL"]["gaps"])
        self.assertIn("GOOGL", markdown(report))
        self.assertFalse(report["investment_approved"])
        self.assertFalse(by["GOOGL"]["eligible_for_trade"])

    def test_cross_issuer_sec_evidence_rejected(self):
        a, b, c = inputs()
        a["companies"][1]["issuer_id"] = "0000320193"
        with self.assertRaisesRegex(ValueError, "cross-issuer"):
            analyze(a, b, c)

    def test_duplicate_score_plan_rejected(self):
        a, b, c = inputs()
        c["excluded"].append(dict(c["excluded"][0]))
        with self.assertRaisesRegex(ValueError, "duplicate"):
            analyze(a, b, c)

    def test_unknown_fields_are_not_substituted(self):
        a, b, c = inputs()
        a["companies"][2]["fields"].append({
            "query": {"field": "bogus_alias"}, "fact": {"value": "999"}})
        with self.assertRaisesRegex(ValueError, "unregistered"):
            analyze(a, b, c)

    def test_missing_attempts_do_not_claim_sources(self):
        a, b, c = inputs()
        a["companies"][2]["fields"][1]["attempts"] = [
            {"source": "SEC", "status": "missing", "detail": "SECRET"},
            {"source": "wrong_host", "status": "collected"}]
        report = analyze(a, b, c)
        text = str(report)
        self.assertNotIn("SECRET", text)
        self.assertNotIn("wrong_host", text)


if __name__ == "__main__":
    unittest.main()
