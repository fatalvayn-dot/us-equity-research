"""Only an unselected *older* SEC share chronology defect may be quarantined."""
import json
import unittest
from datetime import date

from equity_research.providers import ProviderFailure
from equity_research.valuation import disclosed_shares
from test_valuation import CIK, NOW, cf, response
from equity_research.companyfacts import companyfacts_url


class HistoricalShareChronologyTests(unittest.TestCase):
    def check(self, rows):
        raw=json.loads(cf().body)
        raw['facts']['dei']['EntityCommonStockSharesOutstanding']['units']['shares']=rows
        return disclosed_shares(response(companyfacts_url(CIK),raw),cik=CIK,as_of=NOW)

    def test_selected_valid_latest_with_older_inverted_filing_dates(self):
        newest=json.loads(cf().body)['facts']['dei']['EntityCommonStockSharesOutstanding']['units']['shares'][0]
        old=dict(newest,end='2021-09-30',filed='2021-08-01',
                 accn='0000320193-21-000001',val=90)
        out=self.check([old,newest])
        self.assertEqual(out['value'],100)
        self.assertEqual(out['end'].isoformat(),'2026-10-20')
        self.assertEqual(out['historical_numeric_review'],[
            dict(end=date(2021,9,30),
                 filed=date(2021,8,1),
                 accession='0000320193-21-000001',
                 status='unselected_historical_date_order_invalid')])
        self.assertNotIn('chronology_valid',out)

    def test_latest_inverted_chronology_never_falls_back(self):
        current=json.loads(cf().body)['facts']['dei']['EntityCommonStockSharesOutstanding']['units']['shares'][0]
        latest=dict(current,end='2026-10-31',filed='2026-10-30',
                    accn='0000320193-26-000021')
        with self.assertRaises(ProviderFailure):
            self.check([current,latest])

    def test_malformed_accession_still_rejects_even_old(self):
        current=json.loads(cf().body)['facts']['dei']['EntityCommonStockSharesOutstanding']['units']['shares'][0]
        old=dict(current,end='2021-09-30',filed='2021-08-01',accn='bad')
        with self.assertRaises(ProviderFailure):
            self.check([current,old])

    def test_future_filing_still_rejects_even_historical_end(self):
        current=json.loads(cf().body)['facts']['dei']['EntityCommonStockSharesOutstanding']['units']['shares'][0]
        old=dict(current,end='2021-09-30',filed='2026-11-04',
                 accn='0000320193-26-000022')
        with self.assertRaises(ProviderFailure):
            self.check([current,old])

    def test_bad_numeric_latest_still_rejected(self):
        current=json.loads(cf(val=133.9).body)['facts']['dei']['EntityCommonStockSharesOutstanding']['units']['shares'][0]
        old=dict(current,end='2021-09-30',filed='2021-08-01',
                 accn='0000320193-21-000001',val=99)
        with self.assertRaises(ProviderFailure):
            self.check([old,current])

    def test_equal_end_and_filing_conflicting_counts_still_rejected(self):
        current=json.loads(cf().body)['facts']['dei']['EntityCommonStockSharesOutstanding']['units']['shares'][0]
        conflict=dict(current,val=99)
        with self.assertRaises(ProviderFailure):
            self.check([current,conflict])


if __name__=='__main__':
    unittest.main()
