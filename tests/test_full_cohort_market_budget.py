"""Cold 100-company collection with the real identity/share/quote/history parsers."""
import json
import tempfile
import unittest
from dataclasses import replace
from datetime import timedelta
from pathlib import Path

from equity_research.batch import BatchStore
from equity_research.response_archive import ResponseArchive
from equity_research.sec import DIRECTORY_URL
from equity_research.valuation_collection import ValuationSourceCollector
from test_scoring import ASOF, history
from test_valuation import cf, filing, identity, meta, price
from test_valuation_collection import Transport


class FullCohortMarketBudgetTests(unittest.TestCase):
    def collect(self,budget):
        rows=[];directory=[];responses={}
        templates=[cf(),meta(),filing(),price(),history()]
        for i in range(100):
            cik=f'{1000000+i:010d}';symbol=f'A{i:03d}'
            rows.append(dict(issuer_id=cik,symbol=symbol))
            directory.append([int(cik),'Synthetic issuer',symbol,'Nasdaq'])
            def substitute(text):
                return text.replace('0000320193',cik).replace('320193',str(int(cik))).replace('AAPL',symbol)
            for r in templates:
                response=replace(r,url=substitute(r.url),body=substitute(r.body.decode()).encode())
                responses[response.url]=response
        response=replace(identity(),body=json.dumps(dict(
            fields=['cik','name','ticker','exchange'],data=directory)).encode())
        responses[DIRECTORY_URL]=response
        transport=Transport(responses)
        with tempfile.TemporaryDirectory() as td:
            archive=ResponseArchive(Path(td)/'sources.sqlite')
            lock=BatchStore(Path(td)/'lock.sqlite')
            owner=lock.acquire(ASOF,timedelta(minutes=15))
            try:
                collector=ValuationSourceCollector(archive,{host:transport for host in
                    ('www.sec.gov','data.sec.gov','query1.finance.yahoo.com')},
                    max_new_requests=budget,checkpoint=lock,owner=owner,clock=lambda:ASOF)
                return collector.collect(dict(companies=rows))
            finally:
                lock.release(owner);lock.close();archive.close()

    def test_full_budget_covers_every_market_leg_without_inventing_approval(self):
        report=self.collect(501)
        self.assertEqual(report['summary']['new_get_invocations'],501)
        self.assertEqual(report['summary']['share_states'],{'verified_dated_share_class':100})
        self.assertEqual(report['summary']['price_states'],{'valid':100})
        self.assertEqual(report['summary']['history_states'],{'valid':100})
        self.assertFalse(report['mvp_accepted'])
        self.assertTrue(all(c['total_score'] is None and not c['investment_approved'] for c in report['companies']))

    def test_old_half_budget_leaves_real_parser_work_pending(self):
        report=self.collect(250)
        self.assertEqual(report['summary']['new_get_invocations'],250)
        self.assertLess(report['summary']['history_states'].get('valid',0),100)
        self.assertGreater(report['summary']['price_states'].get('pending_source_collection',0),0)
