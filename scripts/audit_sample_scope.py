"""Replay recorded primary evidence; use --live for fresh bounded HTTP requests."""
import argparse
import gzip
import json
from collections import Counter
from dataclasses import asdict
from datetime import datetime,timezone
from pathlib import Path

from equity_research.cache import encode
from equity_research.nasdaq import NasdaqDirectories,parse_directory,build_universe
from equity_research.scope import audit_sample
from equity_research.sec import SecDirectory,parse_directory as parse_sec,DIRECTORY_URL
from equity_research.transport import HttpTransport,Response
from equity_research.providers import ProviderFailure

parser=argparse.ArgumentParser()
parser.add_argument('--live',action='store_true')
parser.add_argument('--user-agent')
parser.add_argument('--output')
args=parser.parse_args()
if args.live and not args.user_agent:parser.error('--live requires --user-agent')
root=Path(__file__).resolve().parents[1];evidence=root/'docs/evidence';fixtures=root/'tests/fixtures'
metadata=evidence/'scope-primary-snapshots.json'
if args.live:
    class Recording(HttpTransport):
        def get(self,url):
            response=super().get(url)
            name=('scope-sec-directory.json.gz' if url==DIRECTORY_URL else
                  ('scope-nasdaqlisted.txt.gz' if 'nasdaqlisted' in url else 'scope-otherlisted.txt.gz'))
            (fixtures/name).write_bytes(gzip.compress(response.body,mtime=0))
            self.observations.append(dict(url=url,retrieved_at=response.retrieved_at.isoformat(),sha256=response.sha256,fixture='tests/fixtures/'+name))
            return response
    observations=[]
    transport=Recording(user_agent=args.user_agent,allowed_hosts={'ftp.nasdaqtrader.com','www.nasdaqtrader.com'},
                        max_attempts=1,budget=15,accept='text/plain')
    transport.observations=observations
    adapter=NasdaqDirectories(transport)
    try:
        snapshots=adapter.fetch()
        sec=Recording(user_agent=args.user_agent,allowed_hosts={'www.sec.gov'})
        sec.observations=observations
        identity=SecDirectory(sec).fetch()
    except ProviderFailure as exc:
        print(json.dumps(dict(status=exc.status.value,attempts=adapter.attempts,active_universe_accepted=False)))
        raise SystemExit(2) from None
    meta=dict(observed_at=datetime.now(timezone.utc).isoformat(),sources=observations,attempts=adapter.attempts)
    metadata.write_text(json.dumps(meta,indent=2)+'\n')
else:
    meta=json.loads(metadata.read_text());snapshots=[]
    for row in meta['sources']:
        response=Response(row['url'],gzip.decompress((root/row['fixture']).read_bytes()),datetime.fromisoformat(row['retrieved_at']))
        if response.sha256!=row['sha256']:raise ValueError('recorded response checksum differs')
        if row['url']==DIRECTORY_URL:identity=parse_sec(response)
        else:snapshots.append(parse_directory(response,'nasdaqlisted' if 'nasdaqlisted' in row['url'] else 'otherlisted'))
now=datetime.fromisoformat(meta['observed_at'])
queue=json.loads((evidence/'sample100-audit-queue.json').read_text())['companies']
report=audit_sample(queue,tuple(snapshots),identity,as_of=now)
all_rows=build_universe(tuple(snapshots),identity,as_of=now)
report['directory_partition']=dict(rows=len(all_rows),statuses=dict(Counter(row.status.value for row in all_rows)))
report['directory_snapshots']=[dict(name=s.name,rows=len(s.rows),url=s.source_url,sha256=s.raw_sha256,
    retrieved_at=s.retrieved_at.isoformat(),created_on=s.created_on.isoformat()) for s in snapshots]
report['verification_mode']='recorded-primary-response replay at original observation time' if not args.live else 'direct live HTTP + primary response parse'
(Path(args.output) if args.output else evidence/('sample100-scope-audit.json' if args.live else 'sample100-scope-replay.json')).write_text(json.dumps(report,default=encode,indent=2)+'\n')
print(json.dumps(dict(summary=report['summary'],directory_partition=report['directory_partition']),indent=2))
