import json,tempfile,unittest
from pathlib import Path
from dataclasses import replace
from datetime import datetime,timedelta,timezone
from equity_research.submissions import SecSubmissions,parse_submissions,submissions_url
from equity_research.providers import ProviderFailure,Status
from equity_research.transport import Response

CIK='0000320193';NOW=datetime(2026,11,2,tzinfo=timezone.utc)
def payload():
 return dict(cik='320193',name='Synthetic Co',entityType='operating',sic='3571',sicDescription='Synthetic',tickers=['AAPL'],fiscalYearEnd='0930',
    filings=dict(files=[{'name':'older-history.json'}],recent=dict(accessionNumber=['0000320193-26-000001'],form=['10-K'],filingDate=['2026-10-30'],
    reportDate=['2026-09-26'],primaryDocument=['annual.htm'],acceptanceDateTime=['2026-10-30T12:00:00.000Z'])))
def response(p=None):return Response(submissions_url(CIK),json.dumps(p or payload()).encode(),NOW)

class SubmissionsTests(unittest.TestCase):
 def test_identity_provenance_and_explicit_end_only(self):
  r=response();s=parse_submissions(r,CIK);f=s.latest_annual()
  self.assertEqual(s.raw_sha256,r.sha256);self.assertEqual(f.report_end.isoformat(),'2026-09-26')
  self.assertEqual(s.entity_type_label,'operating');self.assertIn('/320193/000032019326000001/annual.htm',f.source_url)
  self.assertEqual(s.readiness('AAPL'),'metadata_available_legal_type_pending')
  self.assertEqual(s.older_file_count,1);self.assertFalse(hasattr(f,'period_start'))
 def test_bad_request_identity(self):
  for cik in ('320193','0000000000','../320193','３２０１９３'):
   with self.assertRaises(ValueError):submissions_url(cik)
 def test_response_cik_mismatch_typed(self):
  p=payload();p['cik']=1
  with self.assertRaises(ProviderFailure) as e:parse_submissions(response(p),CIK)
  self.assertEqual(e.exception.status,Status.SYMBOL_MISMATCH)
 def test_bad_cik_types(self):
  for cik in (True,3.0,'bad'):
   p=payload();p['cik']=cik
   with self.assertRaises(ProviderFailure):parse_submissions(response(p),CIK)
 def test_origin_and_naive_time_rejected(self):
  for r in (replace(response(),url='https://evil.example/x'),replace(response(),retrieved_at=NOW.replace(tzinfo=None))):
   with self.assertRaises(ProviderFailure):parse_submissions(r,CIK)
 def test_column_drift_never_truncates(self):
  for key in ('form','extra'):
   p=payload();p['filings']['recent'][key]=[]
   with self.assertRaises(ProviderFailure):parse_submissions(response(p),CIK)
 def test_unsafe_primary_documents_rejected(self):
  for name in ('../annual.htm','a/b.htm','https://evil.example/a.htm','a.htm?x=1','%2e%2e.htm'):
   p=payload();p['filings']['recent']['primaryDocument']=[name]
   with self.assertRaises(ProviderFailure):parse_submissions(response(p),CIK)
 def test_future_or_invalid_period_rejected(self):
  for key,value in (('reportDate','2026-11-01'),('filingDate','2027-01-01'),('reportDate','bad')):
   p=payload();p['filings']['recent'][key]=[value]
   with self.assertRaises(ProviderFailure):parse_submissions(response(p),CIK)
 def test_no_annual_is_recent_window_only(self):
  p=payload();p['filings']['recent']['form']=['8-K']
  self.assertIsNone(parse_submissions(response(p),CIK).latest_annual())
 def test_amendment_is_not_a_new_annual_period(self):
  p=payload();p['filings']['recent']['form']=['10-K/A']
  self.assertIsNone(parse_submissions(response(p),CIK).latest_annual())
 def test_foreign_annual_forms_kept_without_gaap_guess(self):
  for form in ('20-F','40-F'):
   p=payload();p['filings']['recent']['form']=[form]
   self.assertEqual(parse_submissions(response(p),CIK).latest_annual().form,form)
 def test_duplicate_accession_rejected(self):
  p=payload()
  for k,v in p['filings']['recent'].items():v.extend(v.copy())
  with self.assertRaises(ProviderFailure):parse_submissions(response(p),CIK)
 def test_unknown_entity_type_never_approved(self):
  p=payload();p['entityType']='unknown';p['sic']='6798'
  s=parse_submissions(response(p),CIK)
  self.assertEqual(s.entity_type_label,'unknown');self.assertEqual(s.sic_label,'6798')
  self.assertEqual(s.readiness('WRONG'),'symbol_mismatch')
 def test_duplicate_json_keys_rejected(self):
  r=replace(response(),body=b'{"cik":1,"cik":2}')
  with self.assertRaises(ProviderFailure):parse_submissions(r,CIK)
 def test_cache_retains_original_observation_and_survives_restart(self):
  class T:
   calls=0
   def get(self,url):self.calls+=1;return response()
  with tempfile.TemporaryDirectory() as tmp:
   path=Path(tmp)/'db.sqlite';t=T();a=SecSubmissions(t,cache_path=path,clock=lambda:NOW)
   first=a.fetch(CIK);a.close();b=SecSubmissions(t,cache_path=path,clock=lambda:NOW+timedelta(hours=5))
   try:
    second=b.fetch(CIK);self.assertTrue(second.cached);self.assertEqual(second.retrieved_at,first.retrieved_at);self.assertEqual(t.calls,1)
   finally:b.close()
 def test_corrupt_cache_falls_back_and_is_not_accepted(self):
  class T:
   calls=0
   def get(self,url):self.calls+=1;return response()
  with tempfile.TemporaryDirectory() as tmp:
   t=T();a=SecSubmissions(t,cache_path=Path(tmp)/'db.sqlite',clock=lambda:NOW)
   try:
    a.fetch(CIK)
    with a.db:a.db.execute("UPDATE submissions_v1 SET sha256='bad'")
    a.fetch(CIK);self.assertEqual(t.calls,2);self.assertEqual(a.events[0]['event'],'invalid_metadata_checkpoint')
   finally:a.close()
 def test_stale_cache_does_not_refresh_observation_on_read(self):
  class T:
   calls=0
   def get(self,url):self.calls+=1;return response()
  with tempfile.TemporaryDirectory() as tmp:
   t=T();clock=[NOW];a=SecSubmissions(t,cache_path=Path(tmp)/'db.sqlite',clock=lambda:clock[0])
   try:
    a.fetch(CIK);clock[0]+=timedelta(hours=7);s=a.fetch(CIK)
    self.assertEqual(t.calls,2);self.assertEqual(s.retrieved_at,NOW);self.assertFalse(s.cached)
   finally:a.close()
 def test_legacy_paper_metadata_retained_as_unsupported_not_html(self):
  p=payload();p['filings']['recent']['primaryDocument']=['9999999997-02-044234.paper']
  f=parse_submissions(response(p),CIK).latest_annual()
  self.assertEqual(f.document_format,'unsupported')
 def test_latest_annual_selected_by_explicit_end_not_array_position(self):
  p=payload();r=p['filings']['recent']
  for k,v in r.items():v.append(v[0])
  r['accessionNumber'][0]='0000320193-25-000001';r['reportDate'][0]='2025-09-27';r['filingDate'][0]='2025-10-30'
  self.assertEqual(parse_submissions(response(p),CIK).latest_annual().report_end.isoformat(),'2026-09-26')

class RecordedSampleTests(unittest.TestCase):
 def test_all_100_recorded_responses_match_exact_issuer_and_explicit_period(self):
  import gzip
  root=Path(__file__).resolve().parents[1]
  report=json.loads((root/'docs/evidence/sample100-submissions-live.json').read_text())
  self.assertEqual(len(report['companies']),100)
  for row in report['companies']:
   self.assertEqual(row['status'],'metadata_available_legal_type_pending')
   meta=row['snapshot']
   r=Response(meta['source_url'],gzip.decompress((root/row['fixture']).read_bytes()),datetime.fromisoformat(meta['retrieved_at']))
   self.assertEqual(r.sha256,meta['raw_sha256'])
   s=parse_submissions(r,row['issuer_id']);self.assertEqual(s.readiness(row['symbol']),row['status'])
   annual=s.latest_annual()
   self.assertEqual(annual.report_end.isoformat() if annual else None,row['annual']['report_end'] if row['annual'] else None)
   self.assertIsNone(row['period_start'])
  self.assertFalse(report['legal_type_approved']);self.assertFalse(report['hundred_company_accepted'])
 def test_draft_plan_uses_only_exact_report_ends_and_instant_queries(self):
  from equity_research.batch import load_plan
  root=Path(__file__).resolve().parents[1]
  plan=json.loads((root/'docs/evidence/sample-annual-end-plan.json').read_text())
  companies=load_plan(plan)
  self.assertEqual(len(companies),98);self.assertEqual(len(plan['pending_companies']),2)
  for c in companies:
   self.assertEqual(c.scope_status,'pending_scope')
   self.assertEqual([q.field for q in c.queries],['assets','liabilities'])
   self.assertTrue(all(q.period_start is None for q in c.queries))
