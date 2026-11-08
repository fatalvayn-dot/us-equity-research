"""Deterministic collector acquisition, interruption and archive/cooldown contracts."""
import copy
import json
import os
import subprocess
import sys
import tempfile
import unittest
from dataclasses import replace
from datetime import datetime, timedelta
from pathlib import Path

from equity_research.batch import BatchStore, RunBusy
from equity_research.evidence_bundle import read_bundle
from equity_research.market_history import history_url
from equity_research.prices import price_url
from equity_research.providers import ProviderFailure, Status
from equity_research.response_archive import ResponseArchive
from equity_research.sec import DIRECTORY_URL
from equity_research.valuation_collection import ValuationSourceCollector, run_collection, candidate_rows
from test_scoring import history, ASOF
from test_valuation import CIK, NOW, cf, meta, filing, filing_with_other_security, identity, price

ROOT=Path(__file__).resolve().parents[1]
PLAN=dict(companies=[dict(symbol='AAPL',issuer_id=CIK)])


class Transport:
    def __init__(self, responses):self.responses=responses;self.calls=[]
    def get(self,url):
        self.calls.append(url)
        result=self.responses[url]
        if isinstance(result,Exception):raise result
        return result


class CollectionTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.path=Path(self.temp.name)
        self.archive=ResponseArchive(self.path/'source.sqlite');self.lock=BatchStore(self.path/'lock.sqlite')
        self.now=ASOF;self.owner=self.lock.acquire(self.now,timedelta(minutes=15))
        self.responses={r.url:r for r in (identity(),cf(),meta(),filing(),price(),history())}
        self.transport=Transport(self.responses)
    def tearDown(self):
        self.lock.release(self.owner);self.lock.close();self.archive.close();self.temp.cleanup()
    def collector(self,limit=6):
        return ValuationSourceCollector(self.archive,{h:self.transport for h in
            ('www.sec.gov','data.sec.gov','query1.finance.yahoo.com')},max_new_requests=limit,
            checkpoint=self.lock,owner=self.owner,clock=lambda:self.now)
    def test_complete_sources_then_zero_request_resume_preserves_original_evidence(self):
        initial=self.collector().collect(PLAN)
        self.assertEqual(initial['summary']['new_get_invocations'],6)
        company=initial['companies'][0]
        self.assertEqual(company['share_check']['status'],'verified_dated_share_class')
        self.assertEqual(company['price_check']['status'],'valid');self.assertEqual(company['history_check']['status'],'valid')
        replay=self.collector(0).collect(PLAN)
        self.assertEqual(replay['summary']['new_get_invocations'],0)
        for leg in ('share_check','price_check','history_check'):self.assertEqual(company[leg],replay['companies'][0][leg])
        self.assertFalse(initial['mvp_accepted']);self.assertFalse(company['scope_approved']);self.assertIsNone(company['total_score'])
    def test_partial_budget_resumes_without_repeating_successful_requests(self):
        first=self.collector(2).collect(PLAN)
        self.assertEqual(first['summary']['new_get_invocations'],2)
        self.assertEqual(first['companies'][0]['share_check']['status'],'pending_source_collection')
        replay=self.collector(4).collect(PLAN)
        self.assertEqual(replay['summary']['new_get_invocations'],4)
        self.assertEqual(replay['companies'][0]['share_check']['status'],'verified_dated_share_class')
        self.assertEqual(len(self.transport.calls),6)
    def test_zero_budget_does_not_fetch_identity_or_claim_attempts(self):
        r=self.collector(0).collect(PLAN)
        self.assertEqual(self.transport.calls,[]);self.assertEqual(r['summary']['new_get_invocations'],0)
        self.assertEqual(r['identity_attempts'][0]['status'],'not_started')
        self.assertEqual(r['companies'][0]['attempts'],[])
    def test_invalid_identity_body_is_not_reported_as_verified(self):
        r=identity();self.transport.responses[r.url]=replace(r,body=b'{"wrong":"schema"}')
        report=self.collector().collect(PLAN)
        self.assertEqual(report['identity_attempts'][0]['status'],'body_available')
        self.assertEqual(report['identity_validation']['status'],'invalid_data')
        self.assertEqual(report['companies'][0]['identity_status'],'identity_unavailable')
        self.assertEqual(self.transport.calls,[DIRECTORY_URL])

    def test_non_us_listing_is_rejected_before_company_specific_requests(self):
        r=identity();payload=json.loads(r.body);payload['data'][0][3]='OTC'
        self.transport.responses[r.url]=replace(r,body=json.dumps(payload).encode())
        row=self.collector().collect(PLAN)['companies'][0]
        self.assertEqual(row['identity_status'],'out_of_scope_exchange')
        self.assertEqual(self.transport.calls,[DIRECTORY_URL])

    def test_failure_cooldown_expires_and_safe_retry_collects_the_price(self):
        self.transport.responses[price_url('AAPL')]=ProviderFailure(Status.RATE_LIMIT,http_status=429)
        self.collector().collect(PLAN);self.now+=timedelta(minutes=6)
        self.transport.responses[price_url('AAPL')]=price()
        r=self.collector(1).collect(PLAN)
        self.assertEqual(r['summary']['new_get_invocations'],1)
        self.assertEqual(r['companies'][0]['price_check']['status'],'valid')

    def test_wrong_directory_cik_blocks_every_company_specific_request(self):
        plan=copy.deepcopy(PLAN);plan['companies'][0]['issuer_id']='0000000001'
        row=self.collector().collect(plan)['companies'][0]
        self.assertEqual(row['identity_status'],'symbol_mismatch');self.assertEqual(self.transport.calls,[DIRECTORY_URL])
    def test_provider_failures_are_distinct_persisted_and_not_requeried_on_resume(self):
        for status in (Status.RATE_LIMIT,Status.ACCESS_DENIED,Status.TIMEOUT):
            with self.subTest(status=status):
                self.transport.responses[price_url('AAPL')]=ProviderFailure(status,http_status=429 if status==Status.RATE_LIMIT else None)
                # Reset only this test's failure checkpoint between independent cases.
                with self.lock.db:self.lock.db.execute('DELETE FROM batch_fields_v1')
                r=self.collector().collect(PLAN)
                attempt=next(a for a in r['companies'][0]['attempts'] if a['stage']=='price')
                self.assertEqual(attempt['status'],status.value);self.assertTrue(attempt['http_requested'])
                count=len(self.transport.calls);again=self.collector().collect(PLAN)
                attempt=next(a for a in again['companies'][0]['attempts'] if a['stage']=='price')
                self.assertFalse(attempt['http_requested']);self.assertEqual(attempt['deferred_reason'],'retry_cooldown')
                self.assertEqual(count,len(self.transport.calls))
    def test_bad_original_count_rejects_share_reconciliation_without_zero_fill(self):
        r=filing(value='999');self.transport.responses[r.url]=r
        company=self.collector().collect(PLAN)['companies'][0]
        self.assertEqual(company['share_check']['status'],'invalid_data');self.assertIsNone(company['total_score'])
        self.assertEqual(company['price_check']['status'],'valid')
        self.assertEqual(company['history_check'], dict(status='not_started', deferred_reason='share_class_unverified'))
        self.assertNotIn(history_url('AAPL'), self.transport.calls)

    def test_history_is_deferred_when_original_filing_exhausts_request_budget(self):
        self.archive.record(price())
        report = self.collector(3).collect(PLAN)
        company = report['companies'][0]
        self.assertEqual(company['share_check']['status'], 'pending_source_collection')
        self.assertEqual(company['price_check']['status'], 'valid')
        self.assertEqual(company['history_check'], dict(status='not_started', deferred_reason='share_class_unverified'))
        self.assertNotIn(history_url('AAPL'), self.transport.calls)

    def test_metadata_symbol_conflict_does_not_fetch_original_filing(self):
        r=meta(tickers=['MSFT']);self.transport.responses[r.url]=r
        company=self.collector().collect(PLAN)['companies'][0]
        self.assertEqual(company['share_check']['status'],'symbol_mismatch')
        self.assertNotIn(filing().url,self.transport.calls)
    def test_extra_preferred_ticker_needs_and_accepts_exact_filing_cover_proof(self):
        r=meta(tickers=['AAPL','AAPL-P']);self.transport.responses[r.url]=r
        document=filing_with_other_security();self.transport.responses[document.url]=document
        company=self.collector().collect(PLAN)['companies'][0]
        self.assertEqual(company['share_check']['status'],'verified_dated_share_class')
        proof=company['share_check']['evidence']
        self.assertEqual(proof['other_registered_securities'][0]['symbol'],'AAPL-P')
        self.assertFalse(company['scope_approved']);self.assertIsNone(company['total_score'])
    def test_stale_cached_market_inputs_require_refresh_and_budget_remains_hard(self):
        self.collector().collect(PLAN);self.now+=timedelta(minutes=16)
        self.lock.release(self.owner);self.owner=self.lock.acquire(self.now,timedelta(minutes=15))
        r=self.collector(0).collect(PLAN)
        self.assertEqual(r['summary']['new_get_invocations'],0)
        self.assertEqual(r['companies'][0]['share_check']['status'],'verified_dated_share_class')
        self.assertEqual(r['companies'][0]['price_check']['status'],'pending_source_collection')
    def test_invalid_duplicate_oversize_and_punctuation_plans_fail_before_http(self):
        for plan in ({'companies':[]},{'companies':PLAN['companies']*2},
                {'companies':[dict(symbol='aapl',issuer_id=CIK)]},{'companies':PLAN['companies']*101}):
            with self.subTest(plan=plan),self.assertRaises((ValueError,KeyError,TypeError)):self.collector().collect(plan)
        self.assertEqual(self.transport.calls,[])
        for limit in (-1,502,True,1.5):
            with self.subTest(limit=limit),self.assertRaises(ValueError):self.collector(limit)
    def test_current_observation_lease_prevents_overlapping_runner(self):
        path=self.path/'busy';path.mkdir();lock=BatchStore(path/'run-lock.sqlite')
        from datetime import timezone
        owner=lock.acquire(datetime.now(timezone.utc),timedelta(minutes=15))
        try:
            with self.assertRaises(RunBusy):run_collection(PLAN,state_dir=path,user_agent='Research project',max_new_requests=0)
        finally:lock.release(owner);lock.close()
    def test_recorded_three_company_evidence_replays_through_general_collector(self):
        for directory in ('valuation-sources','score-market-sources'):
            for r in read_bundle(ROOT/'tests/fixtures'/directory):self.archive.record(r)
        self.now=datetime.fromisoformat('2026-11-02T21:33:48.135379+00:00')
        plan=dict(companies=[dict(symbol=s,issuer_id=c) for s,c in
            [('AAPL',CIK),('MSFT','0000789019'),('NVDA','0001045810')]])
        # Lease must be renewed consistently with this later replay clock.
        self.lock.release(self.owner);self.owner=self.lock.acquire(self.now,timedelta(minutes=15))
        r=self.collector(0).collect(plan)
        self.assertEqual(r['summary']['new_get_invocations'],0)
        self.assertEqual(r['summary']['share_states'],{'verified_dated_share_class':3})
        self.assertEqual(r['summary']['price_states'],{'valid':3});self.assertEqual(r['summary']['history_states'],{'valid':3})
        self.assertEqual(self.transport.calls,[])
    def test_actual_seven_company_collection_rebuilds_each_leg_from_raw_sources(self):
        import gzip
        evidence=ROOT/'docs/evidence/collection7'
        expected=json.loads(gzip.decompress((evidence/'report.json.gz').read_bytes()))
        proof=json.loads((evidence/'resume-proof.json').read_text())
        self.assertEqual(proof['initial_get_invocations'],32)
        self.assertEqual(proof['resume_get_invocations'],0)
        for response in read_bundle(ROOT/'tests/fixtures/collection7-sources'):
            self.archive.record(response)
        self.now=datetime.fromisoformat(expected['as_of'])
        self.lock.release(self.owner);self.owner=self.lock.acquire(self.now,timedelta(minutes=15))
        actual=self.collector(0).collect(expected['candidate_plan'])
        # The historical artifact remains unchanged. Under the stricter current
        # policy, ORCL is pending its exact preferred-security cover proof instead
        # of being rejected merely because submissions lists a second ticker.
        self.assertEqual(actual['summary']['new_get_invocations'],0)
        self.assertEqual(actual['summary']['share_states'],
            {'verified_dated_share_class':6,'pending_source_collection':1})
        from equity_research.cache import encode
        for got,want in zip(actual['companies'],expected['companies']):
            self.assertEqual(got['symbol'],want['symbol'])
            if got['symbol']=='ORCL':
                self.assertEqual(want['share_check']['status'],'symbol_mismatch')
                self.assertEqual(got['share_check']['status'],'pending_source_collection')
            else:self.assertEqual(json.loads(json.dumps(got['share_check'],default=encode)),want['share_check'])
            self.assertEqual(json.loads(json.dumps(got['price_check'],default=encode)),want['price_check'])
            if got['symbol']=='ORCL':
                self.assertEqual(want['history_check']['status'], 'valid')
                self.assertEqual(got['history_check'], dict(status='not_started', deferred_reason='share_class_unverified'))
                self.assertTrue(any(row['url'] == history_url('ORCL') for row in self.archive.observations()))
            else:
                self.assertEqual(json.loads(json.dumps(got['history_check'],default=encode)),want['history_check'])
            self.assertFalse(got['scope_approved']);self.assertIsNone(got['total_score'])
        self.assertEqual(self.transport.calls,[])

    def test_cli_zero_work_and_input_path_protection(self):
        plan=self.path/'plan.json';plan.write_text(json.dumps(PLAN));state=self.path/'state'
        cmd=[sys.executable,'-m','equity_research','collect-valuation-sources','--candidates',str(plan),
            '--state-dir',str(state),'--user-agent','US Equity Research project','--max-new-requests','0']
        env={**os.environ,'PYTHONPATH':str(ROOT/'src')}
        r=subprocess.run(cmd,capture_output=True,text=True,env=env)
        self.assertEqual(r.returncode,0,r.stdout+r.stderr)
        self.assertEqual(json.loads((state/'report.json').read_text())['summary']['new_get_invocations'],0)
        before=plan.read_bytes();cmd[cmd.index('--state-dir')+1]=str(self.path)
        r=subprocess.run(cmd,capture_output=True,text=True,env=env)
        self.assertEqual(r.returncode,2);self.assertEqual(plan.read_bytes(),before)
        self.assertIn('must be outside',r.stderr)
