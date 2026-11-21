"""Export new-cohort delta evidence and mixed-date reports, never operational SQLite."""
import gzip,hashlib,json,sqlite3
from datetime import datetime
from pathlib import Path
from equity_research.evidence_bundle import read_bundle,write_bundle
from equity_research.response_archive import ResponseArchive

ROOT=Path(__file__).resolve().parents[1]

def export():
    state=ROOT/'data/common-financial17';initial=ROOT/'data/common-financial17-initial'
    with sqlite3.connect(f'file:{state/"run-lock.sqlite"}?mode=ro',uri=True) as db:
        if db.execute('SELECT COUNT(*) FROM batch_lease_v1').fetchone()[0]:raise ValueError('collection still active')
    report=json.loads((state/'report.json').read_text());old=json.loads((initial/'report.json').read_text())
    if len(json.loads((state/'metadata.json').read_text())['companies'])!=report['pipeline']['requested_candidates']:raise ValueError('incomplete final metadata')
    before={c['issuer_id']:[f['fact'] for f in c['fields'] if f['fact']] for c in old['companies']}
    after={c['issuer_id']:[f['fact'] for f in c['fields'] if f['fact']] for c in report['companies']}
    if before!=after or report['pipeline']['public_transport_get_calls']!=0:raise ValueError('warm evidence changed')
    seeds={(r.url,r.sha256,r.retrieved_at.isoformat()) for r in read_bundle(ROOT/'tests/fixtures/common-extra-sources')}
    archive=ResponseArchive(state/'responses.sqlite');delta=ResponseArchive(':memory:')
    try:
        for row in archive.observations():
            key=(row['url'],row['sha256'],row['retrieved_at'])
            if key not in seeds:delta.record(archive.get(row['url'],row['sha256'],datetime.fromisoformat(row['retrieved_at'])))
        bundle=ROOT/'tests/fixtures/common-financial17-sources';manifest=write_bundle(delta,bundle)
    finally:archive.close();delta.close()
    dest=ROOT/'docs/evidence/common-financial17';dest.mkdir(parents=True,exist_ok=True)
    files=[]
    candidates=ROOT/'data/common-financial17-candidates.json'
    if candidates.exists():
        (dest/'candidates.json').write_bytes(candidates.read_bytes());files.append(dict(file='candidates.json',sha256=hashlib.sha256(candidates.read_bytes()).hexdigest()))
    for source,name in [(initial/n,n+'.gz') for n in ('metadata.json','documents.json','plan.json','batch.json','report.json','archive-coverage.json')]+[(state/'report.json','resume-report.json.gz'),(state/'metadata-finalization-audit.json','metadata-finalization-audit.json')]:
        body=source.read_bytes();payload=gzip.compress(body,mtime=0) if name.endswith('.gz') else body
        (dest/name).write_bytes(payload);files.append(dict(file=name,sha256=hashlib.sha256(payload).hexdigest()))
    proof=dict(initial_get_invocations=old['pipeline']['public_transport_get_calls'],warm_get_invocations=0,
        seeded_public_observations=old['pipeline']['seeded_public_observations'],archived_transport_reuses=old['pipeline']['archived_transport_reuses'],
        accepted_facts=old['summary']['accepted_facts'],calculations=old['summary']['arithmetic_results'],accepted_fact_values_source_times_unchanged=True,
        new_raw_observations=manifest['observations'],seed_bundle='tests/fixtures/common-extra-sources',
        full_new_100_live_run=False,initial_as_of=old['as_of'],resume_as_of=report['as_of'])
    (dest/'resume-proof.json').write_text(json.dumps(proof,indent=2)+'\n');files.append(dict(file='resume-proof.json',sha256=hashlib.sha256((dest/'resume-proof.json').read_bytes()).hexdigest()))
    (dest/'manifest.json').write_text(json.dumps(dict(files=files,delta_bundle='tests/fixtures/common-financial17-sources',seed_bundle='tests/fixtures/common-extra-sources',source_summary=manifest,mvp_accepted=False),indent=2)+'\n')
    combined=ROOT/'docs/evidence/common-financial100';combined.mkdir(parents=True,exist_ok=True)
    for n in ('batch.json','report.json'):(combined/(n+'.gz')).write_bytes(gzip.compress((ROOT/'data/common-financial100'/n).read_bytes(),mtime=0))
    for n in ('report.md','report.html'):(combined/n).write_bytes((ROOT/'data/common-financial100'/n).read_bytes())
    r=json.loads((ROOT/'data/common-financial100/report.json').read_text());payload=dict(summary=r['summary'],financial_cohort=r['financial_cohort'],mvp_accepted=False)
    payload['files']=[dict(file=p.name,sha256=hashlib.sha256(p.read_bytes()).hexdigest()) for p in sorted(combined.iterdir()) if p.name!='manifest.json']
    (combined/'manifest.json').write_text(json.dumps(payload,indent=2)+'\n')
    print(json.dumps(dict(delta_observations=manifest['observations'],parts=len(manifest['parts']),bytes=sum(p['bytes'] for p in manifest['parts']),mixed_summary=r['summary'])))

if __name__=='__main__':export()
