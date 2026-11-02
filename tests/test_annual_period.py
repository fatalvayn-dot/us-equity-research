import gzip,json,unittest
from pathlib import Path
from datetime import date
from equity_research.annual_period import annual_period
from equity_research.providers import ProviderFailure

CIK='0000320193';END=date(2026,9,26)
def document(start='2025-09-28',focus='FY',form='10-K',end='2026-09-26',dimension='',period_text='2026-09-26'):
 return f'''<html xmlns:dei="http://xbrl.sec.gov/dei/2026"><xbrli:context id="d"><xbrli:entity><xbrli:identifier scheme="http://www.sec.gov/CIK">{CIK}</xbrli:identifier>{dimension}</xbrli:entity><xbrli:period><xbrli:startDate>{start}</xbrli:startDate><xbrli:endDate>{end}</xbrli:endDate></xbrli:period></xbrli:context><ix:nonNumeric name="dei:DocumentType" contextRef="d">{form}</ix:nonNumeric><ix:nonNumeric name="dei:DocumentFiscalPeriodFocus" contextRef="d">{focus}</ix:nonNumeric><ix:nonNumeric name="dei:DocumentPeriodEndDate" contextRef="d">{period_text}</ix:nonNumeric></html>'''.encode()
def parse(body,**changes):
 args=dict(cik=CIK,report_end=END,document_type='10-K');args.update(changes)
 return annual_period(body,**args)

class AnnualPeriodTests(unittest.TestCase):
 def test_explicit_week_calendar_start_retained(self):
  r=parse(document());self.assertEqual(r['period_start'],'2025-09-28');self.assertFalse(r['calendar_start_inferred']);self.assertFalse(r['scope_approved'])
 def test_quarterly_focus_or_form_not_annual(self):
  for b in (document(focus='Q4'),document(form='10-Q')):
   with self.assertRaises(ProviderFailure):parse(b)
 def test_dimension_or_wrong_issuer_rejected(self):
  for b in (document(dimension='<xbrli:segment><xbrldi:explicitMember>ClassA</xbrldi:explicitMember></xbrli:segment>'),document().replace(CIK.encode(),b'0000789019')):
   with self.assertRaises(ProviderFailure):parse(b)
 def test_no_start_is_not_calendar_inferred(self):
  b=document().replace(b'<xbrli:startDate>2025-09-28</xbrli:startDate>',b'')
  with self.assertRaises(ProviderFailure):parse(b)
 def test_reversed_oversized_or_wrong_period_rejected(self):
  for b in (document(start='2027-01-01'),document(start='2020-01-01'),document(end='2025-09-26'),document(period_text='2025-09-26')):
   with self.assertRaises(ProviderFailure):parse(b)
 def test_nil_document_type_not_accepted(self):
  with self.assertRaises(ProviderFailure):parse(document().replace(b'name="dei:DocumentType"',b'xsi:nil="true" name="dei:DocumentType"'))
 def test_context_facts_must_not_be_cross_joined(self):
  with self.assertRaises(ProviderFailure):parse(document().replace(b'name="dei:DocumentFiscalPeriodFocus" contextRef="d"',b'name="dei:DocumentFiscalPeriodFocus" contextRef="other"'))
 def test_conflicting_duration_contexts_rejected(self):
  b=document();extra=document(start='2025-10-01').split(b'>',1)[1].rsplit(b'</html>',1)[0].replace(b'id="d"',b'id="e"').replace(b'contextRef="d"',b'contextRef="e"')
  with self.assertRaises(ProviderFailure):parse(b.replace(b'</html>',extra+b'</html>'))
 def test_unapproved_namespace_rejected(self):
  with self.assertRaises(ProviderFailure):parse(document().replace(b'http://xbrl.sec.gov/dei/2026',b'http://evil.example/dei/2026'))
 def test_truncated_context_rejected(self):
  with self.assertRaises(ProviderFailure):parse(document().replace(b'</xbrli:context>',b''))
 def test_nested_nontracked_fact_does_not_truncate_parent_date(self):
  b=document().replace(b'name="dei:DocumentPeriodEndDate" contextRef="d">2026-09-26',b'name="dei:DocumentPeriodEndDate" contextRef="d" format="ixt:date-monthname-day-year-en"><ix:nonNumeric name="dei:CurrentFiscalYearEndDate" contextRef="d">September 26</ix:nonNumeric>, 2026')
  self.assertEqual(parse(b)['period_start'],'2025-09-28')
 def test_unsupported_continuation_not_silently_accepted(self):
  b=document().replace(b'name="dei:DocumentPeriodEndDate"',b'continuedAt="missing" name="dei:DocumentPeriodEndDate"')
  with self.assertRaises(ProviderFailure):parse(b)
 def test_recorded_annual_contexts_and_common_classes(self):
  from equity_research.filing_metadata import filing_security_metadata
  root=Path(__file__).resolve().parents[1]
  report=json.loads((root/'docs/evidence/annual-filings-live.json').read_text())
  self.assertEqual(len(report['companies']),3)
  for r in report['companies']:
   body=gzip.decompress((root/r['source_evidence']['fixture']).read_bytes())
   args=dict(cik=r['issuer_id'],report_end=date.fromisoformat(r['annual']['report_end']),document_type=r['annual']['form'])
   result=annual_period(body,**args)
   self.assertEqual(result['period_end'],r['annual']['report_end'])
   self.assertEqual(result['raw_sha256'],r['source_evidence']['sha256'])
   self.assertTrue(filing_security_metadata(body,symbol=r['symbol'],**args)['explicit_common_share_title'])
 def test_source_period_plan_keeps_instant_and_duration_dates_distinct(self):
  from equity_research.batch import load_plan
  root=Path(__file__).resolve().parents[1]
  plan=json.loads((root/'docs/evidence/annual-three-plan.json').read_text())
  companies=load_plan(plan);self.assertEqual(len(companies),3)
  for c in companies:
   self.assertEqual(c.scope_status,'pending_scope');self.assertEqual(len(c.queries),6)
   for q in c.queries:
    self.assertEqual(q.period_start is None,q.field in ('assets','liabilities'))
