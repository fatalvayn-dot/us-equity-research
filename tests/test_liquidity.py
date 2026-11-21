"""Exact balances/flows, never proxies for sector acceptance or investment scores."""
import json
import unittest
from dataclasses import replace
from datetime import date,datetime,timezone
from decimal import Decimal,localcontext

from equity_research.calculations import calculate
from equity_research.fields import SPECS
from equity_research.models import Fact,Source,FactQuery
from equity_research.providers import ProviderFailure,Status
from equity_research.companyfacts import SecCompanyFacts
from equity_research.reporting import build_report
from equity_research.cache import encode
from equity_research.yahoo import YahooAssets
from equity_research.nasdaq_financials import NasdaqFinancials
from equity_research.finnhub import FinnhubReported,FinnhubConfig
from equity_research.transport import Response

NOW=datetime(2026,11,2,18,tzinfo=timezone.utc);START=date(2025,1,1);END=date(2025,12,31);CIK='0000320193'
NEW=('current_assets','current_liabilities','cash_equivalents','operating_income','gross_profit')

def fact(field,value,**changes):
    s=SPECS[field]
    f=Fact(CIK,field,Decimal(value),Source.SEC,None if s.instant else START,END,'USD','currency',NOW,NOW,
        s.accounting_definition,'https://data.sec.gov/recorded',raw_sha256='a'*64)
    return replace(f,**changes)

def calc(name,facts,**changes):
    args=dict(issuer_id=CIK,period_start=START,period_end=END,currency='USD',as_of=NOW);args.update(changes)
    return calculate(name,facts,**args)

class LiquidityTests(unittest.TestCase):
    def test_current_ratio_exact_balances_and_no_duration_assigned(self):
        r=calc('current_ratio',{'current_assets':fact('current_assets','150'),'current_liabilities':fact('current_liabilities','100')},period_start=None)
        self.assertEqual(r['value'],Decimal('1.5'));self.assertIsNone(r['period_start'])
        self.assertTrue(all(f['period_start'] is None for f in r['inputs']));self.assertFalse(r['sector_model_supported'])

    def test_explicit_zero_cash_is_valid_and_does_not_invent_missing_cash(self):
        r=calc('cash_equivalents_to_current_liabilities',{'cash_equivalents':fact('cash_equivalents','0'),'current_liabilities':fact('current_liabilities','100')})
        self.assertEqual(r['value'],Decimal(0))
        r=calc('cash_equivalents_to_current_liabilities',{'current_liabilities':fact('current_liabilities','100')})
        self.assertIsNone(r['value']);self.assertEqual(r['missing_fields'],['cash_equivalents'])

    def test_zero_liabilities_ratio_not_infinity_but_valid_working_capital(self):
        values={'current_assets':fact('current_assets','100'),'current_liabilities':fact('current_liabilities','0')}
        self.assertEqual(calc('current_ratio',values)['status'],'nonpositive_denominator')
        self.assertEqual(calc('working_capital',values)['value'],Decimal(100))

    def test_negative_working_capital_preserved_without_insolvency_claim(self):
        r=calc('working_capital',{'current_assets':fact('current_assets','90'),'current_liabilities':fact('current_liabilities','100')})
        self.assertEqual(r['value'],Decimal('-10'));self.assertEqual(r['unit'],'currency')
        self.assertEqual(r['currency'],'USD');self.assertFalse(r['investment_approved'])

    def test_negative_balance_not_abs_or_zero_filled(self):
        for field in ('current_assets','current_liabilities'):
            values={'current_assets':fact('current_assets','100'),'current_liabilities':fact('current_liabilities','50')}
            values[field]=fact(field,'-1')
            for name in ('current_ratio','working_capital'):
                r=calc(name,values);self.assertEqual(r['status'],'unsupported_balance_sign');self.assertIsNone(r['value'])

    def test_total_assets_or_liabilities_never_fill_current_balances(self):
        r=calc('current_ratio',{'assets':fact('assets','100'),'liabilities':fact('liabilities','50')})
        self.assertEqual(r['missing_fields'],['current_assets','current_liabilities'])
        r=calc('current_ratio',{'current_assets':fact('assets','100'),'current_liabilities':fact('current_liabilities','50')})
        self.assertEqual(r['status'],'invalid_inputs')

    def test_other_cash_concept_cannot_be_substituted(self):
        bad=fact('cash_equivalents','100',accounting_definition='us-gaap:CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents')
        self.assertEqual(calc('cash_equivalents_to_current_liabilities',{'cash_equivalents':bad,'current_liabilities':fact('current_liabilities','50')})['status'],'invalid_inputs')

    def test_current_balances_reject_duration_or_wrong_date(self):
        for bad in (fact('current_assets','100',period_start=START),fact('current_assets','100',period_end=date(2025,12,30))):
            self.assertEqual(calc('current_ratio',{'current_assets':bad,'current_liabilities':fact('current_liabilities','50')})['status'],'invalid_inputs')

    def test_issuer_currency_and_future_snapshot_not_joined(self):
        from datetime import timedelta
        for bad in (fact('current_assets','100',issuer_id='0000789019'),fact('current_assets','100',currency='EUR'),fact('current_assets','100',retrieved_at=NOW+timedelta(days=1))):
            self.assertEqual(calc('current_ratio',{'current_assets':bad,'current_liabilities':fact('current_liabilities','50')})['status'],'invalid_inputs')

    def test_operating_and_gross_margins_keep_distinct_accounting(self):
        values={'operating_income':fact('operating_income','-20'),'gross_profit':fact('gross_profit','40'),'revenue':fact('revenue','100'),'revenue_total':fact('revenue_total','200')}
        self.assertEqual(calc('operating_margin_contract_revenue',values)['value'],Decimal('-.2'))
        self.assertEqual(calc('gross_margin_total_revenue',values)['value'],Decimal('.2'))
        self.assertEqual(calc('gross_margin_total_revenue',values)['semantic_review_fields'],['revenue_total'])
        values.pop('revenue')
        self.assertIsNone(calc('gross_margin_contract_revenue',values)['value'])

    def test_no_operating_income_inferred_from_net_income(self):
        values={'net_income':fact('net_income','20'),'revenue':fact('revenue','100')}
        self.assertEqual(calc('operating_margin_contract_revenue',values)['missing_fields'],['operating_income'])

    def test_duration_margin_requires_exact_start(self):
        with self.assertRaises(ValueError):calc('operating_margin_contract_revenue',{},period_start=None)

    def test_balance_subtraction_precision_and_raw_operand_trace(self):
        values={'current_assets':fact('current_assets','123456789012345678901234567890'),'current_liabilities':fact('current_liabilities','1')}
        with localcontext() as ctx:
            ctx.prec=3;r=calc('working_capital',values)
        self.assertEqual(r['value'],Decimal('123456789012345678901234567889'))
        self.assertEqual(r['inputs'][0]['raw_sha256'],'a'*64)

    def test_new_fields_stop_unsupported_adapters_before_http(self):
        class NoHttp:
            def get(self,url):raise AssertionError('no HTTP allowed')
        for field in NEW:
            s=SPECS[field];q=FactQuery(CIK,field,None if s.instant else START,END,'USD','currency',s.accounting_definition)
            for p in (YahooAssets(NoHttp(),directory=None,symbol='AAPL'),NasdaqFinancials(NoHttp(),directory=None,symbol='AAPL'),FinnhubReported(FinnhubConfig('synthetic'),transport=NoHttp())):
                with self.assertRaises(ProviderFailure) as exc:p.prepare(q)
                self.assertEqual(exc.exception.status,Status.UNSUPPORTED_FIELD)

    def test_sec_extracts_each_literal_new_tag_and_exact_instant_or_duration(self):
        class Transport:
            max_bytes=1000000
            def get(self,url):return Response(url,self.body,NOW)
        for field in NEW:
            s=SPECS[field];row=dict(end=str(END),val=123,form='10-K',accn='0000320193-26-000001',filed='2026-01-31')
            if not s.instant:row['start']=str(START)
            t=Transport();t.body=json.dumps(dict(cik=int(CIK),entityName='Synthetic',facts={'us-gaap':{s.tag:{'units':{'USD':[row]}}}})).encode()
            provider=SecCompanyFacts(t,clock=lambda:NOW)
            f=provider.fetch(FactQuery(CIK,field,None if s.instant else START,END,'USD','currency',s.accounting_definition).at(NOW))
            self.assertEqual(f.value,Decimal(123));self.assertEqual(f.accounting_definition,s.accounting_definition)

    def test_report_calculates_instant_only_liquidity_without_inferred_year_start(self):
        from dataclasses import asdict
        fields=[]
        for name,value in [('current_assets','150'),('current_liabilities','100'),('cash_equivalents','25')]:
            f=fact(name,value);q={k:getattr(f,k) for k in ('issuer_id','field','period_start','period_end','currency','unit','accounting_definition')}
            fields.append(dict(query=q,fact=asdict(f),state='collected',as_of=NOW,attempts=[dict(source='Yahoo',status='unsupported_field',attempted_at=NOW),dict(source='SEC',status='valid',attempted_at=NOW)]))
        b=json.loads(json.dumps(dict(schema_version=1,generated_at=NOW,companies=[dict(symbol='AAPL',issuer_id=CIK,scope_status='pending_scope',scope_reason='review',fields=fields)]),default=encode))
        r=build_report(b)
        self.assertEqual(r['summary']['arithmetic_results'],3);self.assertIsNone(r['companies'][0]['period_start'])
        self.assertIsNone(r['companies'][0]['total_score']);self.assertFalse(r['mvp_accepted'])
