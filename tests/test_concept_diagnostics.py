import gzip,json,unittest
from datetime import date
from pathlib import Path
from equity_research.concept_diagnostics import inspect_concepts

CIK='0000320193';CONCEPT='us-gaap:NetIncomeLoss'
def body(value='12',unit='iso4217:USD',dimension='',start='2025-01-01',extra='',attrs=''):
 return f'''<html xmlns:ixt="http://www.xbrl.org/inlineXBRL/transformation/2020-02-12" xmlns:us-gaap="http://fasb.org/us-gaap/2025" xmlns:iso4217="http://www.xbrl.org/2003/iso4217"><xbrli:context id="c"><xbrli:entity><xbrli:identifier scheme="http://www.sec.gov/CIK">{CIK}</xbrli:identifier>{dimension}</xbrli:entity><xbrli:period><xbrli:startDate>{start}</xbrli:startDate><xbrli:endDate>2025-12-31</xbrli:endDate></xbrli:period></xbrli:context><xbrli:unit id="u"><xbrli:measure>{unit}</xbrli:measure></xbrli:unit><ix:nonFraction name="{CONCEPT}" contextRef="c" unitRef="u" format="ixt:num-dot-decimal" {attrs}>{value}</ix:nonFraction>{extra}</html>'''.encode()
def scan(b,**changes):
 args=dict(cik=CIK,concepts=[CONCEPT],period_start=date(2025,1,1),period_end=date(2025,12,31));args.update(changes)
 return inspect_concepts(b,**args)['concepts'][0]
class ConceptTests(unittest.TestCase):
 def test_exact_duration_scale_and_sign(self):
  r=scan(body('1,234.5',attrs='scale="6" sign="-"'));self.assertEqual(r['value'],'-1234500000.0');self.assertEqual(r['currency'],'USD')
 def test_dimensional_concept_is_not_consolidated_revenue(self):
  r=scan(body(dimension='<xbrli:segment><xbrldi:explicitMember>Segment</xbrldi:explicitMember></xbrli:segment>'))
  self.assertEqual(r['status'],'dimensional_only');self.assertIsNone(r['value'])
 def test_wrong_start_and_identity_do_not_match(self):
  self.assertEqual(scan(body(start='2025-02-01'))['status'],'period_or_scope_mismatch')
  self.assertEqual(scan(body().replace(CIK.encode(),b'0000789019'))['status'],'period_or_scope_mismatch')
 def test_absent_concept_not_mapped_to_an_alternate(self):
  r=scan(body().replace(b'us-gaap:NetIncomeLoss',b'us-gaap:ProfitLoss'))
  self.assertEqual(r['status'],'concept_not_disclosed');self.assertIsNone(r['value'])
 def test_conflicting_values_not_selected(self):
  extra=f'<ix:nonFraction name="{CONCEPT}" contextRef="c" unitRef="u">13</ix:nonFraction>'
  self.assertEqual(scan(body(extra=extra))['status'],'ambiguous_original_values')
 def test_unsupported_duplicate_cannot_be_hidden_by_one_parseable_value(self):
  extra=f'<ix:nonFraction name="{CONCEPT}" contextRef="c" unitRef="u" format="unsupported">13</ix:nonFraction>'
  r=scan(body(extra=extra));self.assertEqual(r['status'],'unsupported_numeric_or_unit');self.assertIsNone(r['value'])
 def test_nil_continuation_bad_grouping_or_missing_unit_not_zero(self):
  for b in (body(attrs='xsi:nil="true"'),body(attrs='continuedAt="elsewhere"'),body('12,34'),body(unit='iso4217:EUR'),body('-')):
   self.assertEqual(scan(b)['status'],'unsupported_numeric_or_unit')
 def test_large_decimal_not_rounded_to_default_context(self):
  text='1234567890123456789012345678901234567890'
  self.assertEqual(scan(body(text))['value'],text)
 def test_source_namespaces_must_be_real(self):
  for b in (body().replace(b'http://fasb.org/us-gaap/2025',b'http://evil.example/2025'),body().replace(b'http://www.xbrl.org/2003/iso4217',b'http://evil.example/currency')):
   with self.assertRaises(ValueError):scan(b)
 def test_duplicate_conflicting_context_rejected(self):
  extra='<xbrli:context id="c"><xbrli:entity></xbrli:entity></xbrli:context>'
  with self.assertRaises(ValueError):scan(body(extra=extra))
 def test_truncated_numeric_fact_rejected(self):
  with self.assertRaises(ValueError):scan(body().replace(b'</ix:nonFraction>',b''))
 def test_instant_query_never_takes_duration(self):
  self.assertEqual(scan(body(),period_start=None)['status'],'period_or_scope_mismatch')
 def test_original_eight_company_duration_reconciliation(self):
  root=Path(__file__).resolve().parents[1];r=json.loads((root/'docs/evidence/original-concept-diagnostics.json').read_text())
  self.assertEqual(r['summary'],dict(duration_checks=32,matched=27,missing_collected=5,unresolved=0,mismatched=0))
  for c in r['companies']:
   e=c['source_evidence'];b=gzip.decompress((root/e['fixture']).read_bytes())
   current=inspect_concepts(b,cik=c['issuer_id'],concepts=[x['concept'] for x in c['concepts']],period_start=date.fromisoformat(c['period_start']),period_end=date.fromisoformat(c['period_end']))
   self.assertEqual(current['raw_sha256'],e['sha256']);self.assertEqual(current['concepts'],c['concepts'])
 def test_amzn_identity_candidate_never_becomes_accepted_liabilities(self):
  root=Path(__file__).resolve().parents[1];r=json.loads((root/'docs/evidence/original-concept-diagnostics.json').read_text())
  candidate=r['amzn_identity_diagnostic']['arithmetic_candidate']
  self.assertEqual(candidate['value'],'406977000000');self.assertFalse(candidate['accepted_as_liabilities'])
  self.assertFalse(r['automatic_substitution']);self.assertEqual(r['new_network_requests'],0)

 def test_unverified_numeric_transform_namespace_does_not_decode(self):
  b=body().replace(b'http://www.xbrl.org/inlineXBRL/transformation/2020-02-12',b'http://evil.example/transform')
  self.assertEqual(scan(b)['status'],'unsupported_numeric_or_unit')
 def test_missing_context_or_unit_ids_rejected(self):
  for b in (body().replace(b'id="c"',b''),body().replace(b'id="u"',b'')):
   with self.assertRaises(ValueError):scan(b)
