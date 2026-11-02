import tempfile,unittest,json
from datetime import date,datetime,timedelta,timezone
from pathlib import Path
from equity_research.documents import FilingStore,DocumentRunner,document_key
from equity_research.batch import RunBusy
from equity_research import __version__
from equity_research.providers import ProviderFailure,Status
from equity_research.transport import Response
from test_annual_period import document

NOW=datetime(2026,11,2,tzinfo=timezone.utc)
def row(cik='0000320193',symbol='AAPL'):
 accession='0000320193-26-000001';name='annual.htm'
 return dict(symbol=symbol,issuer_id=cik,annual=dict(accession=accession,primary_document=name,form='10-K',report_end='2026-09-26',filed_on='2026-10-30',source_url=f'https://www.sec.gov/Archives/edgar/data/{int(cik)}/{accession.replace("-","")}/{name}'))
class Transport:
 def __init__(self):self.calls=[];self.interrupt_at=None;self.error=False
 def get(self,url):
  self.calls.append(url)
  if len(self.calls)==self.interrupt_at:raise KeyboardInterrupt()
  if self.error:raise ProviderFailure(Status.RATE_LIMIT,http_status=429)
  return Response(url,document(),NOW)
class DocumentTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.path=Path(self.tmp.name)/'db.sqlite';self.store=FilingStore(self.path);self.transport=Transport();self.now=NOW
  self.runner=DocumentRunner(self.store,self.transport,clock=lambda:self.now)
 def tearDown(self):self.store.close();self.tmp.cleanup()
 def test_restart_reuses_original_bytes_and_recomputes_parser_outcomes(self):
  a=self.runner.run([row()],max_new_documents=1);self.store.close();self.store=FilingStore(self.path)
  b=DocumentRunner(self.store,self.transport,clock=lambda:self.now).run([row()],max_new_documents=0)
  self.assertEqual(len(self.transport.calls),1);self.assertEqual(b['summary']['reused_documents'],1)
  self.assertEqual(a['companies'][0]['period'],b['companies'][0]['period'])
  self.assertEqual(b['companies'][0]['source_evidence']['retrieved_at'],NOW.isoformat())
  self.assertFalse(b['scope_approved'])
 def test_bounded_work_still_reports_entire_queue(self):
  r=self.runner.run([row(),row('0000789019','MSFT')],max_new_documents=1)
  self.assertEqual(len(r['companies']),2);self.assertEqual(r['companies'][1]['state'],'not_started');self.assertEqual(len(self.transport.calls),1)
 def test_interrupt_preserves_first_document_and_releases_lease(self):
  self.transport.interrupt_at=2
  with self.assertRaises(KeyboardInterrupt):self.runner.run([row(),row('0000789019','MSFT')],max_new_documents=2)
  self.assertIsNotNone(self.store.get(row()['issuer_id'],row()['annual'],NOW,timedelta(hours=6)))
  self.assertIsNotNone(self.store.read('document-outcome:'+__version__+':0000320193'))
  self.transport.interrupt_at=None
  r=self.runner.run([row()],max_new_documents=0);self.assertEqual(r['summary']['reused_documents'],1)
 def test_corrupt_raw_checkpoint_never_accepted(self):
  self.runner.run([row()],max_new_documents=1)
  with self.store.db:self.store.db.execute("UPDATE filing_documents_v1 SET sha256='wrong'")
  r=self.runner.run([row()],max_new_documents=1)
  self.assertEqual(len(self.transport.calls),2);self.assertEqual(r['checkpoint_events'][0]['event'],'invalid_document_checkpoint')
 def test_expired_document_does_not_renew_observation_on_read(self):
  self.runner.run([row()],max_new_documents=1);self.now+=timedelta(hours=7)
  r=self.runner.run([row()],max_new_documents=0)
  self.assertEqual(r['companies'][0]['state'],'not_started');self.assertEqual(len(self.transport.calls),1)
 def test_failure_is_typed_and_persisted_without_invented_fact(self):
  self.transport.error=True;r=self.runner.run([row()],max_new_documents=1)
  self.assertEqual(r['companies'][0]['state'],'rate_limit');self.assertNotIn('period',r['companies'][0])
  saved=self.store.read('document-outcome:'+__version__+':0000320193');self.assertEqual(saved['http_status'],429)
 def test_active_lease_blocks_duplicate_http(self):
  owner=self.store.acquire(NOW,timedelta(minutes=15))
  try:
   with self.assertRaises(RunBusy):self.runner.run([row()],max_new_documents=1)
   self.assertEqual(self.transport.calls,[])
  finally:self.store.release(owner)
 def test_lost_owner_cannot_write_raw_document(self):
  owner=self.store.acquire(NOW,timedelta(seconds=1));new=self.store.acquire(NOW+timedelta(seconds=2),timedelta(minutes=15))
  try:
   with self.assertRaises(RunBusy):self.store.put(row()['issuer_id'],row()['annual'],Response(row()['annual']['source_url'],b'x',NOW),owner,NOW+timedelta(seconds=3),timedelta(minutes=15))
  finally:self.store.release(new)
 def test_origin_and_path_validation_before_any_http(self):
  for field,value in [('source_url','https://evil.example/x'),('primary_document','../x.htm'),('filed_on','2027-01-01')]:
   r=row();r['annual'][field]=value
   with self.assertRaises(ValueError):self.runner.run([r],max_new_documents=1)
  self.assertEqual(self.transport.calls,[])
 def test_missing_annual_and_unsupported_format_are_separate(self):
  r=row();r['annual']=None
  s=row('0000789019','MSFT');s['annual']['primary_document']='annual.paper';s['annual']['source_url']=s['annual']['source_url'].replace('annual.htm','annual.paper')
  out=self.runner.run([r,s],max_new_documents=3)
  self.assertEqual([x['state'] for x in out['companies']],['no_annual_in_recent_window','unsupported_document_format']);self.assertEqual(self.transport.calls,[])
 def test_duplicate_sample_rejected(self):
  with self.assertRaises(ValueError):self.runner.run([row(),row()],max_new_documents=1)
 def test_period_success_not_registered_class_or_scope_success(self):
  r=self.runner.run([row()],max_new_documents=1)['companies'][0]
  self.assertIn('period',r);self.assertEqual(r['registered_share_status'],'invalid_data');self.assertFalse(r['scope_approved'])

class RecordedDocumentBatchTests(unittest.TestCase):
 def test_eight_primary_sources_replay_without_changing_observation(self):
  import gzip
  from equity_research.annual_period import annual_period
  root=Path(__file__).resolve().parents[1]
  first=json.loads((root/'docs/evidence/annual-document-batch.json').read_text())
  resumed=json.loads((root/'docs/evidence/annual-document-resume.json').read_text())
  self.assertEqual(first['summary']['new_documents'],5);self.assertEqual(first['summary']['reused_documents'],3)
  self.assertEqual(resumed['transport_get_calls'],0);self.assertEqual(resumed['summary']['reused_documents'],8)
  self.assertEqual(len(resumed['companies']),100)
  matched=0
  for c in resumed['companies']:
   if 'source_evidence' not in c:continue
   matched+=1;e=c['source_evidence'];body=gzip.decompress((root/e['fixture']).read_bytes())
   result=annual_period(body,cik=c['issuer_id'],report_end=date.fromisoformat(c['annual']['report_end']),document_type=c['annual']['form'])
   self.assertEqual(result['raw_sha256'],e['sha256']);self.assertEqual(result,c['period'])
   self.assertFalse(c['scope_approved'])
  self.assertEqual(matched,8)
 def test_extended_plan_only_uses_corroborated_periods(self):
  from equity_research.batch import load_plan
  root=Path(__file__).resolve().parents[1];plan=json.loads((root/'docs/evidence/annual-eight-plan.json').read_text())
  companies=load_plan(plan);self.assertEqual(len(companies),8)
  self.assertEqual(sum(len(c.queries) for c in companies),48)
  self.assertTrue(all(c.scope_status=='pending_scope' for c in companies))
