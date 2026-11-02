"""Synthetic listing gates; live response acceptance is recorded separately."""
import unittest
from dataclasses import replace
from datetime import timedelta

from equity_research.nasdaq import DIRECTORY_ENDPOINTS,NasdaqDirectories,parse_directory
from equity_research.providers import ProviderFailure,Status
from equity_research.scope import audit_sample
from test_nasdaq import NOW,data,response,snapshots,identity
from test_sec_transport import Opener,FakeResponse,DIRECTORY_URL,Clock
from equity_research.transport import HttpTransport,Response

SAMPLE=[dict(symbol='AAPL',issuer_id='0000320193'),dict(symbol='IBM',issuer_id='0000051143')]

class ScopeTests(unittest.TestCase):
    def test_valid_listing_still_pending_legal_type(self):
        r=audit_sample(SAMPLE,snapshots(),identity(),as_of=NOW)
        self.assertEqual(r['summary']['states'],{'listing_evidence_complete_legal_type_pending':2})
        self.assertEqual(r['summary']['approved'],0)
        self.assertFalse(r['active_universe_accepted'])
        row=r['companies'][0]['evidence'][0]
        self.assertEqual(row['raw_sha256'],snapshots()[0].raw_sha256)
        self.assertEqual(row['listing']['etf'],'N')
        self.assertEqual(row['matched_issuer_id'],SAMPLE[0]['issuer_id'])

    def test_wrong_sample_cik_quarantined(self):
        sample=[dict(symbol='AAPL',issuer_id='0000000001')]
        r=audit_sample(sample,snapshots(),identity(),as_of=NOW)
        self.assertEqual(r['companies'][0]['scope_status'],'pending_scope')
        self.assertIn('cik_disagrees',r['companies'][0]['scope_reason'])

    def test_missing_and_ambiguous_aliases(self):
        r=audit_sample([dict(symbol='BRK.B',issuer_id='0001067983')],snapshots(),identity(),as_of=NOW)
        self.assertEqual(r['companies'][0]['scope_reason'],'no_exact_listing_alias')
        parts=(snapshots()[0],parse_directory(response('otherlisted',[data('otherlisted',**{'ACT Symbol':'AAPL','CQS Symbol':'AAPL','NASDAQ Symbol':'AAPL'})]),'otherlisted'))
        r=audit_sample(SAMPLE,parts,identity(),as_of=NOW)
        self.assertEqual(r['companies'][0]['scope_reason'],'ambiguous_listing_alias')

    def test_etf_test_and_other_exchange_excluded(self):
        for changes in ({'ETF':'Y'},{'Test Issue':'Y'}):
            parts=(parse_directory(response(rows=[data(**changes)]),'nasdaqlisted'),snapshots()[1])
            r=audit_sample(SAMPLE,parts,identity(),as_of=NOW)
            self.assertEqual(r['companies'][0]['scope_status'],'out_of_scope')
        parts=(snapshots()[0],parse_directory(response('otherlisted',[data('otherlisted',Exchange='P')]),'otherlisted'))
        self.assertEqual(audit_sample(SAMPLE,parts,identity(),as_of=NOW)['companies'][1]['scope_status'],'out_of_scope')

    def test_fund_in_issuer_name_never_classified_common(self):
        parts=(parse_directory(response(rows=[data(**{'Security Name':'Example Income Fund - Common Stock'})]),'nasdaqlisted'),snapshots()[1])
        r=audit_sample(SAMPLE,parts,identity(),as_of=NOW)
        self.assertEqual(r['companies'][0]['scope_status'],'pending_scope')
        self.assertEqual(r['companies'][0]['scope_reason'],'fund_word_requires_legal_type_check')

    def test_stale_identity_rejected_and_stale_listing_pending(self):
        with self.assertRaises(ValueError):audit_sample(SAMPLE,snapshots(),replace(identity(),retrieved_at=NOW-timedelta(days=5)),as_of=NOW)
        parts=(replace(snapshots()[0],retrieved_at=NOW-timedelta(days=5)),snapshots()[1])
        r=audit_sample(SAMPLE,parts,identity(),as_of=NOW)
        self.assertEqual(r['companies'][0]['scope_status'],'pending_scope')

    def test_bad_or_duplicate_sample_rejected(self):
        for sample in ([SAMPLE[0],SAMPLE[0]],[dict(symbol='AAPL',issuer_id='1')],[],[{}]):
            with self.assertRaises(ValueError):audit_sample(sample,snapshots(),identity(),as_of=NOW)

    def test_primary_success_never_queries_alternate(self):
        class Transport:
            calls=[]
            def get(self,url):
                self.calls.append(url)
                name='nasdaqlisted' if 'nasdaqlisted' in url else 'otherlisted'
                return response(name)
        t=Transport();adapter=NasdaqDirectories(t);result=adapter.fetch()
        self.assertEqual(len(result),2);self.assertEqual(len(t.calls),2)
        self.assertEqual([r['status'] for r in adapter.attempts],['valid','valid'])

    def test_primary_error_falls_back_preserving_actual_url(self):
        class Transport:
            def get(self,url):
                if 'ftp.' in url:raise ProviderFailure(Status.API_ERROR,http_status=503)
                name='nasdaqlisted' if 'nasdaqlisted' in url else 'otherlisted'
                return replace(response(name),url=url)
        adapter=NasdaqDirectories(Transport());result=adapter.fetch()
        self.assertEqual([r['status'] for r in adapter.attempts],['api_error','valid','api_error','valid'])
        self.assertEqual(result[0].source_url,DIRECTORY_ENDPOINTS['nasdaqlisted'][1])

    def test_invalid_primary_payload_can_use_valid_official_alternate(self):
        class Transport:
            def get(self,url):
                name='nasdaqlisted' if 'nasdaqlisted' in url else 'otherlisted'
                return Response(url,b'<html>bad</html>',NOW) if 'ftp.' in url else replace(response(name),url=url)
        adapter=NasdaqDirectories(Transport());self.assertEqual(len(adapter.fetch()),2)
        self.assertEqual(adapter.attempts[0]['status'],'invalid_data')

    def test_unapproved_directory_origin_rejected(self):
        with self.assertRaises(ProviderFailure):parse_directory(replace(response(),url='https://evil.example/nasdaqlisted.txt'),'nasdaqlisted')

    def test_explicit_accept_header_and_injection_rejected(self):
        for accept in ('application/json','text/plain','text/html'):
            opener=Opener(FakeResponse());clock=Clock()
            h=HttpTransport(user_agent='test',allowed_hosts={'www.sec.gov'},accept=accept,opener=opener,
                monotonic=clock.monotonic,sleep=clock.sleep)
            h.get(DIRECTORY_URL)
            self.assertEqual(opener.calls[0][0].get_header('Accept'),accept)
        with self.assertRaises(ValueError):HttpTransport(user_agent='test',allowed_hosts={'www.sec.gov'},accept='text/plain\r\nX-Injected: yes')

    def test_observed_legacy_otherlisted_footer_only_empty_tail(self):
        r=response('otherlisted');body=r.body.rstrip(b'\n')[:-1]+b'\n'
        parsed=parse_directory(replace(r,body=body),'otherlisted')
        self.assertEqual(len(parsed.rows),1)
        for bad in (body.rstrip(b'\n')[:-1]+b'\n',body.replace(b'||||||\n',b'|||||x\n')):
            with self.assertRaises(ProviderFailure):parse_directory(replace(r,body=bad),'otherlisted')
        # Nasdaq-listed footer cannot use the other-listed legacy variant.
        r=response()
        with self.assertRaises(ProviderFailure):parse_directory(replace(r,body=r.body.rstrip(b'\n')[:-1]+b'\n'),'nasdaqlisted')

    def test_stale_exclusion_is_not_a_current_scope_decision(self):
        s=parse_directory(response(rows=[data(ETF='Y')]),'nasdaqlisted')
        s=replace(s,retrieved_at=NOW-timedelta(days=5))
        r=audit_sample(SAMPLE,(s,snapshots()[1]),identity(),as_of=NOW)
        self.assertEqual(r['companies'][0]['scope_status'],'pending_scope')
        self.assertEqual(r['companies'][0]['scope_reason'],'stale_or_future_source')

class RecordedPrimaryTests(unittest.TestCase):
    def load(self):
        import gzip,json
        from pathlib import Path
        from datetime import datetime
        from equity_research.sec import parse_directory as parse_sec
        root=Path(__file__).resolve().parents[1]
        meta=json.loads((root/'docs/evidence/scope-primary-snapshots.json').read_text())
        snapshots=[];identity_snapshot=None
        for row in meta['sources']:
            r=Response(row['url'],gzip.decompress((root/row['fixture']).read_bytes()),datetime.fromisoformat(row['retrieved_at']))
            self.assertEqual(r.sha256,row['sha256'])
            if r.url==DIRECTORY_URL:identity_snapshot=parse_sec(r)
            else:snapshots.append(parse_directory(r,'nasdaqlisted' if 'nasdaqlisted' in r.url else 'otherlisted'))
        return root,meta,tuple(snapshots),identity_snapshot

    def test_full_recorded_partition_no_rows_lost(self):
        from datetime import datetime
        from equity_research.nasdaq import build_universe
        root,meta,parts,ident=self.load()
        rows=build_universe(parts,ident,as_of=datetime.fromisoformat(meta['observed_at']))
        self.assertEqual(sum(len(s.rows) for s in parts),13286)
        self.assertEqual(len(rows),13286)
        self.assertEqual(len({(r.source_url,r.listing.symbol) for r in rows}),13286)

    def test_recorded_100_exact_identities_are_not_legal_type_approval(self):
        import json
        from datetime import datetime
        root,meta,parts,ident=self.load()
        sample=json.loads((root/'docs/evidence/sample100-audit-queue.json').read_text())['companies']
        r=audit_sample(sample,parts,ident,as_of=datetime.fromisoformat(meta['observed_at']))
        self.assertEqual(r['summary']['states'],{'listing_evidence_complete_legal_type_pending':100})
        self.assertEqual(r['summary']['approved'],0)
        self.assertTrue(all(c['evidence'][0]['matched_issuer_id']==c['issuer_id'] for c in r['companies']))
