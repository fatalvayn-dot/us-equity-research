"""Bounded original annual-document checks; no complete-company acceptance."""
import argparse,gzip,json
from datetime import date,datetime,timezone
from pathlib import Path
from equity_research.annual_period import annual_period
from equity_research.filing_metadata import filing_security_metadata
from equity_research.providers import ProviderFailure,Status
from equity_research.transport import HttpTransport,Response

parser=argparse.ArgumentParser();parser.add_argument('--user-agent');parser.add_argument('--limit',type=int,default=3);parser.add_argument('--replay',action='store_true')
args=parser.parse_args()
if not args.replay and not args.user_agent:parser.error('--user-agent required for live requests')
if not 0<=args.limit<=100:parser.error('limit must be 0..100')
root=Path(__file__).resolve().parents[1];evidence=root/'docs/evidence';fixtures=root/'tests/fixtures/annual';fixtures.mkdir(exist_ok=True)
rows=json.loads((evidence/'sample100-submissions-live.json').read_text())['companies']
if args.replay:rows=json.loads((evidence/'annual-filings-live.json').read_text())['companies']
transport=None if args.replay else HttpTransport(user_agent=args.user_agent,allowed_hosts={'www.sec.gov'},accept='text/html')
results=[]
for row in [r for r in rows if r.get('annual')][:args.limit]:
    result=dict(symbol=row['symbol'],issuer_id=row['issuer_id'],annual=row['annual'])
    annual=row['annual']
    try:
        if not annual['primary_document'].lower().endswith(('.htm','.html')):raise ProviderFailure(Status.INVALID_DATA)
        if args.replay:
            saved=row['source_evidence']
            response=Response(saved['url'],gzip.decompress((root/saved['fixture']).read_bytes()),datetime.fromisoformat(saved['retrieved_at']))
            if response.sha256!=saved['sha256'] or response.url!=annual['source_url']:raise ProviderFailure(Status.INVALID_DATA)
        else:response=transport.get(annual['source_url'])
        name=f"{row['issuer_id']}-{annual['accession']}.html.gz"
        if not args.replay:(fixtures/name).write_bytes(gzip.compress(response.body,mtime=0))
        result['source_evidence']=dict(url=response.url,sha256=response.sha256,retrieved_at=response.retrieved_at.isoformat(),fixture='tests/fixtures/annual/'+name)
        common=dict(cik=row['issuer_id'],report_end=date.fromisoformat(annual['report_end']),document_type=annual['form'])
        for field,parser_function in [('period',annual_period),('registered_share',filing_security_metadata)]:
            try:result[field]=parser_function(response.body,**common,**({'symbol':row['symbol']} if field=='registered_share' else {}))
            except ProviderFailure as e:result[field+'_status']=e.status.value
        result['status']='recorded_source_replayed' if args.replay else 'downloaded'
    except ProviderFailure as e:result.update(status=e.status.value,http_status=e.http_status)
    results.append(result)
report=dict(recorded_at=datetime.now(timezone.utc).isoformat(),companies=results,
    summary=dict(companies=len(results),periods=sum('period' in r for r in results),registered_shares=sum('registered_share' in r for r in results)),
    mode='recorded-original-source replay; zero new HTTP requests' if args.replay else 'live bounded original annual-document downloads',
    scope_approved=False,hundred_company_accepted=False)
(evidence/('annual-filings-replay.json' if args.replay else 'annual-filings-live.json')).write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report['summary']))
