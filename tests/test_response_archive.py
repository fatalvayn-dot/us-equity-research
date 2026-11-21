import tempfile,unittest
from pathlib import Path
from datetime import datetime,timedelta,timezone
from equity_research.response_archive import ResponseArchive,ArchivedTransport,public_url
from equity_research.transport import Response
from equity_research.providers import ProviderFailure,Status
from test_sec_transport import Opener,FakeResponse,Clock,DIRECTORY_URL

NOW=datetime(2026,11,2,tzinfo=timezone.utc)
class ArchiveTests(unittest.TestCase):
 def setUp(self):self.tmp=tempfile.TemporaryDirectory();self.path=Path(self.tmp.name)/'db.sqlite';self.archive=ResponseArchive(self.path)
 def tearDown(self):self.archive.close();self.tmp.cleanup()
 def test_exact_bytes_and_original_observation_survive_restart(self):
  r=Response(DIRECTORY_URL,b'original\x00bytes',NOW);self.archive.record(r);self.archive.close();self.archive=ResponseArchive(self.path)
  restored=self.archive.get(r.url,r.sha256,NOW);self.assertEqual(restored,r)
  self.assertIsNone(self.archive.get(r.url,r.sha256,NOW+timedelta(seconds=1)))
 def test_same_body_multiple_observations_no_timestamp_refresh(self):
  a=Response(DIRECTORY_URL,b'x',NOW);b=Response(a.url,a.body,NOW+timedelta(hours=1))
  self.archive.record(a);self.archive.record(b);self.archive.record(a)
  self.assertEqual(len(self.archive.observations()),2)
  self.assertEqual(self.archive.db.execute('SELECT COUNT(*) FROM response_bodies_v1').fetchone()[0],1)
  self.assertEqual(self.archive.get(a.url,a.sha256).retrieved_at,NOW)
 def test_corrupt_body_is_rejected_on_read_and_record(self):
  r=Response(DIRECTORY_URL,b'x',NOW);self.archive.record(r)
  with self.archive.db:self.archive.db.execute("UPDATE response_bodies_v1 SET body=X'79'")
  with self.assertRaises(ValueError):self.archive.get(r.url,r.sha256,NOW)
  with self.assertRaises(ValueError):self.archive.record(r)
 def test_sensitive_urls_never_stored(self):
  for suffix in ('?token=x','?api_key=x','?access-token=x','?crumb=x','?password=x','?key='):
   with self.assertRaises(ValueError):self.archive.record(Response(DIRECTORY_URL+suffix,b'x',NOW))
  self.assertEqual(self.archive.observations(),[])
 def test_origins_userinfo_and_fragments_rejected(self):
  for url in ('https://finnhub.io/api','https://evil.example/x','http://www.sec.gov/x','https://u:p@www.sec.gov/x',DIRECTORY_URL+'#secret'):
   with self.assertRaises(ValueError):public_url(url)
 def test_naive_observation_not_stored(self):
  with self.assertRaises(ValueError):self.archive.record(Response(DIRECTORY_URL,b'x',NOW.replace(tzinfo=None)))
 def test_authenticated_transport_cannot_be_archived(self):
  with self.assertRaises(ValueError):ArchivedTransport(archive=self.archive,user_agent='test',allowed_hosts={'finnhub.io'},auth_headers={'X-Finnhub-Token':'synthetic'})
 def test_public_success_recorded_only_after_transport_success(self):
  opener=Opener(FakeResponse());clock=Clock()
  h=ArchivedTransport(archive=self.archive,user_agent='test',allowed_hosts={'www.sec.gov'},opener=opener,clock=lambda:NOW,monotonic=clock.monotonic,sleep=clock.sleep)
  r=h.get(DIRECTORY_URL);self.assertEqual(self.archive.get(r.url,r.sha256,NOW),r)
 def test_archive_failure_distinct_from_source_api_error(self):
  opener=Opener(FakeResponse());clock=Clock();self.archive.close()
  h=ArchivedTransport(archive=self.archive,user_agent='test',allowed_hosts={'www.sec.gov'},opener=opener,clock=lambda:NOW,monotonic=clock.monotonic,sleep=clock.sleep)
  with self.assertRaises(ProviderFailure) as e:h.get(DIRECTORY_URL)
  self.assertEqual(e.exception.status,Status.EVIDENCE_ERROR)
 def test_credential_url_rejected_before_network(self):
  opener=Opener(FakeResponse())
  h=ArchivedTransport(archive=self.archive,user_agent='test',allowed_hosts={'www.sec.gov'},opener=opener)
  with self.assertRaises(ValueError):h.get(DIRECTORY_URL+'?apiKey=synthetic')
  self.assertEqual(opener.calls,[])
 def test_sec_disk_snapshot_archived_without_network_or_time_refresh(self):
  import gzip
  from equity_research.response_archive import ArchivedCompanyFacts
  from equity_research.companyfacts import companyfacts_url
  root=Path(__file__).resolve().parents[1]
  body=gzip.decompress((root/'tests/fixtures/companyfacts-expanded/0000320193.json.gz').read_bytes())
  observed=NOW-timedelta(minutes=5);r=Response(companyfacts_url('0000320193'),body,observed)
  folder=Path(self.tmp.name)/'sec';folder.mkdir()
  import json
  (folder/'0000320193.json').write_text(json.dumps(dict(url=r.url,body=body.decode(),sha256=r.sha256,retrieved_at=observed.isoformat())))
  class NoNetwork:
   max_bytes=16000000
   def get(self,url):raise AssertionError('no HTTP')
  provider=ArchivedCompanyFacts(NoNetwork(),archive=self.archive,cache_dir=folder,clock=lambda:NOW)
  provider.snapshot('0000320193')
  self.assertEqual(self.archive.get(r.url,r.sha256,observed),r)

class RecordedCoverageTests(unittest.TestCase):
 def test_all_43_facts_have_exact_main_identity_and_unit_source_bytes(self):
  import gzip,json
  root=Path(__file__).resolve().parents[1]
  manifest=json.loads((root/'docs/evidence/financial-response-manifest.json').read_text())['observations']
  with tempfile.TemporaryDirectory() as tmp:
   archive=ResponseArchive(Path(tmp)/'db.sqlite')
   try:
    for row in manifest:
     r=Response(row['url'],gzip.decompress((root/row['fixture']).read_bytes()),datetime.fromisoformat(row['retrieved_at']))
     self.assertEqual(r.sha256,row['sha256']);archive.record(r)
    coverage=json.loads((root/'docs/evidence/financial-response-coverage.json').read_text())
    self.assertTrue(coverage['all_references_archived']);self.assertEqual(len(coverage['facts']),43)
    for fact in coverage['facts']:
     for reference in fact['references']:self.assertIsNotNone(archive.get(reference['url'],reference['sha256'],datetime.fromisoformat(reference['observed_at'])))
   finally:archive.close()
 def test_original_balance_checks_keep_one_unresolved_separate(self):
  import json
  root=Path(__file__).resolve().parents[1];report=json.loads((root/'docs/evidence/eight-original-balances.json').read_text())
  self.assertEqual(report['summary'],dict(checks=16,matched=15,unresolved=1));self.assertFalse(report['scope_approved'])
  pending=[r for r in report['checks'] if r['status']!='matched']
  self.assertEqual([(r['symbol'],r['field']) for r in pending],[('AMZN','liabilities')])
