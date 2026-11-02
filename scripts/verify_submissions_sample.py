"""Opt-in bounded SEC metadata collection; no financial/scope acceptance."""
import argparse,gzip,json,os,tempfile
from dataclasses import asdict
from datetime import datetime,timezone
from pathlib import Path

from equity_research.cache import encode
from equity_research.providers import ProviderFailure
from equity_research.submissions import SecSubmissions
from equity_research.transport import HttpTransport

parser=argparse.ArgumentParser();parser.add_argument('--user-agent',required=True)
parser.add_argument('--limit',type=int,default=100)
args=parser.parse_args()
if not 0<=args.limit<=100:parser.error('limit 0..100 required')
root=Path(__file__).resolve().parents[1];evidence=root/'docs/evidence'
rows=json.loads((evidence/'sample100-audit-queue.json').read_text())['companies'][:args.limit]
fixture_dir=root/'tests/fixtures/submissions';fixture_dir.mkdir(exist_ok=True)
class Recording(HttpTransport):
    calls=0
    def get(self,url):
        self.calls+=1
        r=super().get(url)
        filename=url.rsplit('/',1)[-1]+'.gz'
        (fixture_dir/filename).write_bytes(gzip.compress(r.body,mtime=0))
        return r
transport=Recording(user_agent=args.user_agent,allowed_hosts={'data.sec.gov'})
client=SecSubmissions(transport,cache_path=root/'data/cache/submissions.sqlite')
results=[]
def save():
    counts={}
    for r in results:counts[r['status']]=counts.get(r['status'],0)+1
    payload=dict(recorded_at=datetime.now(timezone.utc).isoformat(),companies=results,
        summary=dict(companies=len(results),states=counts,explicit_annual_ends=sum(r.get('annual') is not None for r in results)),
        coverage='recent filings only; older archive pages not queried',
        transport_get_calls=transport.calls,original_observation_cache_hits=sum(r.get('snapshot',{}).get('cached',False) for r in results),
        legal_type_approved=False,financial_values_validated=False,hundred_company_accepted=False)
    dest=evidence/'sample100-submissions-live.json'
    with tempfile.NamedTemporaryFile(mode='w',dir=dest.parent,delete=False) as f:
        json.dump(payload,f,default=encode,indent=2);temporary=f.name
    os.replace(temporary,dest)
try:
    for row in rows:
        result=dict(symbol=row['symbol'],issuer_id=row['issuer_id'])
        try:
            s=client.fetch(row['issuer_id']);annual=s.latest_annual()
            result.update(status=s.readiness(row['symbol']),snapshot=asdict(s),annual=asdict(annual) if annual else None,
                period_start=None,period_start_status='not_inferred_from_submission_report_date',
                fixture='tests/fixtures/submissions/'+('CIK'+row['issuer_id']+'.json.gz'))
        except ProviderFailure as e:result.update(status=e.status.value,reason=e.reason.value if e.reason else None,http_status=e.http_status)
        results.append(result);save()
        print(len(results),row['symbol'],result['status'],flush=True)
finally:client.close()
