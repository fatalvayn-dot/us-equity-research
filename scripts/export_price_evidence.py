"""Publish bounded original public recordings, never operational SQLite caches."""
import argparse
import gzip
import hashlib
import json
import sqlite3
from pathlib import Path

from equity_research.evidence_bundle import write_bundle, read_bundle
from equity_research.prices import render_price_markdown
from equity_research.response_archive import ResponseArchive


def export(state_dir, output, sources):
    state_dir,output,sources=map(Path,(state_dir,output,sources))
    # Do not export a partial collection or race a live writer.
    db=sqlite3.connect(f'file:{state_dir / "run-lock.sqlite"}?mode=ro',uri=True)
    try:
        if db.execute('SELECT owner FROM batch_lease_v1 WHERE singleton=1').fetchone():
            raise ValueError('price collection lease is active')
    finally:db.close()
    report=json.loads((state_dir/'report.json').read_text())
    archive=ResponseArchive(state_dir/'sources.sqlite')
    try:manifest=write_bundle(archive,sources)
    finally:archive.close()
    count=sum(1 for _ in read_bundle(sources))
    if count!=manifest['observations']:raise ValueError('recording count mismatch')
    output.mkdir(parents=True,exist_ok=True)
    body=json.dumps(report,sort_keys=True).encode()
    stored=gzip.compress(body,mtime=0)
    (output/'report.json.gz').write_bytes(stored)
    markdown=render_price_markdown(report).encode()
    (output/'report.md').write_bytes(markdown)
    result=dict(schema_version=1,report_sha256=hashlib.sha256(body).hexdigest(),
                stored_report_sha256=hashlib.sha256(stored).hexdigest(),
                markdown_sha256=hashlib.sha256(markdown).hexdigest(),
                source_manifest=str(sources/'manifest.json'),source_observations=count,
                summary=report['summary'],new_identity_get_invocations=report['new_identity_get_invocations'],
                all_selected_price_references_archived=report['all_selected_price_references_archived'],
                mvp_accepted=False,scoring_accepted=False)
    (output/'manifest.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result))


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--state-dir',default='data/price100')
    parser.add_argument('--output',default='docs/evidence/price100')
    parser.add_argument('--sources',default='tests/fixtures/price100-sources')
    args=parser.parse_args()
    export(args.state_dir,args.output,args.sources)
