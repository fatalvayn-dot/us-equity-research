"""Fresh ordered financial collection with original public response capture."""
import argparse,gzip,json
from datetime import datetime,timezone
from pathlib import Path
from equity_research.batch import BatchRunner,BatchStore,load_plan
from equity_research.cache import encode
from equity_research.companyfacts import SecCompanyFacts
from equity_research.pipeline import research_resolver
from equity_research.response_archive import ResponseArchive,ArchivedTransport
from equity_research.sec import SecDirectory
from equity_research.transport import Response

p=argparse.ArgumentParser();p.add_argument('--user-agent',required=True);args=p.parse_args()
root=Path(__file__).resolve().parents[1];evidence=root/'docs/evidence'
archive=ResponseArchive(root/'data/financial-responses.sqlite')
# Reuse exact original SEC bodies from accepted disk snapshots, not fresh labels.
for file in (root/'data/cache/companyfacts').glob('*.json'):
 e=json.loads(file.read_text());r=Response(e['url'],e['body'].encode(),datetime.fromisoformat(e['retrieved_at']))
 if r.sha256!=e['sha256']:raise ValueError('SEC checkpoint checksum differs')
 archive.record(r)
identity=SecDirectory(ArchivedTransport(archive=archive,user_agent=args.user_agent,allowed_hosts={'www.sec.gov'})).fetch()
companies=load_plan(json.loads((evidence/'annual-eight-plan.json').read_text()))
def factory(company):
 if identity.lookup(company.symbol,expected_cik=company.issuer_id) is None:raise ValueError('wrong identity')
 return research_resolver(directory=identity,symbol=company.symbol,user_agent=args.user_agent,
     cache_dir=root/'data/cache/companyfacts',response_archive=archive)
store=BatchStore(root/'data/archived-financial.sqlite')
try:report=BatchRunner(store,factory).run(companies)
finally:store.close()
(evidence/'archived-eight-financial.json').write_text(json.dumps(report,default=encode,indent=2)+'\n')
folder=root/'tests/fixtures/financial-responses';folder.mkdir(exist_ok=True)
observations=archive.observations()
for e in observations:
 r=archive.get(e['url'],e['sha256'],datetime.fromisoformat(e['retrieved_at']))
 target=folder/(e['sha256']+'.gz');target.write_bytes(gzip.compress(r.body,mtime=0));e['fixture']=str(target.relative_to(root))
(evidence/'financial-response-manifest.json').write_text(json.dumps(dict(observations=observations,headers_stored=False,credentials_stored=False),indent=2)+'\n')
coverage=[]
for c in report['companies']:
 for field in c['fields']:
  f=field['fact']
  if f is None:continue
  refs=[('financial',f['source_url'],f['raw_sha256'],f.get('data_observed_at') or f['retrieved_at'])]
  for prefix in ('identity','unit'):
   if f.get(prefix+'_evidence_url'):refs.append((prefix,f[prefix+'_evidence_url'],f[prefix+'_evidence_sha256'],f[prefix+'_observed_at']))
  checked=[]
  for kind,url,sha,stamp in refs:
   checked.append(dict(kind=kind,url=url,sha256=sha,observed_at=stamp,exact_observation_found=archive.get(url,sha,datetime.fromisoformat(stamp)) is not None))
  coverage.append(dict(symbol=c['symbol'],field=f['field'],references=checked))
(evidence/'financial-response-coverage.json').write_text(json.dumps(dict(facts=coverage,all_references_archived=all(ref['exact_observation_found'] for c in coverage for ref in c['references']),
    scope_approved=False,hundred_company_accepted=False),indent=2)+'\n')
archive.close();print(json.dumps(report['summary']))
