"""Synthetic Finnhub contracts only; no production key or live fixture used."""
import io
import json
import unittest
import os
import subprocess
import sys
from unittest.mock import patch
from contextlib import redirect_stdout
from dataclasses import replace
from datetime import date,datetime,timedelta,timezone
from decimal import Decimal

from equity_research.finnhub import FinnhubConfig,FinnhubReported,reported_url
from equity_research.models import FactQuery,Source
from equity_research.providers import ProviderFailure,Resolver,Status
from equity_research.transport import HttpTransport,Response

NOW=datetime(2026,11,1,21,40,tzinfo=timezone.utc)
END=date(2025,9,27)
FAKE_KEY='synthetic-finnhub-contract-token'


def query(**changes):
    return replace(FactQuery('0000320193','assets',None,END,'USD','currency','us-gaap:Assets'),**changes)


def payload(value=123):
    return {'cik':'320193','symbol':'AAPL','data':[{
        'cik':'320193','symbol':'AAPL','form':'10-K','accessNumber':'0000320193-25-000079',
        'startDate':'2024-09-29 00:00:00','endDate':'2025-09-27 00:00:00','filedDate':'2025-10-31 00:00:00',
        'report':{'bs':[{'concept':'us-gaap_Assets','unit':'usd','value':value}]}}]}


class Transport:
    def __init__(self,data=None,failure=None,body=None):
        self.calls=[];self.data=data or payload();self.failure=failure;self.body=body
    def get(self,url):
        self.calls.append(url)
        if self.failure:raise ProviderFailure(self.failure)
        body=self.body if self.body is not None else json.dumps(self.data).encode()
        return Response(url,body,NOW)


class FinnhubTests(unittest.TestCase):
    def test_cli_operational_failure_cannot_be_green_smoke(self):
        from equity_research.__main__ import main
        class Blocked:
            source=Source.FINNHUB
            def fetch(self,request):raise ProviderFailure(Status.ACCESS_DENIED)
        stdout=io.StringIO()
        args=['equity_research','finnhub-fact','--cik','0000320193','--field','assets','--period-end','2025-09-27']
        with patch('sys.argv',args),patch('equity_research.__main__.FinnhubConfig.from_environment',return_value=FinnhubConfig(FAKE_KEY)),patch('equity_research.__main__.FinnhubReported',return_value=Blocked()),redirect_stdout(stdout):
            with self.assertRaises(SystemExit) as ctx:main()
        self.assertEqual(ctx.exception.code,2)
        self.assertEqual(json.loads(stdout.getvalue())['attempts'][-1]['status'],'access_denied')
        self.assertNotIn(FAKE_KEY,stdout.getvalue())

    def test_cli_missing_key_returns_not_configured_without_network(self):
        env={k:v for k,v in os.environ.items() if k not in ('FINNHUB_API_KEY','FINNHUB_TOKEN')}
        result=subprocess.run([sys.executable,'-m','equity_research','finnhub-fact','--cik','0000320193','--field','assets','--period-end','2025-09-27'],env=env,capture_output=True,text=True)
        self.assertEqual(result.returncode,2)
        self.assertEqual(json.loads(result.stdout)['status'],'not_configured')
        self.assertFalse(json.loads(result.stdout)['network_attempted'])

    def make(self,data=None,**kwargs):
        transport=Transport(data)
        provider=FinnhubReported(FinnhubConfig(FAKE_KEY),transport=transport,clock=lambda:NOW,**kwargs)
        return provider,transport

    def test_key_unconfigured_not_queried_or_counted_missing(self):
        transport=Transport()
        provider=FinnhubReported(FinnhubConfig(),transport=transport)
        result=Resolver([provider],clock=lambda:NOW).resolve_current(query())
        self.assertEqual(result.attempts[-1].source,Source.FINNHUB)
        self.assertEqual(result.attempts[-1].status,Status.NOT_CONFIGURED)
        self.assertFalse(result.confirmed_absent)
        self.assertEqual(transport.calls,[])

    def test_environment_and_repr_do_not_expose_credential(self):
        config=FinnhubConfig.from_environment({'FINNHUB_API_KEY':FAKE_KEY})
        self.assertTrue(config.configured)
        self.assertNotIn(FAKE_KEY,repr(config))
        self.assertFalse(FinnhubConfig.from_environment({}).configured)
        self.assertEqual(FinnhubConfig.from_environment({'FINNHUB_TOKEN':FAKE_KEY}),config)
        with self.assertRaises(ValueError):FinnhubConfig.from_environment({'FINNHUB_TOKEN':'a','FINNHUB_API_KEY':'b'})
        with self.assertRaises(ValueError):FinnhubConfig('bad\r\nheader')

    def test_value_exact_identity_units_and_filing_provenance(self):
        provider,http=self.make();result=Resolver([provider],clock=lambda:NOW).resolve_current(query())
        self.assertEqual(result.fact.value,Decimal(123))
        self.assertEqual(result.fact.filing_accession,'0000320193-25-000079')
        self.assertEqual(result.fact.filed_on,date(2025,10,31))
        self.assertEqual(result.fact.available_at,datetime(2025,11,1,5,tzinfo=timezone.utc))
        self.assertEqual(result.fact.source_field,'us-gaap_Assets')
        self.assertNotIn(FAKE_KEY,result.fact.source_url)
        self.assertEqual(len(http.calls),1)

    def test_lower_priority_not_prepared_after_first_success(self):
        provider,http=self.make()
        class Earlier:
            source=Source.SEC
            def fetch(self,request):
                from equity_research.models import Fact
                return Fact(request.issuer_id,'assets',Decimal(123),Source.SEC,None,END,'USD','currency',NOW,NOW,'us-gaap:Assets','https://data.sec.gov/synthetic')
        result=Resolver([provider,Earlier()],clock=lambda:NOW).resolve_current(query())
        self.assertEqual(result.fact.source,Source.SEC)
        self.assertEqual(http.calls,[])

    def test_mismatched_identity_is_never_missing(self):
        for location in ('top','filing'):
            data=payload()
            if location=='top':data['cik']='789019'
            else:data['data'][0]['cik']='789019'
            provider,_=self.make(data)
            result=Resolver([provider],clock=lambda:NOW).resolve_current(query())
            self.assertEqual(result.attempts[-1].status,Status.SYMBOL_MISMATCH)

    def test_exact_end_date_and_duration_start_required(self):
        provider,_=self.make();self.assertIsNone(provider.fetch(query(period_end=date(2025,9,30)).at(NOW)))
        data=payload();data['data'][0]['report']['ic']=[{'concept':'us-gaap_NetIncomeLoss','unit':'usd','value':50}]
        provider,_=self.make(data)
        q=query(field='net_income',period_start=date(2024,9,28),accounting_definition='us-gaap:NetIncomeLoss')
        self.assertIsNone(provider.fetch(q.at(NOW)))
        valid=query(field='net_income',period_start=date(2024,9,29),accounting_definition='us-gaap:NetIncomeLoss')
        self.assertEqual(provider.fetch(valid.at(NOW)).value,Decimal(50))

    def test_unverified_currency_scale_dimensions_and_numbers_rejected(self):
        for changes in ({'unit':None},{'unit':'eur'},{'scale':6},{'dimensions':{'segment':'x'}},{'value':True},{'value':'123'}):
            data=payload();data['data'][0]['report']['bs'][0].update(changes)
            provider,_=self.make(data)
            with self.subTest(changes=changes),self.assertRaises(ProviderFailure):provider.fetch(query().at(NOW))

    def test_legacy_unitless_map_unsupported_not_zero(self):
        data=payload();data['data'][0]['report']['bs']={'Assets':123}
        provider,_=self.make(data)
        with self.assertRaises(ProviderFailure) as ctx:provider.fetch(query().at(NOW))
        self.assertEqual(ctx.exception.status,Status.UNSUPPORTED_FIELD)

    def test_zero_negative_and_decimal_precision(self):
        for value in (0,-10):
            provider,_=self.make(payload(value));self.assertEqual(provider.fetch(query().at(NOW)).value,Decimal(value))
        body=json.dumps(payload()).replace('"value": 123','"value": 123.1234567890123456789').encode()
        provider=FinnhubReported(FinnhubConfig(FAKE_KEY),transport=Transport(body=body),clock=lambda:NOW)
        self.assertEqual(provider.fetch(query().at(NOW)).value,Decimal('123.1234567890123456789'))

    def test_missing_concept_after_valid_response(self):
        data=payload();data['data'][0]['report']['bs']=[]
        provider,_=self.make(data)
        self.assertIsNone(provider.fetch(query().at(NOW)))

    def test_http_and_json_access_errors_remain_operational(self):
        for message,status in (('API limit reached',Status.RATE_LIMIT),('Invalid API key',Status.ACCESS_DENIED),('You do not have access',Status.ACCESS_DENIED),('Other failure',Status.API_ERROR)):
            provider,_=self.make({'error':message})
            result=Resolver([provider],clock=lambda:NOW).resolve_current(query())
            self.assertEqual(result.attempts[-1].status,status)
            self.assertFalse(result.confirmed_absent)
        provider=FinnhubReported(FinnhubConfig(FAKE_KEY),transport=Transport(failure=Status.RATE_LIMIT),clock=lambda:NOW)
        self.assertEqual(Resolver([provider],clock=lambda:NOW).resolve_current(query()).attempts[-1].status,Status.RATE_LIMIT)

    def test_future_filed_and_historical_snapshot_not_accepted(self):
        data=payload();data['data'][0]['filedDate']='2026-11-01'
        provider,_=self.make(data);self.assertIsNone(provider.fetch(query().at(NOW)))
        provider,_=self.make()
        with self.assertRaises(ProviderFailure):provider.fetch(query().at(NOW-timedelta(seconds=1)))

    def test_conflicting_values_same_filing_day_not_averaged(self):
        data=payload();data['data'][0]['report']['bs'].append({'concept':'us-gaap_Assets','unit':'USD','value':124})
        provider,_=self.make(data)
        with self.assertRaises(ProviderFailure):provider.fetch(query().at(NOW))

    def test_unsupported_fields_and_frequency_before_network(self):
        provider,http=self.make()
        for q in (query(field='unknown'),query(field='net_income',period_start=END-timedelta(days=90),accounting_definition='us-gaap:NetIncomeLoss')):
            with self.assertRaises(ProviderFailure) as ctx:provider.fetch(q.at(NOW))
            self.assertEqual(ctx.exception.status,Status.UNSUPPORTED_FIELD)
        self.assertEqual(http.calls,[])

    def test_memory_cache_reuses_snapshot_across_fields(self):
        provider,http=self.make();provider.fetch(query().at(NOW));provider.fetch(query(field='liabilities',accounting_definition='us-gaap:Liabilities').at(NOW))
        self.assertEqual(len(http.calls),1)

    def test_url_never_includes_secret(self):
        url=reported_url('0000320193',END,'annual')
        self.assertNotIn('token',url);self.assertIn('cik=0000320193',url)
        with self.assertRaises(ValueError):reported_url('../secret',END,'annual')


class HeaderTests(unittest.TestCase):
    def transport(self,body=b'{}',**changes):
        url=reported_url('0000320193',END,'annual')
        class Fake(io.BytesIO):
            status=200;headers={}
            def geturl(self):return url
        class Opener:
            def open(self,request,timeout):self.request=request;return Fake(body)
        opener=Opener()
        args=dict(user_agent='Synthetic tests',allowed_hosts={'finnhub.io'},opener=opener,auth_headers={'X-Finnhub-Token':FAKE_KEY})
        args.update(changes)
        return HttpTransport(**args),opener,url

    def test_auth_header_only_and_no_token_in_response_url(self):
        transport,opener,url=self.transport();response=transport.get(url)
        self.assertEqual(opener.request.get_header('X-finnhub-token'),FAKE_KEY)
        self.assertNotIn(FAKE_KEY,response.url)
        self.assertNotIn(FAKE_KEY,repr(transport))

    def test_secret_never_forwarded_to_another_origin(self):
        for hosts in ({'data.sec.gov'},{'finnhub.io','query1.finance.yahoo.com'}):
            with self.subTest(hosts=hosts),self.assertRaises(ValueError):self.transport(allowed_hosts=hosts)

    def test_echoed_token_body_and_secret_query_rejected(self):
        transport,_,url=self.transport(body=FAKE_KEY.encode())
        with self.assertRaises(ProviderFailure):transport.get(url)
        transport,_,url=self.transport()
        with self.assertRaises(ValueError):transport.get(url+'&token='+FAKE_KEY)
