"""Synthetic contract tests; recorded/live checks are kept separate."""
import copy
import json
import unittest
from dataclasses import asdict,replace
from datetime import date,datetime,timedelta,timezone
from decimal import Decimal,localcontext

from equity_research.cache import encode
from equity_research.fields import SPECS
from equity_research.models import Fact,Source
from equity_research.prices import price_url
from equity_research.providers import ProviderFailure
from equity_research.reporting import build_report
from equity_research.sec import DIRECTORY_URL
from equity_research.submissions import submissions_url
from equity_research.transport import Response
from equity_research.valuation import disclosed_shares,original_filing_shares,verify_share_class,indicative_valuation,build_valuation_report
from equity_research.companyfacts import companyfacts_url

NOW=datetime(2026,11,2,20,tzinfo=timezone.utc);CIK='0000320193';ACC='0000320193-26-000020'
FILE=f'https://www.sec.gov/Archives/edgar/data/320193/{ACC.replace("-", "")}/aapl-20260930.htm'


def response(url,payload):return Response(url,json.dumps(payload).encode(),NOW-timedelta(minutes=2))


def cf(metric_values=None,**change):
    row=dict(end='2026-10-20',filed='2026-10-28',val=100,accn=ACC,form='10-Q');row.update(change)
    values=dict(revenue=1000,net_income=100,operating_cash_flow=120,capital_expenditure=20);values.update(metric_values or {})
    gaap={SPECS[k].tag:dict(units=dict(USD=[dict(start='2025-01-01',end='2025-12-31',val=v,
        accn='0000320193-26-000001',filed='2026-01-15',form='10-K')])) for k,v in values.items()}
    return response(companyfacts_url(CIK),dict(cik=320193,entityName='Synthetic A',facts={'us-gaap':gaap,
        'dei':dict(EntityCommonStockSharesOutstanding=dict(units=dict(shares=[row])))}))


def meta(tickers=None):
    return response(submissions_url(CIK),dict(cik=320193,name='Synthetic A',tickers=tickers or ['AAPL'],
        filings=dict(files=[],recent=dict(accessionNumber=[ACC],form=['10-Q'],filingDate=['2026-10-28'],
        reportDate=['2026-09-30'],primaryDocument=['aapl-20260930.htm'],acceptanceDateTime=['2026-10-28T16:00:00Z']))))


def filing(title='Common Stock',value='100',unit='xbrli:shares',extra='',scale='0'):
    body=f'''<html xmlns:dei="http://xbrl.sec.gov/dei/2026" xmlns:xbrli="http://www.xbrl.org/2003/instance" xmlns:ix="http://www.xbrl.org/2013/inlineXBRL">
<xbrli:context id="cover"><xbrli:entity><xbrli:identifier scheme="http://www.sec.gov/CIK">{CIK}</xbrli:identifier></xbrli:entity><xbrli:period><xbrli:startDate>2026-07-01</xbrli:startDate><xbrli:endDate>2026-09-30</xbrli:endDate></xbrli:period></xbrli:context>
<xbrli:context id="shares"><xbrli:entity><xbrli:identifier scheme="http://www.sec.gov/CIK">{CIK}</xbrli:identifier></xbrli:entity><xbrli:period><xbrli:instant>2026-10-20</xbrli:instant></xbrli:period></xbrli:context>
<xbrli:unit id="u"><xbrli:measure>{unit}</xbrli:measure></xbrli:unit>
<ix:nonNumeric name="dei:DocumentType" contextRef="cover">10-Q</ix:nonNumeric>
<ix:nonNumeric name="dei:DocumentPeriodEndDate" contextRef="cover">2026-09-30</ix:nonNumeric>
<ix:nonNumeric name="dei:Security12bTitle" contextRef="cover">{title}</ix:nonNumeric>
<ix:nonNumeric name="dei:TradingSymbol" contextRef="cover">AAPL</ix:nonNumeric>
<ix:nonNumeric name="dei:SecurityExchangeName" contextRef="cover">Nasdaq</ix:nonNumeric>
<ix:nonFraction name="dei:EntityCommonStockSharesOutstanding" contextRef="shares" unitRef="u" scale="{scale}" decimals="0">{value}</ix:nonFraction>{extra}</html>'''
    return Response(FILE,body.encode(),NOW-timedelta(minutes=1))


def filing_with_other_security(*, symbol='AAPL-P', title='Preferred Stock'):
    other=f'''<xbrli:context id="other"><xbrli:entity><xbrli:identifier scheme="http://www.sec.gov/CIK">{CIK}</xbrli:identifier></xbrli:entity><xbrli:period><xbrli:endDate>2026-09-30</xbrli:endDate></xbrli:period></xbrli:context>
<ix:nonNumeric name="dei:Security12bTitle" contextRef="other">{title}</ix:nonNumeric>
<ix:nonNumeric name="dei:TradingSymbol" contextRef="other">{symbol}</ix:nonNumeric>
<ix:nonNumeric name="dei:SecurityExchangeName" contextRef="other">Nasdaq</ix:nonNumeric>'''
    return filing(extra=other)


def identity():return response(DIRECTORY_URL,dict(fields=['cik','name','ticker','exchange'],data=[[320193,'Synthetic A','AAPL','Nasdaq']]))


def price(**changes):
    m=dict(symbol='AAPL',currency='USD',instrumentType='EQUITY',exchangeName='NMS',exchangeTimezoneName='America/New_York',regularMarketPrice=10,regularMarketTime=int((NOW-timedelta(seconds=30)).timestamp()))
    m.update(changes)
    return Response(price_url('AAPL'),json.dumps(dict(chart=dict(error=None,result=[dict(meta=m)]))).encode(),NOW)


def batch(**changes):
    values=dict(revenue='1000',net_income='100',operating_cash_flow='120',capital_expenditure='20');values.update(changes)
    rows=[]
    for name,v in values.items():
        if v is None:continue
        s=SPECS[name]
        f=Fact(CIK,name,Decimal(v),Source.SEC,None if s.instant else date(2025,1,1),date(2025,12,31),
            'USD','currency',NOW,NOW,s.accounting_definition,'https://data.sec.gov/recorded',raw_sha256='a'*64)
        q={k:getattr(f,k) for k in ('issuer_id','field','period_start','period_end','currency','unit','accounting_definition')}
        rows.append(dict(query=q,state='collected',fact=asdict(f),as_of=NOW,
            attempts=[dict(source='Yahoo',status='unsupported_field',attempted_at=NOW),dict(source='SEC',status='valid',attempted_at=NOW)]))
    return json.loads(json.dumps(dict(schema_version=1,generated_at=NOW,companies=[dict(symbol='AAPL',issuer_id=CIK,scope_status='pending_scope',scope_reason='review',fields=rows)]),default=encode))


def valuation(**changes):
    kwargs=dict(price_response=price(),identity=identity(),companyfacts=cf(),metadata=meta(),filing=filing(),financial_company=build_report(batch())['companies'][0],as_of=NOW)
    kwargs.update(changes);return indicative_valuation(**kwargs)


class ValuationTests(unittest.TestCase):
    def test_original_sec_share_fallback_when_companyfacts_lacks_dei(self):
        original=filing()
        proof=original_filing_shares(meta(),original,cik=CIK,symbol='AAPL',as_of=NOW)
        self.assertEqual(proof['value'],Decimal(100))
        self.assertEqual(proof['source_url'],original.url)
        self.assertEqual(proof['raw_sha256'],original.sha256)
        self.assertEqual(proof['evidence_method'],'original_sec_filing_dei_exact')
        raw=json.loads(cf().body)
        raw['facts'].pop('dei')
        missing=Response(companyfacts_url(CIK),json.dumps(raw).encode(),NOW-timedelta(minutes=2))
        historical=build_valuation_report(batch(),[missing,meta(),original,identity(),price()],as_of=NOW)
        self.assertIsNone(historical['companies'][0]['valuation'])
        latest=build_valuation_report(batch(),[missing,meta(),original,identity(),price()],
                                      as_of=NOW,allow_original_share_fallback=True)
        self.assertEqual(latest['summary']['indicative_valuations'],1)
        v=latest['companies'][0]['valuation']
        self.assertEqual(v['indicated_capitalization'],Decimal(1000))
        self.assertEqual(v['disclosed_shares']['companyfacts']['evidence_method'],
                         'original_sec_filing_dei_exact')

    def test_original_share_fallback_rejects_wrong_issuer_count_and_class(self):
        from equity_research.valuation import original_filing_shares
        with self.assertRaises(ProviderFailure):
            original_filing_shares(meta(),filing(),cik='0000789019',symbol='AAPL',as_of=NOW)
        with self.assertRaises(ProviderFailure):
            original_filing_shares(meta(),filing(value='99x'),cik=CIK,symbol='AAPL',as_of=NOW)
        raw=json.loads(cf().body);raw['facts'].pop('dei')
        missing=Response(companyfacts_url(CIK),json.dumps(raw).encode(),NOW-timedelta(minutes=2))
        report=build_valuation_report(batch(),[missing,meta(),filing(title='Class A Common Stock'),
                                               identity(),price()],as_of=NOW,allow_original_share_fallback=True)
        self.assertEqual(report['summary']['indicative_valuations'],0)

    def test_latest_exact_disclosed_shares_preserves_dates_units_and_source(self):
        s=disclosed_shares(cf(),cik=CIK,as_of=NOW)
        self.assertEqual(s['value'],Decimal(100));self.assertEqual(s['end'],date(2026,10,20))
        self.assertEqual(s['unit'],'shares');self.assertEqual(s['raw_sha256'],cf().sha256)
        self.assertEqual(s['available_at'],datetime(2026,10,29,5,tzinfo=timezone.utc))

    def test_unselected_historic_fraction_is_quarantined_without_repairing_or_using_it(self):
        raw=json.loads(cf().body);rows=raw['facts']['dei']['EntityCommonStockSharesOutstanding']['units']['shares']
        rows.append(dict(rows[0],end='2011-04-30',filed='2011-05-26',val=133.9,accn='0001193125-11-151778'))
        result=disclosed_shares(response(companyfacts_url(CIK),raw),cik=CIK,as_of=NOW)
        self.assertEqual(result['value'],Decimal(100))
        self.assertEqual(result['historical_numeric_review'][0]['end'],date(2011,4,30))
        self.assertEqual(result['historical_numeric_review'][0]['status'],'unselected_historical_numeric_value_invalid')

    def test_invalid_latest_row_cannot_fall_back_to_valid_older_shares(self):
        raw=json.loads(cf(val=133.9).body);rows=raw['facts']['dei']['EntityCommonStockSharesOutstanding']['units']['shares']
        rows.append(dict(rows[0],end='2026-09-01',filed='2026-09-04',val=100))
        with self.assertRaises(ProviderFailure):disclosed_shares(response(companyfacts_url(CIK),raw),cik=CIK,as_of=NOW)

    def test_issued_or_weighted_average_shares_are_not_aliases(self):
        raw=json.loads(cf().body);raw['facts']={'us-gaap':{'CommonStockSharesIssued':{'units':{'shares':[dict(val=100)]}}}}
        self.assertIsNone(disclosed_shares(response(companyfacts_url(CIK),raw),cik=CIK,as_of=NOW))

    def test_shares_zero_negative_boolean_fractional_and_wrong_unit_rejected(self):
        for value in (0,-1,True,1.5,'100'):
            with self.subTest(value=value),self.assertRaises(ProviderFailure):disclosed_shares(cf(val=value),cik=CIK,as_of=NOW)
        raw=json.loads(cf().body);concept=raw['facts']['dei']['EntityCommonStockSharesOutstanding'];concept['units']['USD']=concept['units'].pop('shares')
        with self.assertRaises(ProviderFailure):disclosed_shares(response(companyfacts_url(CIK),raw),cik=CIK,as_of=NOW)

    def test_malformed_taxonomy_units_and_rows_are_classified_invalid_data(self):
        for dei in ([],dict(EntityCommonStockSharesOutstanding=[]),
                    dict(EntityCommonStockSharesOutstanding=dict(units=[])),
                    dict(EntityCommonStockSharesOutstanding=dict(units=dict(shares=['bad row'])))):
            raw=json.loads(cf().body);raw['facts']['dei']=dei
            with self.assertRaises(ProviderFailure):disclosed_shares(response(companyfacts_url(CIK),raw),cik=CIK,as_of=NOW)

    def test_future_stale_or_duration_share_count_cannot_be_current(self):
        for change in (dict(end='2027-01-01'),dict(end='2026-01-01'),dict(start='2026-01-01')):
            with self.subTest(change=change),self.assertRaises(ProviderFailure):disclosed_shares(cf(**change),cik=CIK,as_of=NOW)
        with self.assertRaises(ProviderFailure):disclosed_shares(replace(cf(),retrieved_at=NOW+timedelta(seconds=1)),cik=CIK,as_of=NOW)
        with self.assertRaises(ProviderFailure):disclosed_shares(cf(),cik=CIK,as_of=NOW+timedelta(hours=7))

    def test_ambiguous_latest_rows_not_arbitrarily_selected(self):
        raw=json.loads(cf().body);rows=raw['facts']['dei']['EntityCommonStockSharesOutstanding']['units']['shares'];rows.append(dict(rows[0],val=101))
        with self.assertRaises(ProviderFailure):disclosed_shares(response(companyfacts_url(CIK),raw),cik=CIK,as_of=NOW)

    def test_original_primary_share_count_must_match_exact_value_and_unit(self):
        s=disclosed_shares(cf(),cik=CIK,as_of=NOW)
        proof=verify_share_class(s,meta(),filing(),symbol='AAPL',as_of=NOW)
        self.assertEqual(proof['value'],Decimal(100));self.assertEqual(proof['original_filing']['raw_sha256'],filing().sha256)
        for doc in (filing(value='101'),filing(unit='xbrli:pure'),replace(filing(),url=FILE+'wrong')):
            with self.assertRaises(ProviderFailure):verify_share_class(s,meta(),doc,symbol='AAPL',as_of=NOW)

    def test_multi_ticker_class_labeled_or_preferred_instruments_withheld(self):
        for kwargs in (dict(metadata=meta(['AAPL','AAPL-B'])),dict(filing=filing(title='Class A Common Stock')),
                       dict(filing=filing(title='Preferred Stock')),dict(filing=filing(title='Depositary Shares'))):
            with self.subTest(kwargs=kwargs),self.assertRaises(ProviderFailure):valuation(**kwargs)

    def test_extra_ticker_requires_exact_non_common_cover_corroboration(self):
        s=disclosed_shares(cf(),cik=CIK,as_of=NOW)
        proof=verify_share_class(s,meta(['AAPL','AAPL-P']),filing_with_other_security(),symbol='AAPL',as_of=NOW)
        self.assertEqual(proof['common_security_scope'],'single_verified_common_symbol_with_explicit_non_common_tickers')
        self.assertEqual(proof['other_registered_securities'],[
            dict(symbol='AAPL-P',title='Preferred Stock',exchange='Nasdaq',
                 symbol_corroboration='exact_cover_symbol')])
        for document in (filing(),filing_with_other_security(title='Class B Common Stock'),
                         filing_with_other_security(title='Subscription Rights')):
            with self.subTest(document=document),self.assertRaises(ProviderFailure):
                verify_share_class(s,meta(['AAPL','AAPL-P']),document,symbol='AAPL',as_of=NOW)

    def test_single_non_common_cover_alias_is_retained_without_symbol_normalization(self):
        s=disclosed_shares(cf(),cik=CIK,as_of=NOW)
        proof=verify_share_class(s,meta(['AAPL','AAPL-P']),
            filing_with_other_security(symbol='AAPL PRP'),symbol='AAPL',as_of=NOW)
        other=proof['other_registered_securities'][0]
        self.assertEqual(other['symbol'],'AAPL-P');self.assertEqual(other['cover_symbol'],'AAPL PRP')
        self.assertEqual(other['symbol_corroboration'],'single_unambiguous_non_common_cover_alias')

    def test_cover_only_fixed_coupon_debt_is_excluded_from_common_share_count(self):
        shares = disclosed_shares(cf(), cik=CIK, as_of=NOW)
        document = filing_with_other_security(symbol='AAPL30', title='1.125% Senior Notes due 2030')
        proof = verify_share_class(shares, meta(), document, symbol='AAPL', as_of=NOW)
        self.assertEqual(proof['value'], shares['value'])
        self.assertEqual(proof['original_filing']['raw_sha256'], document.sha256)
        self.assertEqual(proof['other_registered_securities'], [
            dict(symbol='AAPL30', title='1.125% Senior Notes due 2030', exchange='Nasdaq',
                 symbol_corroboration='cover_only_fixed_coupon_debt')])

    def test_explicit_floating_and_fractional_cover_debt_keeps_exact_common_count(self):
        shares = disclosed_shares(cf(), cik=CIK, as_of=NOW)
        for title in ('7 1/2% Guaranteed Subordinated Notes due 2035',
                      'Floating Rate Notes Due 2028',
                      '3.433% Fixed-to-Floating Rate Notes due May 20, 2032'):
            with self.subTest(title=title):
                document = filing_with_other_security(symbol='AAPL/30', title=title)
                proof = verify_share_class(shares, meta(), document, symbol='AAPL', as_of=NOW)
                self.assertEqual(proof['value'], shares['value'])
                self.assertEqual(proof['original_filing']['raw_sha256'], document.sha256)
                self.assertEqual(proof['other_registered_securities'], [
                    dict(symbol='AAPL/30', title=title, exchange='Nasdaq',
                         symbol_corroboration='cover_only_explicit_debt')])
                with self.assertRaises(ProviderFailure):
                    verify_share_class(shares, meta(['AAPL', 'AAPL-B']), document,
                                       symbol='AAPL', as_of=NOW)

    def test_cover_only_ambiguous_security_or_unmatched_metadata_still_rejected(self):
        shares = disclosed_shares(cf(), cik=CIK, as_of=NOW)
        for title in ('Preferred Stock', '1.125% Convertible Notes due 2030', 'Common Stock',
                      'Floating Rate Convertible Notes due 2030', 'Medium-Term Notes'):
            with self.subTest(title=title), self.assertRaises(ProviderFailure):
                verify_share_class(shares, meta(), filing_with_other_security(title=title),
                                   symbol='AAPL', as_of=NOW)
        document = filing_with_other_security(symbol='AAPL30', title='1.125% Notes due 2030')
        with self.assertRaises(ProviderFailure):
            verify_share_class(shares, meta(['AAPL', 'AAPL-B']), document, symbol='AAPL', as_of=NOW)

    def test_dimensional_share_count_never_becomes_issuer_aggregate(self):
        doc=filing();body=doc.body.replace(b'<xbrli:context id="shares">',b'<xbrli:context id="shares"><xbrli:scenario></xbrli:scenario>')
        with self.assertRaises(ProviderFailure):valuation(filing=replace(doc,body=body))

    def test_indicated_cap_and_three_ratios_are_traceable_without_score(self):
        v=valuation()
        self.assertEqual(v['indicated_capitalization'],Decimal(1000))
        self.assertEqual([m['value'] for m in v['metrics']],[Decimal(1),Decimal('.1'),Decimal('.1')])
        self.assertFalse(v['corporate_actions_validated']);self.assertFalse(v['investment_approved'])
        self.assertIsNone(v['fair_value']);self.assertIsNone(v['total_score'])
        self.assertIn('not_observed_current_market_capitalization',v['limitations'])

    def test_caller_calculation_injection_is_ignored(self):
        c=build_report(batch())['companies'][0];c['calculations'][6]['value']=Decimal('99999999999999999999')
        c['total_score']=100;c['investment_approved']=True
        self.assertEqual(valuation(financial_company=c)['metrics'][2]['value'],Decimal('.1'))

    def test_conflicting_current_sec_value_blocks_indication_without_replacing_first_source(self):
        with self.assertRaises(ProviderFailure):valuation(companyfacts=cf(metric_values={'net_income':99}))

    def test_negative_income_remains_negative_missing_is_not_zero(self):
        c=build_report(batch(net_income='-100'))['companies'][0]
        self.assertEqual(valuation(financial_company=c,companyfacts=cf(metric_values={'net_income':-100}))['metrics'][1]['value'],Decimal('-.1'))
        c=build_report(batch(net_income=None,capital_expenditure=None,productive_asset_cash_payments='20'))['companies'][0]
        metrics=valuation(financial_company=c)['metrics']
        self.assertIsNone(metrics[1]['value']);self.assertIsNone(metrics[2]['value'])

    def test_price_wrong_issuer_currency_and_stale_response_not_joined(self):
        for p in (price(symbol='MSFT'),price(currency='EUR'),replace(price(),retrieved_at=NOW-timedelta(hours=1))):
            with self.assertRaises(ProviderFailure):valuation(price_response=p)

    def test_rejected_financial_currency_and_period_do_not_reach_valuation(self):
        b=batch();b['companies'][0]['fields'][0]['fact']['currency']='EUR'
        with self.assertRaises(ProviderFailure):valuation(financial_company=build_report(b)['companies'][0])

    def test_decimal_arithmetic_independent_of_callers_precision(self):
        with localcontext() as context:
            context.prec=3
            value=valuation(price_response=price(regularMarketPrice=12.345))['indicated_capitalization']
        self.assertEqual(value,Decimal('1234.500'))

    def test_report_only_evaluates_provided_sources_no_invented_attempts(self):
        r=build_valuation_report(batch(),[cf(),meta(),filing(),identity(),price()],as_of=NOW)
        self.assertEqual(r['summary']['indicative_valuations'],1);self.assertEqual(r['new_network_requests'],0)
        r=build_valuation_report(batch(),[],as_of=NOW)
        self.assertEqual(r['summary']['pending'],1);self.assertIsNone(r['companies'][0]['valuation'])

    def test_conflicting_same_timestamp_sources_and_future_financial_cutoff_rejected(self):
        with self.assertRaises(ValueError):build_valuation_report(batch(),[cf(),cf(val=101)],as_of=NOW)
        with self.assertRaises(ValueError):build_valuation_report(batch(),[],as_of=NOW-timedelta(seconds=1))

    def test_invalid_company_identity_isolated_from_other_companies(self):
        b=batch();bad=copy.deepcopy(b['companies'][0]);bad.update(symbol='BAD',issuer_id='bad-cik');b['companies'].insert(0,bad)
        r=build_valuation_report(b,[cf(),meta(),filing(),identity(),price()],as_of=NOW)
        self.assertEqual(r['summary']['indicative_valuations'],1);self.assertEqual(r['summary']['rejected'],1)


if __name__=='__main__':unittest.main()
