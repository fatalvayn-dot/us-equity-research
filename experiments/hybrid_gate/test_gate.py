"""Offline regression checks for the hybrid discovery and Sharia compliance gate."""
import unittest
from types import SimpleNamespace

from experiments.hybrid_gate.run import merge_discovery, map_symbol, screen_snapshot, provisional_score

FACTS = {"market_cap": 100, "total_debt": 10, "cash": 4,
         "short_investments": 2, "receivables": 5, "revenue": 200,
         "interest_income": 1}

def engine(f):
    ratios = (f.total_debt/f.market_cap,
              (f.cash_and_equivalents+f.short_term_investments)/f.market_cap,
              f.accounts_receivable/f.market_cap, f.interest_income/f.total_revenue)
    return SimpleNamespace(is_compliant=all(a < b for a,b in zip(ratios,(.33,.33,.49,.05))),
                           standard="opensource-test-convention")

class TestGate(unittest.TestCase):
    def test_missing_not_zero(self):
        bad=dict(FACTS);bad["interest_income"]=None
        result=screen_snapshot(bad,"Technology","Software",engine)
        self.assertEqual(result["status"],"belirsiz")
        self.assertIn("interest_income",result["missing"])

    def test_no_bank_or_insurance(self):
        for industry in ("Regional Banks","Insurance Brokers"):
            self.assertEqual(screen_snapshot(FACTS,"Financials",industry,engine)["status"],"uygunsuz")

    def test_pass_only_complete(self):
        self.assertEqual(screen_snapshot(FACTS,"Technology","Software",engine)["status"],"kosullu_gecti")

    def test_debt_fail(self):
        bad=dict(FACTS);bad["total_debt"]=50
        self.assertEqual(screen_snapshot(bad,"Technology","Software",engine)["status"],"uygunsuz")

    def test_invalid_denominator(self):
        bad=dict(FACTS);bad["market_cap"]=0
        self.assertEqual(screen_snapshot(bad,"Technology","Software",engine)["status"],"belirsiz")

    def test_google_to_yahoo_market_symbol(self):
        self.assertEqual(map_symbol({"symbol":"ASELS:IST"})["yahoo_symbol"],"ASELS.IS")
        self.assertEqual(map_symbol({"symbol":"SAP:ETR"})["yahoo_symbol"],"SAP.DE")

    def test_dedupe(self):
        left=[{"yahoo_symbol":"SAP.DE","source":"google_finance"}]
        right=[{"yahoo_symbol":"SAP.DE","source":"yfinance"}]
        found=merge_discovery(left,right)
        self.assertEqual(len(found),1)
        self.assertEqual(found[0]["source"],"google_finance+yfinance")

    def test_scoring_not_assumed(self):
        self.assertIsNone(provisional_score({},None))
        self.assertIsInstance(provisional_score({"trailingPE":12},0.3),float)

if __name__=="__main__":
    unittest.main()
