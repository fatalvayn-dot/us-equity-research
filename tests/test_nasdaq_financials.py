import gzip
import json
import unittest
from dataclasses import replace
from datetime import date,datetime,timedelta,timezone
from decimal import Decimal
from pathlib import Path

from equity_research.cache import FactCache
from equity_research.models import FactQuery,Issuer,Source
from equity_research.nasdaq_financials import NasdaqFinancials,financial_urls,monetary_value,parse_units
from equity_research.providers import ProviderFailure,Resolver,Status
from equity_research.sec import DIRECTORY_URL,DirectoryEntry,DirectorySnapshot,parse_directory
from equity_research.transport import Response

NOW=datetime(2026,11,1,22,30,tzinfo=timezone.utc)
END=date(2025,9,27)


def query(**changes):return replace(FactQuery('0000320193','assets',None,END,'USD','currency','us-gaap:Assets'),**changes)


def payload():
    return {'status':{'rCode':200},'data':{'symbol':'AAPL','balanceSheetTable':{
        'headers':{'value1':'Period Ending:','value2':'9/27/2025'},
        'rows':[{'value1':'Total Assets','value2':'$359,241,000'},{'value1':'Total Liabilities','value2':'$285,508,000'}]}}}


def unit_html(symbol='AAPL',label='In USD Thousands'):
    return f'<html><title>Company ({symbol}) Financials | Nasdaq</title><h1>Financials</h1><p>{label}</p></html>'.encode()


def identity():return DirectorySnapshot((DirectoryEntry(Issuer('0000320193','Synthetic Apple'),'AAPL','Nasdaq'),),DIRECTORY_URL,NOW-timedelta(hours=1),'0'*64)


class Replay:
    def __init__(self,responses):self.responses=responses;self.calls=[]
    def get(self,url):self.calls.append(url);return self.responses[url]


class NasdaqFinancialTests(unittest.TestCase):
    def make(self,data=None,unit=None):
        a,u=financial_urls('AAPL')
        responses={a:Response(a,json.dumps(data if data is not None else payload()).encode(),NOW),u:Response(u,unit if unit is not None else unit_html(),NOW-timedelta(seconds=1))}
        http=Replay(responses)
        return NasdaqFinancials(http,directory=identity(),symbol='AAPL',clock=lambda:NOW),http

    def test_explicit_scale_and_complete_provenance(self):
        provider,http=self.make();result=Resolver([provider],clock=lambda:NOW).resolve_current(query())
        fact=result.fact
        self.assertEqual(fact.value,Decimal('359241000000'))
        self.assertEqual(fact.source_multiplier,Decimal(1000))
        self.assertEqual(fact.unit_evidence_url,financial_urls('AAPL')[1])
        self.assertEqual(len(fact.unit_evidence_sha256),64)
        self.assertEqual(fact.data_observed_at,NOW)
        self.assertEqual(fact.available_at,NOW)
        self.assertEqual(http.calls,[financial_urls('AAPL')[1],financial_urls('AAPL')[0]])

    def test_missing_unit_caption_stops_before_financial_fetch(self):
        provider,http=self.make(unit=unit_html(label='$ alone is ambiguous'))
        result=Resolver([provider],clock=lambda:NOW).resolve_current(query())
        self.assertIsNone(result.fact)
        self.assertEqual(result.attempts[2].status,Status.INVALID_DATA)
        self.assertEqual(len(http.calls),1)

    def test_units_cannot_be_taken_from_scripts_or_wrong_symbol(self):
        for body,status in ((unit_html(label='<script>In USD Thousands</script>'),Status.INVALID_DATA),
                            (unit_html('MSFT'),Status.SYMBOL_MISMATCH),
                            (unit_html(label='In USD Thousands In EUR Millions'),Status.INVALID_DATA)):
            provider,_=self.make(unit=body)
            self.assertEqual(Resolver([provider],clock=lambda:NOW).resolve_current(query()).attempts[2].status,status)

    def test_numeric_formats_do_not_turn_missing_into_zero(self):
        for raw,value in (('$1,234',1234000),('-$1,234',-1234000),('($1,234)',-1234000),('$0',0)):
            self.assertEqual(monetary_value(raw,Decimal(1000)),Decimal(value))
        for raw in ('--','',None,'N/A','—'):self.assertIsNone(monetary_value(raw,Decimal(1000)))
        for raw in ('1,23','USD100','NaN',True,123):
            with self.subTest(raw=raw),self.assertRaises(ProviderFailure):monetary_value(raw,Decimal(1000))

    def test_wrong_period_not_calendar_aligned(self):
        provider,_=self.make()
        result=Resolver([provider],clock=lambda:NOW).resolve_current(query(period_end=date(2025,9,30)))
        self.assertEqual(result.attempts[2].status,Status.PERIOD_MISMATCH)

    def test_unsupported_duration_no_fetch(self):
        provider,http=self.make()
        result=Resolver([provider],clock=lambda:NOW).resolve_current(query(field='revenue'))
        self.assertEqual(result.attempts[2].status,Status.UNSUPPORTED_FIELD)
        self.assertEqual(http.calls,[])

    def test_wrong_identity_currency_and_vendor_symbol_rejected(self):
        provider,http=self.make()
        self.assertEqual(Resolver([provider],clock=lambda:NOW).resolve_current(query(issuer_id='0000789019')).attempts[2].status,Status.SYMBOL_MISMATCH)
        self.assertEqual(http.calls,[])
        provider,_=self.make();self.assertIsNone(Resolver([provider],clock=lambda:NOW).resolve_current(query(currency='EUR')).fact)
        data=payload();data['data']['symbol']='MSFT';provider,_=self.make(data)
        self.assertEqual(Resolver([provider],clock=lambda:NOW).resolve_current(query()).attempts[2].status,Status.SYMBOL_MISMATCH)

    def test_unavailable_cell_after_valid_evidence_is_missing(self):
        data=payload();data['data']['balanceSheetTable']['rows'][0]['value2']='--'
        provider,_=self.make(data)
        self.assertIsNone(provider.fetch(query().at(NOW)))

    def test_duplicate_rows_or_dates_rejected(self):
        for kind in ('rows','dates'):
            data=payload();table=data['data']['balanceSheetTable']
            if kind=='rows':table['rows'].append(table['rows'][0])
            else:table['headers']['value3']='9/27/2025'
            provider,_=self.make(data)
            with self.subTest(kind=kind),self.assertRaises(ProviderFailure):provider.fetch(query().at(NOW))

    def test_historical_cutoff_and_stale_identity_rejected(self):
        provider,_=self.make()
        self.assertIsNone(Resolver([provider],clock=lambda:NOW).resolve(query().at(NOW-timedelta(seconds=1))).fact)
        provider.directory=replace(provider.directory,retrieved_at=NOW-timedelta(days=2))
        self.assertIsNone(Resolver([provider],clock=lambda:NOW).resolve_current(query()).fact)

    def test_provider_error_is_not_field_absence(self):
        for code,status in ((403,Status.ACCESS_DENIED),(429,Status.RATE_LIMIT),(500,Status.API_ERROR)):
            provider,_=self.make({'status':{'rCode':code}})
            result=Resolver([provider],clock=lambda:NOW).resolve_current(query())
            self.assertEqual(result.attempts[2].status,status)
            self.assertFalse(result.confirmed_absent)

    def test_cache_reuses_both_responses_and_sqlite_preserves_scale(self):
        provider,http=self.make();resolver=Resolver([provider],clock=lambda:NOW)
        result=resolver.resolve_current(query());resolver.resolve_current(query(field='liabilities',accounting_definition='us-gaap:Liabilities'))
        self.assertEqual(len(http.calls),2)
        cache=FactCache(':memory:')
        try:
            request=query().at(result.as_of);cache.put(request,result.fact,NOW)
            self.assertEqual(cache.get(request,Source.NASDAQ,NOW,timedelta(hours=1)),result.fact)
        finally:cache.close()

    def test_ordered_fallback_stops_before_finnhub(self):
        provider,http=self.make()
        class Empty:
            def __init__(self,source):self.source=source
            def fetch(self,request):return None
        class Later:
            source=Source.FINNHUB
            def prepare(self,query):raise AssertionError('must not prepare lower source')
            def fetch(self,request):raise AssertionError('must not query lower source')
        result=Resolver([Later(),provider,Empty(Source.SEC),Empty(Source.YAHOO)],clock=lambda:NOW).resolve_current(query())
        self.assertEqual([a.status for a in result.attempts],[Status.MISSING,Status.MISSING,Status.VALID])

    def test_replay_six_real_values_and_original_filings(self):
        from equity_research.filingcheck import filing_instant
        root=Path(__file__).resolve().parents[1]
        report=json.loads((root/'docs/evidence/nasdaq-financial-live.json').read_text())
        identity_meta=json.loads((root/'docs/evidence/sec-directory-live.json').read_text())
        directory=parse_directory(Response(DIRECTORY_URL,(root/'tests/fixtures/sec-directory-recorded.json').read_bytes(),datetime.fromisoformat(identity_meta['retrieved_at'])))
        cutoff=datetime.fromisoformat(report['recorded_at']);count=0
        for case in report['companies']:
            responses={}
            for record in (case,case['unit_page']):
                response=Response(record['url'],gzip.decompress((root/record['fixture']).read_bytes()),datetime.fromisoformat(record['retrieved_at']))
                self.assertEqual(response.sha256,record['sha256']);responses[response.url]=response
            provider=NasdaqFinancials(Replay(responses),directory=directory,symbol=case['symbol'],clock=lambda:cutoff)
            for check in case['checks']:
                saved=check['fact'];q=FactQuery(saved['issuer_id'],saved['field'],None,date.fromisoformat(saved['period_end']),'USD','currency',saved['accounting_definition'])
                result=Resolver([provider],clock=lambda:cutoff).resolve_current(q)
                self.assertEqual(result.fact.value,Decimal(saved['value']))
                filing=gzip.decompress((root/check['original_filing_fixture']).read_bytes())
                original=filing_instant(filing,cik=q.issuer_id,period_end=q.period_end,concept='Assets' if q.field=='assets' else 'Liabilities')
                self.assertEqual(result.fact.value,original);count+=1
        self.assertEqual(count,6)
