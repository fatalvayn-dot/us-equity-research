"""Price identity, chronology and source-attempt contracts; synthetic unit fixtures."""
import json
import tempfile
import unittest
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

from equity_research.models import Source
from equity_research.prices import (price_url, parse_price, YahooMarketPrice, collect_prices,
    run_prices, PriceFailure, PriceIssue, PriceNotStarted)
from equity_research.providers import ProviderFailure, Status, FailureReason
from equity_research.response_archive import ResponseArchive
from equity_research.sec import DIRECTORY_URL
from equity_research.transport import Response

NOW=datetime(2026,11,2,16,30,tzinfo=timezone.utc)
CIK='0000320193'
CANDIDATES=dict(companies=[dict(symbol='AAPL',issuer_id=CIK)])

def identity(exchange='Nasdaq'):
    body=json.dumps(dict(fields=['cik','name','ticker','exchange'],data=[[320193,'Synthetic A','AAPL',exchange],[789019,'Synthetic B','MSFT','Nasdaq'],[1067983,'Synthetic classes','BRK-B','NYSE']])).encode()
    return Response(DIRECTORY_URL,body,NOW-timedelta(minutes=1))

def response(**changes):
    meta=dict(currency='USD',symbol='AAPL',exchangeName='NMS',instrumentType='EQUITY',exchangeTimezoneName='America/New_York',regularMarketPrice=120.25,regularMarketTime=int((NOW-timedelta(seconds=30)).timestamp()),fulldayPrice=999999)
    meta.update(changes)
    return Response(price_url('AAPL'),json.dumps(dict(chart=dict(error=None,result=[dict(meta=meta)]))).encode(),NOW)

def parse(r=None,i=None,**changes):
    args=dict(cik=CIK,symbol='AAPL',as_of=NOW);args.update(changes)
    return parse_price(r or response(),i or identity(),**args)

class Transport:
    def __init__(self,result=None): self.calls=[];self.result=result or response()
    def get(self,url):
        self.calls.append(url)
        if isinstance(self.result,Exception):raise self.result
        return self.result

class PricesTests(unittest.TestCase):
    def test_exact_regular_price_retains_full_original_evidence(self):
        p=parse()
        self.assertEqual(p.value,Decimal('120.25'));self.assertEqual(p.source,Source.YAHOO)
        self.assertEqual(p.raw_sha256,response().sha256);self.assertEqual(p.identity_evidence_sha256,identity().sha256)
        self.assertEqual(p.available_at,p.retrieved_at);self.assertLess(p.market_at,p.available_at)
        self.assertEqual(p.unit,'currency_per_share');self.assertFalse(p.scope_approved)
        self.assertFalse(p.investment_approved)

    def test_price_does_not_use_close_fullday_or_price_hint_multiplier(self):
        p=parse(response(priceHint=3,chartPreviousClose=999,regularMarketPrice=1.25))
        self.assertEqual(p.value,Decimal('1.25'))

    def test_missing_price_is_none_after_identity_and_metadata_validation(self):
        self.assertIsNone(parse(response(regularMarketPrice=None)))
        with self.assertRaises(ProviderFailure):parse(response(symbol='MSFT',regularMarketPrice=None))

    def test_zero_negative_boolean_string_and_nonfinite_price_rejected(self):
        for value in (0,-1,True,'123',float('nan'),float('inf'),1e101):
            r=response(regularMarketPrice=value)
            if value==1e101: r=replace(r,body=r.body.replace(b'1e+101',b'1e1001'))
            with self.subTest(value=value),self.assertRaises(ProviderFailure):parse(r)

    def test_json_decimal_has_no_binary_float_rounding(self):
        r=response();r=replace(r,body=r.body.replace(b'120.25',b'120.250000000000000000001'))
        self.assertEqual(parse(r).value,Decimal('120.250000000000000000001'))

    def test_exact_cik_and_symbol_not_name_or_class_alias(self):
        with self.assertRaises(ProviderFailure) as exc:parse(cik='0000789019')
        self.assertEqual(exc.exception.status,Status.SYMBOL_MISMATCH)
        with self.assertRaises(ProviderFailure):parse(response(symbol='MSFT'))
        with self.assertRaises(ProviderFailure):parse(response(symbol='BRK.B'),cik='0001067983',symbol='BRK.B')

    def test_symbol_url_rejects_escaping_lowercase_and_conversions(self):
        for symbol in ('aapl',' AAPL','BRK/B','AAPL?token=x','AAPL#x','^GSPC',''):
            with self.assertRaises(ValueError):price_url(symbol)
        self.assertIn('/BRK-B?',price_url('BRK-B'));self.assertIn('/BRK.B?',price_url('BRK.B'))

    def test_wrong_quote_or_identity_endpoint_rejected(self):
        for r,i in ((replace(response(),url='https://query2.finance.yahoo.com/chart/AAPL'),identity()),
                    (response(),replace(identity(),url='https://example.com/directory.json'))):
            with self.assertRaises(ProviderFailure):parse(r,i)

    def test_etf_fund_index_and_other_instruments_rejected(self):
        for instrument in ('ETF','MUTUALFUND','INDEX','CRYPTOCURRENCY','OPTION','PREFERRED'):
            with self.assertRaises(PriceFailure) as exc:parse(response(instrumentType=instrument))
            self.assertEqual(exc.exception.issue,PriceIssue.UNSUPPORTED_INSTRUMENT)

    def test_otc_arca_foreign_or_conflicting_exchange_rejected(self):
        for exchange in ('PNK','PCX','LSE','NYQ'):
            with self.assertRaises(PriceFailure) as exc:parse(response(exchangeName=exchange))
            self.assertEqual(exc.exception.issue,PriceIssue.UNSUPPORTED_EXCHANGE)
        with self.assertRaises(PriceFailure):parse(response(exchangeTimezoneName='Europe/London'))

    def test_explicit_nyse_american_pair_only(self):
        self.assertEqual(parse(response(exchangeName='ASE'),identity('NYSE American')).exchange,'ASE')
        with self.assertRaises(PriceFailure):parse(response(exchangeName='ASE'),identity('NYSE'))

    def test_non_usd_price_is_never_silently_converted(self):
        with self.assertRaises(PriceFailure) as exc:parse(response(currency='CAD'))
        self.assertEqual(exc.exception.issue,PriceIssue.CURRENCY_MISMATCH)

    def test_future_price_market_or_identity_observation_rejected(self):
        for r,i in ((replace(response(),retrieved_at=NOW+timedelta(seconds=1)),identity()),
                    (response(regularMarketTime=int((NOW+timedelta(seconds=1)).timestamp())),identity()),
                    (response(),replace(identity(),retrieved_at=NOW+timedelta(seconds=1)))):
            with self.assertRaises(PriceFailure) as exc:parse(r,i)
            self.assertEqual(exc.exception.issue,PriceIssue.FUTURE_OBSERVATION)

    def test_price_response_identity_and_market_age_are_separate(self):
        with self.assertRaises(PriceFailure) as exc:parse(as_of=NOW+timedelta(minutes=16))
        self.assertEqual(exc.exception.issue,PriceIssue.STALE_RESPONSE)
        with self.assertRaises(PriceFailure) as exc:parse(i=replace(identity(),retrieved_at=NOW-timedelta(days=2)))
        self.assertEqual(exc.exception.issue,PriceIssue.STALE_IDENTITY)
        with self.assertRaises(PriceFailure) as exc:parse(response(regularMarketTime=int((NOW-timedelta(days=5)).timestamp())))
        self.assertEqual(exc.exception.issue,PriceIssue.STALE_QUOTE)
        self.assertIsNotNone(parse(response(regularMarketTime=int((NOW-timedelta(days=3)).timestamp()))))

    def test_invalid_timestamps_and_duplicate_keys_rejected(self):
        for stamp in (True,'1793636580',1.2,10**30):
            with self.assertRaises(ProviderFailure):parse(response(regularMarketTime=stamp))
        r=response();r=replace(r,body=r.body.replace(b'"currency": "USD"',b'"currency":"USD","currency":"USD"'))
        with self.assertRaises(ProviderFailure):parse(r)

    def test_chart_errors_classified_and_empty_result_not_missing(self):
        for code,status in [('Unauthorized',Status.ACCESS_DENIED),('Too Many Requests',Status.RATE_LIMIT),('Bad Request',Status.API_ERROR)]:
            r=replace(response(),body=json.dumps(dict(chart=dict(error=dict(code=code),result=None))).encode())
            with self.assertRaises(ProviderFailure) as exc:parse(r)
            self.assertEqual(exc.exception.status,status)
        for body in (b'{"chart":{"result":[]}}',b'{"chart":{"error":{"code":123}}}',b'null',b'{}'):
            with self.assertRaises(ProviderFailure):parse(replace(response(),body=body))

    def test_scope_approval_cannot_be_constructor_injected(self):
        with self.assertRaises((TypeError,ValueError)):replace(parse(),scope_approved=True)
        with self.assertRaises(ValueError):replace(parse(),value=Decimal(0))

    def provider(self,archive,transport=None):
        return YahooMarketPrice(transport or Transport(),identity=identity(),archive=archive,clock=lambda:NOW)

    def test_cache_restart_preserves_original_time_with_zero_new_gets(self):
        with tempfile.TemporaryDirectory() as tmp:
            archive=ResponseArchive(Path(tmp)/'raw.sqlite');archive.record(identity())
            first=self.provider(archive);a,cached=first.fetch(CIK,'AAPL');self.assertFalse(cached)
            second=self.provider(archive);b,cached=second.fetch(CIK,'AAPL',allow_network=False)
            self.assertTrue(cached);self.assertEqual(a,b);self.assertEqual(second.http_calls,0)
            archive.close()

    def test_first_valid_stops_fallback_and_all_sources_archived(self):
        with tempfile.TemporaryDirectory() as tmp:
            archive=ResponseArchive(Path(tmp)/'raw.sqlite');archive.record(identity())
            report=collect_prices(CANDIDATES,provider=self.provider(archive),clock=lambda:NOW)
            self.assertEqual(report['summary']['collected_prices'],1)
            self.assertEqual([a['source'] for a in report['companies'][0]['attempts']],['Yahoo'])
            self.assertTrue(report['all_selected_price_references_archived']);self.assertFalse(report['mvp_accepted'])
            archive.close()

    def test_quota_failure_is_not_true_absence_or_other_http_attempt(self):
        with tempfile.TemporaryDirectory() as tmp:
            archive=ResponseArchive(Path(tmp)/'raw.sqlite');provider=self.provider(archive,Transport(ProviderFailure(Status.RATE_LIMIT,reason=FailureReason.HTTP,http_status=429)))
            r=collect_prices(CANDIDATES,provider=provider,clock=lambda:NOW)['companies'][0]
            self.assertEqual([a['status'] for a in r['attempts']],['rate_limit','unsupported_field','not_configured','not_configured'])
            self.assertEqual(r['attempts'][0]['http_status'],429)
            self.assertTrue(r['attempts'][0]['http_requested']);self.assertTrue(all(not a['http_requested'] for a in r['attempts'][1:]));self.assertIsNone(r['price'])
            archive.close()

    def test_zero_work_is_unattempted_not_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            archive=ResponseArchive(Path(tmp)/'raw.sqlite')
            r=collect_prices(CANDIDATES,provider=self.provider(archive),max_new_prices=0,clock=lambda:NOW)
            self.assertEqual(r['companies'][0]['state'],'not_started');self.assertEqual(r['companies'][0]['attempts'],[])
            archive.close()

    def test_identity_mismatch_blocks_yahoo_http(self):
        with tempfile.TemporaryDirectory() as tmp:
            archive=ResponseArchive(Path(tmp)/'raw.sqlite');provider=self.provider(archive)
            candidates=dict(companies=[dict(symbol='AAPL',issuer_id='0000789019')])
            r=collect_prices(candidates,provider=provider,clock=lambda:NOW)
            self.assertEqual(provider.http_calls,0);self.assertEqual(r['companies'][0]['attempts'][0]['status'],'symbol_mismatch')
            archive.close()

    def test_work_limit_and_duplicate_candidates_checked(self):
        with tempfile.TemporaryDirectory() as tmp:
            archive=ResponseArchive(Path(tmp)/'raw.sqlite');provider=self.provider(archive)
            candidates=dict(companies=CANDIDATES['companies']+[dict(symbol='MSFT',issuer_id='0000789019')])
            r=collect_prices(candidates,provider=provider,max_new_prices=1,clock=lambda:NOW)
            self.assertEqual(r['companies'][1]['state'],'not_started');self.assertEqual(provider.http_calls,1)
            for limit in (True,-1,101):
                with self.assertRaises(ValueError):collect_prices(CANDIDATES,provider=provider,max_new_prices=limit)
            with self.assertRaises(ValueError):collect_prices(dict(companies=CANDIDATES['companies']*2),provider=provider)
            archive.close()

    def test_new_identity_after_cached_price_requires_new_observation(self):
        with tempfile.TemporaryDirectory() as tmp:
            archive=ResponseArchive(Path(tmp)/'raw.sqlite');archive.record(replace(response(),retrieved_at=NOW-timedelta(minutes=2)))
            provider=self.provider(archive)
            with self.assertRaises(PriceNotStarted):provider.fetch(CIK,'AAPL',allow_network=False)
            self.assertEqual(provider.http_calls,0);archive.close()

    def test_zero_network_runner_reuses_disk_identity_and_price(self):
        with tempfile.TemporaryDirectory() as tmp:
            archive=ResponseArchive(Path(tmp)/'sources.sqlite');archive.record(identity());archive.record(response());archive.close()
            with patch('equity_research.prices.datetime',wraps=datetime) as clock:
                clock.now.return_value=NOW
                r=run_prices(CANDIDATES,state_dir=tmp,user_agent='Unit tests contact.example',max_new_prices=0)
            self.assertEqual(r['new_identity_get_invocations'],0);self.assertEqual(r['summary']['new_price_get_invocations'],0)
            self.assertTrue(Path(tmp,'report.json').exists())

    def test_missing_identity_zero_work_has_no_network(self):
        with tempfile.TemporaryDirectory() as tmp, self.assertRaises(PriceNotStarted):
            run_prices(CANDIDATES,state_dir=tmp,user_agent='Unit test contact.example',max_new_prices=0)

    def test_runner_conflicting_lease_blocks_writes(self):
        from equity_research.batch import BatchStore,RunBusy
        with tempfile.TemporaryDirectory() as tmp:
            store=BatchStore(Path(tmp)/'run-lock.sqlite');owner=store.acquire(datetime.now(timezone.utc),timedelta(hours=1))
            try:
                with self.assertRaises(RunBusy):run_prices(CANDIDATES,state_dir=tmp,user_agent='Unit test contact.example',max_new_prices=0)
            finally:store.release(owner);store.close()

    def test_confirmed_missing_and_invalid_metadata_retain_raw_source_proof(self):
        with tempfile.TemporaryDirectory() as tmp:
            archive=ResponseArchive(Path(tmp)/'raw.sqlite')
            for response_body in (response(regularMarketPrice=None),response(currency='EUR')):
                archive.db.execute('DELETE FROM response_observations_v1');archive.db.commit()
                r=collect_prices(CANDIDATES,provider=self.provider(archive,Transport(response_body)),clock=lambda:NOW)['companies'][0]
                self.assertIsNone(r['price']);self.assertEqual(r['source_evidence']['sha256'],response_body.sha256)
            archive.close()

    def test_markdown_escapes_fields_and_exposes_unattempted_status(self):
        from equity_research.prices import render_price_markdown
        report=dict(companies=[dict(symbol='<X|Y>',issuer_id=CIK,price=None,state='not_started',attempts=[])])
        text=render_price_markdown(report)
        self.assertIn('&lt;X&#124;Y&gt;',text);self.assertIn('Henüz denenmedi',text)
        self.assertIn('Mevcut değil',text)

    def test_cli_zero_work_without_identity_is_safe_typed_error(self):
        import os,subprocess,sys
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'candidates.json';path.write_text(json.dumps(CANDIDATES))
            result=subprocess.run([sys.executable,'-m','equity_research','price-run','--candidates',str(path),
                '--state-dir',str(Path(tmp)/'state'),'--max-new-prices','0','--user-agent','Unit tests contact.example'],
                capture_output=True,text=True,env=os.environ)
            self.assertEqual(result.returncode,2);self.assertEqual(json.loads(result.stdout)['error_type'],'PriceNotStarted')
            self.assertNotIn('Traceback',result.stderr)
