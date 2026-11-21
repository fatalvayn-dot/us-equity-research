import json,unittest
from dataclasses import replace
from datetime import date,datetime,timedelta,timezone
from decimal import Decimal,localcontext
from pathlib import Path
from equity_research.calculations import calculate,CALCULATIONS
from equity_research.fields import SPECS
from equity_research.models import Fact,Source
from equity_research.cache import decode_fact

NOW=datetime(2026,11,2,tzinfo=timezone.utc);START=date(2025,1,1);END=date(2025,12,31);CIK='0000320193'
def fact(name,value):return Fact(CIK,name,Decimal(value),Source.SEC,START,END,'USD','currency',NOW,NOW,SPECS[name].accounting_definition,'https://data.sec.gov/recorded',raw_sha256='0'*64)
def run(name,values,**changes):
 args=dict(issuer_id=CIK,period_start=START,period_end=END,currency='USD',as_of=NOW);args.update(changes)
 return calculate(name,values,**args)
class CalculationTests(unittest.TestCase):
 def test_exact_margin_and_full_operand_provenance(self):
  r=run('net_margin_contract_revenue',{'net_income':fact('net_income','20'),'revenue':fact('revenue','100')})
  self.assertEqual(r['value'],Decimal('.2'));self.assertEqual(r['unit'],'ratio');self.assertIsNone(r['currency'])
  self.assertEqual(len(r['inputs']),2);self.assertEqual(r['inputs'][0]['raw_sha256'],'0'*64);self.assertFalse(r['investment_approved'])
 def test_missing_is_not_zero(self):
  r=run('cash_after_ppe_payments',{'operating_cash_flow':fact('operating_cash_flow','20')})
  self.assertEqual(r['status'],'pending_data');self.assertIsNone(r['value']);self.assertEqual(r['missing_fields'],['capital_expenditure'])
 def test_explicit_zero_payment_is_valid(self):
  r=run('cash_after_ppe_payments',{'operating_cash_flow':fact('operating_cash_flow','20'),'capital_expenditure':fact('capital_expenditure','0')})
  self.assertEqual(r['value'],Decimal(20));self.assertEqual(r['currency'],'USD')
 def test_negative_profit_is_not_clamped(self):
  r=run('net_margin_contract_revenue',{'net_income':fact('net_income','-20'),'revenue':fact('revenue','100')})
  self.assertEqual(r['value'],Decimal('-.2'))
 def test_nonpositive_denominator_is_not_a_ratio(self):
  for denominator in ('0','-10'):
   r=run('net_margin_contract_revenue',{'net_income':fact('net_income','1'),'revenue':fact('revenue',denominator)})
   self.assertEqual(r['status'],'nonpositive_denominator');self.assertIsNone(r['value'])
 def test_cash_payment_sign_not_guessed(self):
  r=run('cash_after_ppe_payments',{'operating_cash_flow':fact('operating_cash_flow','20'),'capital_expenditure':fact('capital_expenditure','-5')})
  self.assertEqual(r['status'],'unsupported_payment_sign')
 def test_broader_revenue_does_not_fill_contract_revenue(self):
  r=run('net_margin_contract_revenue',{'net_income':fact('net_income','20'),'revenue_total':fact('revenue_total','100')})
  self.assertEqual(r['missing_fields'],['revenue']);self.assertIsNone(r['value'])
 def test_wrong_definition_or_field_never_used(self):
  for wrong in (fact('revenue_total','100'),replace(fact('revenue','100'),accounting_definition='us-gaap:Revenues')):
   r=run('net_margin_contract_revenue',{'net_income':fact('net_income','20'),'revenue':wrong})
   self.assertEqual(r['status'],'invalid_inputs')
 def test_cross_company_currency_or_period_rejected(self):
  for bad in (replace(fact('revenue','100'),issuer_id='0000789019'),replace(fact('revenue','100'),currency='EUR'),replace(fact('revenue','100'),period_start=date(2025,2,1)),replace(fact('revenue','100'),period_end=date(2025,12,30))):
   self.assertEqual(run('net_margin_contract_revenue',{'net_income':fact('net_income','20'),'revenue':bad})['status'],'invalid_inputs')
 def test_future_observation_and_publication_cannot_leak(self):
  for bad in (replace(fact('revenue','100'),retrieved_at=NOW+timedelta(days=1)),replace(fact('revenue','100'),retrieved_at=NOW+timedelta(days=1),available_at=NOW+timedelta(days=1))):
   self.assertEqual(run('net_margin_contract_revenue',{'net_income':fact('net_income','20'),'revenue':bad})['status'],'invalid_inputs')
 def test_unproven_raw_source_is_not_a_calculation_input(self):
  r=run('net_margin_contract_revenue',{'net_income':fact('net_income','20'),'revenue':replace(fact('revenue','100'),raw_sha256=None)})
  self.assertEqual(r['rejections'][0]['reason'],'missing_raw_source_hash')
 def test_distinct_cash_definitions_stay_distinct(self):
  values={'operating_cash_flow':fact('operating_cash_flow','100'),'capital_expenditure':fact('capital_expenditure','20'),'productive_asset_cash_payments':fact('productive_asset_cash_payments','30')}
  self.assertEqual(run('cash_after_ppe_payments',values)['value'],Decimal(80))
  r=run('cash_after_productive_asset_payments',values);self.assertEqual(r['value'],Decimal(70));self.assertEqual(r['semantic_review_fields'],['productive_asset_cash_payments'])
 def test_precision_and_global_decimal_context_do_not_change_subtraction(self):
  values={'operating_cash_flow':fact('operating_cash_flow','123456789012345678901234567890'),'capital_expenditure':fact('capital_expenditure','1')}
  with localcontext() as ctx:
   ctx.prec=4;r=run('cash_after_ppe_payments',values)
  self.assertEqual(r['value'],Decimal('123456789012345678901234567889'))
 def test_unknown_calculation_naive_cutoff_or_bad_currency_rejected(self):
  for name,changes in [('x',{}),('cash_after_ppe_payments',{'as_of':NOW.replace(tzinfo=None)}),('cash_after_ppe_payments',{'currency':'usd'})]:
   with self.assertRaises(ValueError):run(name,{},**changes)
 def test_recorded_sample_recomputes_with_persisted_operands(self):
  root=Path(__file__).resolve().parents[1];report=json.loads((root/'docs/evidence/calculation-sample.json').read_text())
  self.assertEqual(report['summary'],dict(requested=64,calculated=24,pending=40));self.assertFalse(report['sector_model_accepted'])
  for r in report['calculations']:
   if r['status']!='calculated_arithmetic_only':continue
   values={f['field']:decode_fact(f) for f in r['inputs']}
   got=calculate(r['calculation'],values,issuer_id=r['issuer_id'],period_start=date.fromisoformat(r['period_start']),period_end=date.fromisoformat(r['period_end']),currency=r['input_currency'],as_of=datetime.fromisoformat(r['as_of']))
   self.assertEqual(got['value'],Decimal(r['value']));self.assertFalse(got['scope_approved'])
