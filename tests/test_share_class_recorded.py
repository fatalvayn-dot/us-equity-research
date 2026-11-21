"""Recorded 5 November share-class proof; not full-100 acceptance."""
import json
import tempfile
import unittest
from datetime import datetime,timedelta
from pathlib import Path

from equity_research.batch import BatchStore
from equity_research.cache import encode
from equity_research.evidence_bundle import read_bundle
from equity_research.response_archive import ResponseArchive
from equity_research.valuation_collection import ValuationSourceCollector

ROOT=Path(__file__).resolve().parents[1]


class NoTransport:
    def __init__(self):self.calls=[]
    def get(self,url):
        self.calls.append(url);raise AssertionError('recorded replay must not use network')


class RecordedShareClassTests(unittest.TestCase):
    def test_orcl_and_mchp_common_counts_reconcile_without_ticker_guessing(self):
        expected=json.loads((ROOT/'docs/evidence/share-class2/resume.json').read_text())
        plan=json.loads((ROOT/'docs/evidence/share-class2/candidates.json').read_text())
        with tempfile.TemporaryDirectory() as folder:
            archive=ResponseArchive(Path(folder)/'sources.sqlite');lock=BatchStore(Path(folder)/'lock.sqlite')
            try:
                observations=list(read_bundle(ROOT/'tests/fixtures/share-class2-sources'))
                self.assertEqual(len(observations),11)
                for response in observations:archive.record(response)
                now=datetime.fromisoformat(expected['as_of']);owner=lock.acquire(now,timedelta(minutes=15))
                transport=NoTransport();collector=ValuationSourceCollector(archive,
                    {host:transport for host in ('www.sec.gov','data.sec.gov','query1.finance.yahoo.com')},
                    max_new_requests=0,checkpoint=lock,owner=owner,clock=lambda:now)
                actual=collector.collect(plan)
                self.assertEqual(actual['summary'],expected['summary']);self.assertEqual(transport.calls,[])
                for got,want in zip(actual['companies'],expected['companies']):
                    self.assertEqual(got['identity_status'],want['identity_status'])
                    for leg in ('share_check','price_check','history_check'):
                        self.assertEqual(json.loads(json.dumps(got[leg],default=encode)),want[leg])
                    self.assertFalse(got['scope_approved']);self.assertFalse(got['investment_approved'])
                    self.assertIsNone(got['total_score'])
                by_symbol={row['symbol']:row['share_check']['evidence'] for row in actual['companies']}
                oracle=by_symbol['ORCL']['other_registered_securities'][0]
                self.assertEqual((oracle['symbol'],oracle['cover_symbol']),('ORCL-PD','ORCL PRD'))
                self.assertEqual(oracle['symbol_corroboration'],'single_unambiguous_non_common_cover_alias')
                microchip=by_symbol['MCHP']['other_registered_securities'][0]
                self.assertEqual(microchip['symbol'],'MCHPP')
                self.assertEqual(microchip['symbol_corroboration'],'exact_cover_symbol')
            finally:
                if 'owner' in locals():lock.release(owner)
                lock.close();archive.close()
