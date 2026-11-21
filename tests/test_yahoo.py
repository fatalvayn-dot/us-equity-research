"""Synthetic contracts; recorded live Yahoo replay is a separate test."""
import json
import unittest
import gzip
from pathlib import Path
from dataclasses import replace
from datetime import date,datetime,timedelta,timezone
from decimal import Decimal

from equity_research.cache import FactCache
from equity_research.models import Fact,FactQuery,Issuer,Source
from equity_research.providers import ProviderFailure,Resolver,Status
from equity_research.sec import DIRECTORY_URL,DirectoryEntry,DirectorySnapshot
from equity_research.transport import Response
from equity_research.yahoo import YahooAssets,assets_url
from equity_research.companyfacts import SecCompanyFacts
from equity_research.sec import parse_directory

NOW=datetime(2026,11,1,19,tzinfo=timezone.utc)
END=date(2026,6,30)


def query(**changes):
    return replace(FactQuery('0000789019','assets',None,END,'USD','currency','us-gaap:Assets'),**changes)


def payload(value=100,**changes):
    row={'asOfDate':str(END),'periodType':'12M','currencyCode':'USD','reportedValue':{'raw':value}}
    row.update(changes)
    return {'timeseries':{'error':None,'result':[{'meta':{'symbol':['MSFT'],'type':['annualTotalAssets']},'annualTotalAssets':[row]}]}}


class Clock:
    def __init__(self):self.now=NOW
    def __call__(self):return self.now


class Transport:
    def __init__(self,clock,body=None,failure=None):
        self.clock=clock;self.body=body or json.dumps(payload()).encode();self.failure=failure;self.calls=[]
    def get(self,url):
        self.calls.append(url);self.clock.now+=timedelta(seconds=2)
        if self.failure:raise ProviderFailure(self.failure)
        return Response(url,self.body,self.clock.now)


class SecSpy:
    source=Source.SEC
    def __init__(self,clock):self.clock=clock;self.prepared=0;self.calls=0
    def prepare(self,spec):self.prepared+=1;self.clock.now+=timedelta(seconds=1)
    def fetch(self,request):
        self.calls+=1
        return Fact(request.issuer_id,'assets',Decimal(100),Source.SEC,None,request.period_end,'USD','currency',
                    self.clock(),self.clock(),'us-gaap:Assets','https://data.sec.gov/synthetic')


class YahooTests(unittest.TestCase):
    def make(self,data=None,**changes):
        clock=Clock()
        directory=DirectorySnapshot((DirectoryEntry(Issuer('0000789019','Synthetic Microsoft'),'MSFT','Nasdaq'),),DIRECTORY_URL,NOW-timedelta(hours=1),'0'*64)
        transport=Transport(clock,body=json.dumps(data).encode() if data is not None else None)
        args=dict(transport=transport,directory=directory,symbol='MSFT',clock=clock);args.update(changes)
        return YahooAssets(**args),clock,transport

    def test_live_collection_cutoff_after_fetch_and_stops_before_sec(self):
        yahoo,clock,http=self.make();sec=SecSpy(clock)
        result=Resolver([sec,yahoo],clock=clock).resolve_current(query())
        self.assertEqual(result.fact.source,Source.YAHOO)
        self.assertEqual(result.fact.value,Decimal(100))
        self.assertEqual((sec.prepared,sec.calls),(0,0))
        self.assertEqual(len(http.calls),1)
        self.assertEqual(result.as_of,result.fact.retrieved_at)

    def test_fixed_cutoff_never_advanced_to_accept_new_download(self):
        yahoo,clock,_=self.make()
        result=Resolver([yahoo],clock=clock).resolve(query().at(NOW))
        self.assertIsNone(result.fact)
        self.assertEqual(result.attempts[0].status,Status.INVALID_DATA)

    def test_live_mode_rejects_fixed_cutoff_request(self):
        yahoo,clock,_=self.make()
        with self.assertRaises(TypeError):Resolver([yahoo],clock=clock).resolve_current(query().at(NOW))

    def test_invalid_query_does_not_touch_network(self):
        yahoo,clock,http=self.make()
        with self.assertRaises(ValueError):Resolver([yahoo],clock=clock).resolve_current(query(period_end=date(2027,1,1)))
        self.assertEqual(http.calls,[])

    def test_source_failure_then_sec_prepare(self):
        for status in (Status.ACCESS_DENIED,Status.RATE_LIMIT,Status.TIMEOUT):
            with self.subTest(status=status):
                yahoo,clock,http=self.make();http.failure=status;sec=SecSpy(clock)
                result=Resolver([yahoo,sec],clock=clock).resolve_current(query())
                self.assertEqual([a.status for a in result.attempts],[status,Status.VALID])
                self.assertEqual((sec.prepared,sec.calls),(1,1))

    def test_same_month_wrong_day_not_silently_aligned(self):
        yahoo,clock,_=self.make(payload(asOfDate='2026-06-27'));sec=SecSpy(clock)
        result=Resolver([yahoo,sec],clock=clock).resolve_current(query())
        self.assertEqual(result.fact.source,Source.SEC)
        self.assertEqual(result.attempts[0].status,Status.PERIOD_MISMATCH)

    def test_exact_absence_distinct_from_bad_schema(self):
        yahoo,clock,_=self.make(payload(asOfDate='2025-06-30'))
        result=Resolver([yahoo],clock=clock).resolve_current(query())
        self.assertEqual(result.attempts[0].status,Status.MISSING)
        bad={'timeseries':{'error':None,'result':[]}}
        yahoo,clock,_=self.make(bad)
        result=Resolver([yahoo],clock=clock).resolve_current(query())
        self.assertEqual(result.attempts[0].status,Status.INVALID_DATA)

    def test_identity_and_vendor_symbol_checked(self):
        yahoo,clock,http=self.make()
        result=Resolver([yahoo],clock=clock).resolve_current(query(issuer_id='0000320193'))
        self.assertEqual(result.attempts[0].status,Status.SYMBOL_MISMATCH)
        self.assertEqual(http.calls,[])
        data=payload();data['timeseries']['result'][0]['meta']['symbol']=['AAPL']
        yahoo,clock,_=self.make(data)
        self.assertEqual(Resolver([yahoo],clock=clock).resolve_current(query()).attempts[0].status,Status.SYMBOL_MISMATCH)

    def test_stale_identity_not_accepted(self):
        yahoo,clock,http=self.make();yahoo.directory=replace(yahoo.directory,retrieved_at=NOW-timedelta(days=2))
        result=Resolver([yahoo],clock=clock).resolve_current(query())
        self.assertEqual(result.attempts[0].status,Status.INVALID_DATA)
        self.assertEqual(http.calls,[])

    def test_unsupported_duration_field_before_network(self):
        yahoo,clock,http=self.make()
        result=Resolver([yahoo],clock=clock).resolve_current(query(field='revenue'))
        self.assertEqual(result.attempts[0].status,Status.UNSUPPORTED_FIELD)
        self.assertEqual(http.calls,[])

    def test_metadata_and_bad_numbers(self):
        for change in ({'periodType':'TTM'},{'currencyCode':'EUR'},{'reportedValue':{'raw':True}},{'reportedValue':{'raw':'100'}}):
            with self.subTest(change=change):
                yahoo,clock,_=self.make(payload(**change))
                self.assertEqual(Resolver([yahoo],clock=clock).resolve_current(query()).attempts[0].status,Status.INVALID_DATA)

    def test_zero_and_negative_not_missing(self):
        for value in (0,-1):
            yahoo,clock,_=self.make(payload(value))
            result=Resolver([yahoo],clock=clock).resolve_current(query())
            self.assertEqual(result.fact.value,Decimal(value))

    def test_vendor_error_is_not_missing(self):
        for code,status in (('Unauthorized',Status.ACCESS_DENIED),('Too Many Requests',Status.RATE_LIMIT),('Other',Status.API_ERROR)):
            yahoo,clock,_=self.make({'timeseries':{'error':{'code':code},'result':None}})
            self.assertEqual(Resolver([yahoo],clock=clock).resolve_current(query()).attempts[0].status,status)

    def test_valid_snapshot_reused(self):
        yahoo,clock,http=self.make();resolver=Resolver([yahoo],clock=clock)
        resolver.resolve_current(query());resolver.resolve_current(query())
        self.assertEqual(len(http.calls),1)

    def test_duplicate_conflict_not_averaged(self):
        data=payload();data['timeseries']['result'][0]['annualTotalAssets'].append(payload(101)['timeseries']['result'][0]['annualTotalAssets'][0])
        yahoo,clock,_=self.make(data)
        self.assertEqual(Resolver([yahoo],clock=clock).resolve_current(query()).attempts[0].status,Status.INVALID_DATA)

    def test_identity_provenance_survives_sqlite(self):
        yahoo,clock,_=self.make();result=Resolver([yahoo],clock=clock).resolve_current(query())
        fact=result.fact;cache=FactCache(':memory:')
        try:
            request=query().at(result.as_of);cache.put(request,fact,clock())
            self.assertEqual(cache.get(request,Source.YAHOO,clock(),timedelta(hours=1)),fact)
            self.assertEqual(fact.source_field,'annualTotalAssets')
            self.assertEqual(fact.identity_evidence_url,DIRECTORY_URL)
        finally:cache.close()

    def test_url_does_not_alias_or_inject_symbol(self):
        for symbol in ('BRK/B','AAPL?x=1','aapl',''):
            with self.subTest(symbol=symbol),self.assertRaises(ValueError):assets_url(symbol,2026)
        self.assertNotEqual(assets_url('BRK.B',2026),assets_url('BRK-B',2026))

    def test_recorded_live_ordering_values_and_no_later_fetch_on_success(self):
        root=Path(__file__).resolve().parents[1]
        report=json.loads((root/'docs/evidence/yahoo-sec-live.json').read_text())
        previous=json.loads((root/'docs/evidence/companyfacts-live.json').read_text())
        identity=json.loads((root/'docs/evidence/sec-directory-live.json').read_text())
        directory=parse_directory(Response(DIRECTORY_URL,(root/'tests/fixtures/sec-directory-recorded.json').read_bytes(),datetime.fromisoformat(identity['retrieved_at'])))
        cutoff=datetime.fromisoformat(report['recorded_at'])
        class Replay:
            max_bytes=16_000_000
            def __init__(self,response):self.response=response;self.calls=0
            def get(self,url):
                self.calls+=1
                if url!=self.response.url:raise AssertionError('unexpected endpoint')
                return self.response
        for case in report['companies']:
            y=case['yahoo_response'];body=gzip.decompress((root/y['fixture']).read_bytes())
            yr=Response(y['url'],body,datetime.fromisoformat(y['retrieved_at']))
            self.assertEqual(yr.sha256,y['sha256'])
            prior=next(p for p in previous['companies'] if p['symbol']==case['symbol'])
            sb=gzip.decompress((root/prior['fixture']).read_bytes())
            sr=Response(prior['url'],sb,datetime.fromisoformat(prior['retrieved_at']))
            yh,sh=Replay(yr),Replay(sr)
            yahoo=YahooAssets(yh,directory=directory,symbol=case['symbol'],clock=lambda:cutoff)
            sec=SecCompanyFacts(sh,clock=lambda:cutoff)
            q=FactQuery(case['cik'],'assets',None,date.fromisoformat(case['requested_period_end']),'USD','currency','us-gaap:Assets')
            result=Resolver([sec,yahoo],clock=lambda:cutoff).resolve_current(q)
            self.assertEqual(result.fact.value,Decimal(case['fact']['value']))
            reference=next(m['value'] for m in prior['metrics'] if m['field']=='assets')
            self.assertEqual(result.fact.value,Decimal(reference))
            self.assertEqual([a.status.value for a in result.attempts],[a['status'] for a in case['attempts']])
            self.assertEqual(sh.calls,0 if result.fact.source is Source.YAHOO else 1)
