"""Export completed public source evidence and reports; never operational databases."""
import argparse
import json
import shutil
import sqlite3
import gzip
import hashlib
from pathlib import Path
from equity_research.evidence_bundle import write_bundle, read_bundle
from equity_research.response_archive import ResponseArchive

p=argparse.ArgumentParser();p.add_argument('--state-dir',required=True);p.add_argument('--output',required=True)
p.add_argument('--sources',required=True);args=p.parse_args()
source=Path(args.state_dir);dest=Path(args.output);dest.mkdir(parents=True,exist_ok=True)
if not (source/'report.json').is_file():raise ValueError('completed report required before export')
with sqlite3.connect(f'file:{source / "run-lock.sqlite"}?mode=ro',uri=True) as lock:
    if lock.execute('SELECT COUNT(*) FROM batch_lease_v1').fetchone()[0]:raise ValueError('cannot export an active collection')
archive=ResponseArchive(source/'responses.sqlite')
try:manifest=write_bundle(archive,args.sources)
finally:archive.close()
verified=sum(1 for _ in read_bundle(args.sources))
if verified!=manifest['observations']:raise ValueError('source bundle verification failed')
files=[]
for name in ('metadata.json','documents.json','plan.json','batch.json','report.json','report.md','archive-coverage.json'):
    body=(source/name).read_bytes();stored=name
    payload=body
    if name.endswith('.json') and len(body)>524288:
        stored=name+'.gz';payload=gzip.compress(body,mtime=0)
    (dest/stored).write_bytes(payload)
    files.append(dict(logical_name=name,file=stored,encoding='gzip' if stored.endswith('.gz') else 'identity',
        raw_bytes=len(body),raw_sha256=hashlib.sha256(body).hexdigest(),stored_sha256=hashlib.sha256(payload).hexdigest()))
(dest/'reports-manifest.json').write_text(json.dumps(dict(files=files),indent=2)+'\n')
(dest/'source-bundle.json').write_text(json.dumps(dict(directory=args.sources,**manifest),indent=2)+'\n')
print(json.dumps(dict(observations=verified,parts=len(manifest['parts']),compressed_bytes=sum(p['bytes'] for p in manifest['parts']))))
