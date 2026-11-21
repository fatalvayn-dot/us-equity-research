"""Bounded resumable annual-source collection; scope/financial acceptance stays pending."""
import argparse,gzip,json,os,tempfile
from datetime import datetime,timezone,timedelta
from pathlib import Path
from equity_research.documents import FilingStore,DocumentRunner
from equity_research.transport import HttpTransport,Response

parser=argparse.ArgumentParser();parser.add_argument('--user-agent',required=True);parser.add_argument('--max-new-documents',type=int,default=5)
parser.add_argument('--output',default='docs/evidence/annual-document-batch.json')
args=parser.parse_args()
if not 0<=args.max_new_documents<=100:parser.error("max-new-documents must be 0..100")
root=Path(__file__).resolve().parents[1]
store=FilingStore(root/'data/annual-documents.sqlite')
# Import only exact original evidence if no fresh checkpoint already exists.
seed=json.loads((root/'docs/evidence/annual-filings-live.json').read_text())
owner=store.acquire(datetime.now(timezone.utc),timedelta(minutes=15))
try:
 for row in seed['companies']:
  if 'source_evidence' not in row:continue
  now=datetime.now(timezone.utc)
  if store.get(row['issuer_id'],row['annual'],now,timedelta(hours=6)) is not None:continue
  e=row['source_evidence'];response=Response(e['url'],gzip.decompress((root/e['fixture']).read_bytes()),datetime.fromisoformat(e['retrieved_at']))
  if response.sha256!=e['sha256']:raise ValueError('seed checksum differs')
  store.put(row['issuer_id'],row['annual'],response,owner,now,timedelta(minutes=15))
finally:store.release(owner)
class Recording(HttpTransport):
 calls=0
 def get(self,url):
  self.calls+=1;response=super().get(url)
  name=response.sha256+'.html.gz';folder=root/'tests/fixtures/annual-batch';folder.mkdir(exist_ok=True)
  (folder/name).write_bytes(gzip.compress(response.body,mtime=0))
  return response
transport=Recording(user_agent=args.user_agent,allowed_hosts={'www.sec.gov'},accept='text/html')
rows=json.loads((root/'docs/evidence/sample100-submissions-live.json').read_text())['companies']
try:report=DocumentRunner(store,transport).run(rows,max_new_documents=args.max_new_documents)
finally:store.close()
report['transport_get_calls']=transport.calls
report['request_measure']='transport GET invocations, excluding internal retries; cached parser outcomes are recomputed from original bytes'
# All fresh source bodies are content-addressed; original three sources use seed fixtures.
seed_hashes={r['source_evidence']['sha256']:r['source_evidence']['fixture'] for r in seed['companies'] if 'source_evidence' in r}
for r in report['companies']:
 if 'source_evidence' in r:
  e=r['source_evidence'];e['fixture']=seed_hashes.get(e['sha256'],'tests/fixtures/annual-batch/'+e['sha256']+'.html.gz')
destination=root/args.output;destination.parent.mkdir(parents=True,exist_ok=True)
with tempfile.NamedTemporaryFile(mode='w',dir=destination.parent,delete=False) as f:
 json.dump(report,f,indent=2);temporary=f.name
os.replace(temporary,destination)
print(json.dumps(dict(summary=report['summary'],transport_get_calls=transport.calls)))
