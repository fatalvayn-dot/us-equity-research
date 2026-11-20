import unittest
from unittest.mock import patch
from experiments.hybrid_gate.full_bist import normalize_yahoo,discover_yahoo
class TestFullBist(unittest.TestCase):
    def test_bist_equities_only(self):
        self.assertEqual(normalize_yahoo({"symbol":"ASELS.IS","exchange":"IST","quoteType":"EQUITY"})["symbol"],"ASELS.IS")
        self.assertIsNone(normalize_yahoo({"symbol":"ASELS.IS","exchange":"IST","quoteType":"ETF"}))
        self.assertIsNone(normalize_yahoo({"symbol":"AAPL","exchange":"NMS","quoteType":"EQUITY"}))
        self.assertIsNone(normalize_yahoo({"symbol":"ASELS.IS","exchange":"IST","quoteType":"UNKNOWN"}))
    @patch("yfinance.screen")
    def test_pagination(self,screen):
        screen.side_effect=[
          {"total":3,"quotes":[{"symbol":"ASELS.IS","exchange":"IST","quoteType":"EQUITY"},
                                {"symbol":"BANK.IS","exchange":"IST","quoteType":"EQUITY"}]},
          {"total":3,"quotes":[{"symbol":"BIMAS.IS","exchange":"IST","quoteType":"EQUITY"}]}]
        vals,summary=discover_yahoo(page_size=2,max_pages=3)
        self.assertEqual(len(vals),3)
        self.assertTrue(summary["pagination_exhausted"])
        self.assertEqual(screen.call_count,2)
    @patch("yfinance.screen")
    def test_incomplete_cannot_claim_exhaustive(self,screen):
        screen.side_effect=[{"total":100,"quotes":[{"symbol":"ASELS.IS","exchange":"IST","quoteType":"EQUITY"}]*2}]
        _,summary=discover_yahoo(page_size=2,max_pages=1)
        self.assertFalse(summary["pagination_exhausted"])
if __name__=="__main__":unittest.main()
