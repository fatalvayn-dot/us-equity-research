"""Only explicit SEC annual periods can enter a live full-score comparison."""
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from equity_research.cache import encode
from equity_research.companyfacts import companyfacts_url
from test_scoring import CIK, companyfacts, financial
from scripts.prepare_first_score_plans import plans


class FirstScorePlansTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.fact = companyfacts()
        self.batch = json.loads(json.dumps(financial(), default=encode))
        for field in self.batch["companies"][0]["fields"]:
            if field["query"]["field"] == "revenue":
                field["fact"]["raw_sha256"] = self.fact.sha256
        self.meta = dict(companies=[dict(issuer_id=CIK, symbol="AAPL",
            status="metadata_available_legal_type_pending",
            snapshot=dict(entity_type_label="operating", sic_label="3571",
                annual_filings=[dict(accession="0000320193-26-000001",
                                     report_end="2025-12-31")]))])
        self.valuation = dict(companies=[dict(issuer_id=CIK, symbol="AAPL",
            identity_status="exact_match",
            share_check=dict(status="verified_dated_share_class"),
            price_check=dict(status="valid"),
            history_check=dict(status="valid"))])
        self.write_cache(self.fact.body)
    def tearDown(self):
        self.temp.cleanup()
    def write_cache(self, body, sha=None):
        (self.root / (CIK + ".json")).write_text(json.dumps(dict(
            url=companyfacts_url(CIK), body=body.decode(),
            retrieved_at=self.fact.retrieved_at.isoformat(),
            sha256=sha or hashlib.sha256(body).hexdigest())))
    def runplan(self, **kwargs):
        return plans(kwargs.get("batch",self.batch),kwargs.get("metadata",self.meta),
            kwargs.get("valuation",self.valuation),self.root,maximum=1)
    def test_real_periods_not_subtraction_are_selected(self):
        current, prior, report=self.runplan()
        self.assertEqual(report["selected"],1)
        self.assertEqual(report["selected_symbols"],["AAPL"])
        self.assertEqual(current["companies"][0]["period_start"],"2025-01-01")
        self.assertEqual(prior["companies"][0]["period_start"],"2024-01-01")
        self.assertEqual(prior["companies"][0]["period_end"],"2024-12-31")
        self.assertEqual(prior["companies"][0]["fields"],["revenue"])
        self.assertFalse(report["full_scores_generated"])
        self.assertFalse(report["mvp_accepted"])
    def test_missing_prior_is_not_filled_or_guessed(self):
        raw=json.loads(self.fact.body)
        rows=raw["facts"]["us-gaap"]["RevenueFromContractWithCustomerExcludingAssessedTax"]["units"]["USD"]
        raw["facts"]["us-gaap"]["RevenueFromContractWithCustomerExcludingAssessedTax"]["units"]["USD"]=[
            r for r in rows if r.get("end")!="2024-12-31"]
        updated=json.dumps(raw).encode()
        self.write_cache(updated)
        for field in self.batch["companies"][0]["fields"]:
            if field["query"]["field"] == "revenue":
                field["fact"]["raw_sha256"] = hashlib.sha256(updated).hexdigest()
        _, prior, report=self.runplan()
        self.assertEqual(report["selected"],0)
        self.assertEqual(prior["companies"],[])
        self.assertIn("explicit_comparable_revenue_missing_or_ambiguous",report["excluded_reasons"])
    def test_wrong_hash_and_unverified_market_never_select(self):
        self.write_cache(self.fact.body,sha="0"*64)
        self.assertEqual(self.runplan()[2]["selected"],0)
        self.write_cache(self.fact.body)
        self.valuation["companies"][0]["share_check"]["status"]="invalid_data"
        self.assertEqual(self.runplan()[2]["selected"],0)
    def test_unsupported_sector_is_not_scored(self):
        self.meta["companies"][0]["snapshot"]["sic_label"]="6021"
        _,_,report=self.runplan()
        self.assertEqual(report["selected"],0)
        self.assertIn("unsupported_sector_or_entity_type",report["excluded_reasons"])


if __name__=="__main__":
    unittest.main()
