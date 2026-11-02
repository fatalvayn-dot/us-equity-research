import gzip
import json
import unittest
import subprocess
import sys
from datetime import datetime,timezone
from pathlib import Path

from equity_research.nasdaq_screener import NasdaqScreener,parse_page,screener_url
from equity_research.providers import FailureReason,ProviderFailure,Status
from equity_research.transport import Response

NOW=datetime(2026,11,1,20,30,tzinfo=timezone.utc)


def page(symbols=('A','B'),total=3,offset=0,label='Last price as of Oct 29, 2026'):
    body={'status':{'rCode':200},'data':{'totalrecords':total,'asof':label,'table':{'rows':[{'symbol':s,'name':s+' Common Stock'} for s in symbols]}}}
    return Response(screener_url(2,offset),json.dumps(body).encode(),NOW)


class Replay:
    def __init__(self,responses):self.responses=list(responses);self.calls=[]
    def get(self,url):
        self.calls.append(url)
        result=self.responses.pop(0)
        if result.url!=url:raise AssertionError('wrong offset')
        return result


class ScreenerTests(unittest.TestCase):
    def test_complete_pagination_preserves_evidence_and_no_active_inference(self):
        transport=Replay([page(),page(('C',),offset=2)])
        snapshot=NasdaqScreener(transport,page_size=2).fetch()
        self.assertEqual([r.symbol for r in snapshot.records],['A','B','C'])
        self.assertEqual(len(snapshot.pages),2)
        self.assertFalse(hasattr(snapshot.records[0],'active'))
        self.assertFalse(hasattr(snapshot.records[0],'exchange'))
        self.assertFalse(hasattr(snapshot.records[0],'security_type'))

    def test_duplicate_changed_total_and_changed_asof_abort(self):
        for last in (page(('A',),offset=2),page(('C',),total=4,offset=2),page(('C',),offset=2,label='changed')):
            with self.subTest(last=last),self.assertRaises(ProviderFailure):
                NasdaqScreener(Replay([page(),last]),page_size=2).fetch()

    def test_max_page_and_record_bounds_prevent_partial_success(self):
        for options in ({'max_pages':1},{'max_records':2}):
            with self.subTest(options=options),self.assertRaises(ProviderFailure):
                NasdaqScreener(Replay([page()]),page_size=2,**options).fetch()

    def test_bad_and_empty_schema_not_empty_universe(self):
        for body in ({},{'status':{'rCode':200},'data':None},
                     {'status':{'rCode':200},'data':{'totalrecords':0,'table':{'rows':[]}}}):
            r=Response(screener_url(2,0),json.dumps(body).encode(),NOW)
            with self.subTest(body=body),self.assertRaises(ProviderFailure):parse_page(r,limit=2,offset=0)

    def test_vendor_access_error_not_missing(self):
        for code,status in ((403,Status.ACCESS_DENIED),(429,Status.RATE_LIMIT),(503,Status.API_ERROR)):
            r=Response(screener_url(2,0),json.dumps({'status':{'rCode':code}}).encode(),NOW)
            with self.assertRaises(ProviderFailure) as ctx:parse_page(r,limit=2,offset=0)
            self.assertEqual(ctx.exception.status,status)

    def test_bad_bounds_rejected(self):
        for limit,offset in ((0,0),(10001,0),(True,0),(2,-1)):
            with self.subTest(limit=limit),self.assertRaises(ValueError):screener_url(limit,offset)

    def test_ascii_symbol_padding_preserved_and_collisions_rejected(self):
        snapshot=NasdaqScreener(Replay([page(('A  ','B'),total=2)]),page_size=2).fetch()
        self.assertEqual(snapshot.records[0].symbol,'A')
        self.assertEqual(snapshot.records[0].raw_symbol,'A  ')
        with self.assertRaises(ProviderFailure):
            NasdaqScreener(Replay([page(('A','A  '),total=2)]),page_size=2).fetch()

    def test_replay_real_complete_nasdaq_discovery(self):
        root=Path(__file__).resolve().parents[1]
        evidence=json.loads((root/'docs/evidence/nasdaq-discovery-live.json').read_text())
        self.assertEqual(evidence['status'],'success')
        responses=[]
        for record in evidence['pages']:
            response=Response(record['url'],gzip.decompress((root/record['fixture']).read_bytes()),datetime.fromisoformat(record['retrieved_at']))
            self.assertEqual(response.sha256,record['sha256'])
            responses.append(response)
        snapshot=NasdaqScreener(Replay(responses),page_size=10000).fetch()
        self.assertEqual(len(snapshot.records),evidence['records'])
        self.assertEqual(len({r.symbol for r in snapshot.records}),evidence['records'])
        self.assertFalse(evidence['active_common_universe_accepted'])


class DiagnosticTests(unittest.TestCase):
    def test_cli_refuses_empty_agent_before_network(self):
        result=subprocess.run([sys.executable,'-m','equity_research','nasdaq-discovery','--user-agent',''],capture_output=True,text=True)
        self.assertEqual(result.returncode,2)
        self.assertIn('User-Agent',result.stderr)

    def test_http_code_is_safe_structured_evidence(self):
        from equity_research.models import FactQuery,Source
        from equity_research.providers import Resolver
        from datetime import date
        class Broken:
            source=Source.NASDAQ
            def fetch(self,request):raise ProviderFailure(Status.API_ERROR,reason=FailureReason.HTTP,http_status=503)
        query=FactQuery('0000320193','assets',None,date(2026,9,30),'USD','currency','us-gaap:Assets')
        result=Resolver([Broken()],clock=lambda:NOW).resolve_current(query)
        self.assertEqual(result.attempts[2].detail,'http:503')

    def test_free_text_diagnostic_refused(self):
        with self.assertRaises(ValueError):ProviderFailure(Status.API_ERROR,reason='secret')
        with self.assertRaises(ValueError):ProviderFailure(Status.API_ERROR,http_status=999)
