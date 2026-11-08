"""Bounded valuation GET work must rotate fairly without changing report order."""
import json
import tempfile
import unittest
from dataclasses import replace
from datetime import timedelta
from pathlib import Path

from equity_research.batch import BatchStore
from equity_research.companyfacts import companyfacts_url
from equity_research.response_archive import ResponseArchive
from equity_research.valuation_collection import ValuationSourceCollector
from test_scoring import ASOF
from test_valuation import cf, identity, meta
from test_valuation_collection import Transport


MSFT='0000789019'
PLAN=dict(companies=[
    dict(symbol='AAPL',issuer_id='0000320193'),
    dict(symbol='MSFT',issuer_id=MSFT),
])


class FairValuationCursorTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        root=Path(self.tmp.name)
        self.archive=ResponseArchive(root/'responses.sqlite')
        self.lock=BatchStore(root/'checkpoint.sqlite')
        self.owner=self.lock.acquire(ASOF,timedelta(minutes=15))
        directory=identity()
        p=json.loads(directory.body)
        p['data'].append([789019,'Synthetic Microsoft','MSFT','Nasdaq'])
        directory=replace(directory,body=json.dumps(p).encode())
        first=cf()
        other=json.loads(first.body);other['cik']=789019
        second=replace(first,url=companyfacts_url(MSFT),body=json.dumps(other).encode())
        third=meta()
        self.transport=Transport({directory.url:directory,first.url:first,second.url:second,third.url:third})
    def tearDown(self):
        self.lock.release(self.owner);self.lock.close();self.archive.close();self.tmp.cleanup()
    def collector(self,budget):
        return ValuationSourceCollector(self.archive,{host:self.transport for host in
            ('www.sec.gov','data.sec.gov','query1.finance.yahoo.com')},
            max_new_requests=budget,checkpoint=self.lock,owner=self.owner,clock=lambda:ASOF)

    def test_request_budget_rotates_without_permuting_reports(self):
        one=self.collector(2).collect(PLAN)
        self.assertEqual(one['summary']['new_get_invocations'],2)
        self.assertEqual([c['symbol'] for c in one['companies']],['AAPL','MSFT'])
        self.assertEqual(self.lock.read('valuation-candidate-cursor-v1')['next_index'],1)
        requested_before=len(self.transport.calls)
        two=self.collector(1).collect(PLAN)
        self.assertEqual([c['symbol'] for c in two['companies']],['AAPL','MSFT'])
        self.assertEqual(two['summary']['new_get_invocations'],1)
        self.assertEqual(self.transport.calls[requested_before],companyfacts_url(MSFT))
        self.assertEqual(self.lock.read('valuation-candidate-cursor-v1')['next_index'],0)
        self.assertFalse(two['mvp_accepted'])
        self.assertTrue(all(c['total_score'] is None for c in two['companies']))

    def test_zero_budget_never_advances_checkpoint(self):
        self.collector(2).collect(PLAN)
        before=self.lock.read('valuation-candidate-cursor-v1')
        response_count=len(self.transport.calls)
        replay=self.collector(0).collect(PLAN)
        self.assertEqual(self.lock.read('valuation-candidate-cursor-v1'),before)
        self.assertEqual(len(self.transport.calls),response_count)
        self.assertEqual(replay['summary']['new_get_invocations'],0)

    def test_changed_candidate_order_invalidates_old_cursor(self):
        self.collector(2).collect(PLAN)
        changed=dict(companies=list(reversed(PLAN['companies'])))
        before=len(self.transport.calls)
        result=self.collector(1).collect(changed)
        self.assertEqual(self.transport.calls[before],companyfacts_url(MSFT))
        self.assertEqual([c['symbol'] for c in result['companies']],['MSFT','AAPL'])

    def test_corrupt_cursor_checksum_starts_from_head_safely(self):
        self.collector(2).collect(PLAN)
        with self.lock.db:
            self.lock.db.execute(
                "UPDATE batch_fields_v1 SET checksum=? WHERE key=?",
                ('bad', 'valuation-candidate-cursor-v1'))
        before=len(self.transport.calls)
        self.collector(1).collect(PLAN)
        # Cached AAPL Companyfacts makes its next request the missing metadata.
        self.assertEqual(self.transport.calls[before],
            'https://data.sec.gov/submissions/CIK0000320193.json')


if __name__=='__main__':
    unittest.main()
