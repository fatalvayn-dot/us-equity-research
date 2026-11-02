import json,gzip,unittest
from pathlib import Path
from dataclasses import replace,FrozenInstanceError
from datetime import date,datetime,timezone
from decimal import Decimal
from equity_research.fields import SPECS,TAGS,accounting_readiness
from equity_research.companyfacts import SecCompanyFacts
from equity_research.models import FactQuery,Fact,Source
from equity_research.providers import ProviderFailure,Status,Resolver
from equity_research.finnhub import FinnhubReported,FinnhubConfig
from equity_research.yahoo import YahooAssets
from equity_research.nasdaq_financials import NasdaqFinancials
from equity_research.batch import load_plan
from equity_research.transport import Response
from test_companyfacts import payload,Transport,req

NOW=datetime(2026,11,2,tzinfo=timezone.utc)
class FieldTests(unittest.TestCase):
 def test_original_six_definitions_unchanged(self):
  self.assertEqual(TAGS['revenue'],('RevenueFromContractWithCustomerExcludingAssessedTax',False))
  self.assertEqual(TAGS['net_income'],('NetIncomeLoss',False))
  self.assertEqual(TAGS['capital_expenditure'],('PaymentsToAcquirePropertyPlantAndEquipment',False))
  self.assertEqual(len(SPECS),9)
 def test_registry_and_specs_immutable(self):
  with self.assertRaises(TypeError):SPECS['x']=SPECS['assets']
  with self.assertRaises(FrozenInstanceError):SPECS['profit_loss'].tag='NetIncomeLoss'
 def test_new_definitions_are_distinct_and_require_review(self):
  for a,b in [('revenue','revenue_total'),('net_income','profit_loss'),('capital_expenditure','productive_asset_cash_payments')]:
   self.assertNotEqual(SPECS[a].accounting_definition,SPECS[b].accounting_definition)
   self.assertTrue(SPECS[b].requires_semantic_model_review)
 def test_sec_rejects_field_definition_mismatch(self):
  p=SecCompanyFacts(Transport(),clock=lambda:NOW)
  with self.assertRaises(ProviderFailure) as e:p._validate_specification(req(field='profit_loss',accounting_definition='us-gaap:NetIncomeLoss'))
  self.assertEqual(e.exception.status,Status.INVALID_DATA)
 def test_plan_accepts_explicit_new_fields(self):
  c=load_plan(dict(schema_version=1,companies=[dict(symbol='AAPL',issuer_id='0000320193',period_start='2025-01-01',period_end='2025-12-31',fields=['revenue_total','profit_loss','productive_asset_cash_payments'])]))[0]
  self.assertEqual([q.accounting_definition for q in c.queries],[SPECS[n].accounting_definition for n in ('revenue_total','profit_loss','productive_asset_cash_payments')])
 def test_broader_fact_cannot_fill_narrow_required_field(self):
  fact=Fact('0000320193','revenue_total',Decimal(1),Source.SEC,date(2025,1,1),date(2025,12,31),'USD','currency',NOW,NOW,'us-gaap:Revenues','https://data.sec.gov/example')
  status=accounting_readiness(['revenue'],{'revenue_total':fact})
  self.assertEqual(status['missing_fields'],['revenue']);self.assertFalse(status['investment_approved'])
 def test_wrong_fact_key_definition_detected(self):
  fact=Fact('0000320193','revenue_total',Decimal(1),Source.SEC,date(2025,1,1),date(2025,12,31),'USD','currency',NOW,NOW,'us-gaap:Revenues','https://data.sec.gov/example')
  status=accounting_readiness(['revenue'],{'revenue':fact})
  self.assertEqual(status['definition_mismatches'],['revenue'])
 def test_semantic_data_completeness_not_sector_model_validation(self):
  fact=Fact('0000320193','profit_loss',Decimal(1),Source.SEC,date(2025,1,1),date(2025,12,31),'USD','currency',NOW,NOW,'us-gaap:ProfitLoss','https://data.sec.gov/example')
  r=accounting_readiness(['profit_loss'],{'profit_loss':fact})
  self.assertEqual(r['status'],'data_complete_model_validation_pending');self.assertEqual(r['semantic_model_review_fields'],['profit_loss']);self.assertFalse(r['sector_model_supported'])
 def test_unknown_duplicate_or_empty_model_requirements_rejected(self):
  for names in ([],['x'],['profit_loss','profit_loss']):
   with self.assertRaises(ValueError):accounting_readiness(names,{})
 def test_unsupported_new_provider_fields_never_make_http(self):
  class NoNetwork:
   def get(self,url):raise AssertionError('must not query')
  for name in ('revenue_total','profit_loss','productive_asset_cash_payments'):
   q=FactQuery('0000320193',name,date(2025,1,1),date(2025,12,31),'USD','currency',SPECS[name].accounting_definition)
   providers=[YahooAssets(NoNetwork(),directory=None,symbol='AAPL'),NasdaqFinancials(NoNetwork(),directory=None,symbol='AAPL'),FinnhubReported(FinnhubConfig('synthetic'),transport=NoNetwork())]
   for provider in providers:
    with self.assertRaises(ProviderFailure) as e:provider.prepare(q)
    self.assertEqual(e.exception.status,Status.UNSUPPORTED_FIELD)
 def test_five_real_recorded_fields_retain_distinct_definitions_and_stopping(self):
  root=Path(__file__).resolve().parents[1];r=json.loads((root/'docs/evidence/distinct-accounting-fields.json').read_text())
  self.assertEqual(r['summary'],dict(new_distinct_facts=5,original_matches=5,network_requests=0))
  for row in r['observations']:
   self.assertEqual(row['fact']['accounting_definition'],SPECS[row['field']].accounting_definition)
   self.assertEqual([(a['source'],a['status']) for a in row['attempts']],[('Yahoo','unsupported_field'),('SEC','valid')])
   self.assertEqual(Decimal(row['fact']['value']),Decimal(row['original']['value']))
   self.assertFalse(row['readiness']['sector_model_supported'])
  self.assertFalse(r['old_narrow_fields_filled'])
 def test_mixed_company_or_period_inputs_not_data_complete(self):
  a=Fact('0000320193','revenue_total',Decimal(1),Source.SEC,date(2025,1,1),date(2025,12,31),'USD','currency',NOW,NOW,'us-gaap:Revenues','https://data.sec.gov/example')
  b=replace(a,field='profit_loss',accounting_definition='us-gaap:ProfitLoss')
  for changed in (replace(b,issuer_id='0000789019'),replace(b,period_start=date(2025,2,1)),replace(b,period_end=date(2025,12,30)),replace(b,currency='EUR')):
   r=accounting_readiness(['revenue_total','profit_loss'],{'revenue_total':a,'profit_loss':changed})
   self.assertEqual(r['status'],'incompatible_fact_context')
 def test_duration_definition_cannot_be_instant_input(self):
  a=Fact('0000320193','profit_loss',Decimal(1),Source.SEC,None,date(2025,12,31),'USD','currency',NOW,NOW,'us-gaap:ProfitLoss','https://data.sec.gov/example')
  self.assertEqual(accounting_readiness(['profit_loss'],{'profit_loss':a})['definition_mismatches'],['profit_loss'])
