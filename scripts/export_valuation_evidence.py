"""Publish only selected public evidence artifacts, never operational SQLite state."""
import gzip
import hashlib
import json
import shutil
from pathlib import Path
from datetime import datetime
from equity_research.cache import encode
from equity_research.evidence_bundle import read_bundle
from equity_research.valuation import build_valuation_report,render_valuation_markdown

ROOT=Path(__file__).resolve().parents[1]


def main():
    state=ROOT/'data/valuation-sample';target=ROOT/'docs/evidence/valuation-sample'
    target.mkdir(parents=True,exist_ok=True)
    bundle=ROOT/'tests/fixtures/valuation-sources';bundle.mkdir(parents=True,exist_ok=True)
    source_manifest=json.loads((state/'source-bundle/manifest.json').read_text())
    for name in ['manifest.json']+[p['file'] for p in source_manifest['parts']]:
        shutil.copy2(state/'source-bundle'/name,bundle/name)
    batch=ROOT/'docs/evidence/liquidity100/batch.json.gz'
    # Re-render an existing capture at its recorded cutoff rather than replacing
    # its live-GET evidence with a later zero-work resume's counters.
    capture_path=target/'audit.json' if (target/'audit.json').exists() else state/'audit.json'
    capture=json.loads(capture_path.read_text())
    report=build_valuation_report(json.loads(gzip.decompress(batch.read_bytes())),read_bundle(bundle),
        as_of=datetime.fromisoformat(capture['evidence_cutoff']))
    body=(json.dumps(report,default=encode,indent=2)+'\n').encode()
    (target/'report.json.gz').write_bytes(gzip.compress(body,mtime=0))
    (target/'report.md').write_text(render_valuation_markdown(report))
    if capture_path!=target/'audit.json':shutil.copy2(capture_path,target/'audit.json')
    # Preserve the initial capture as generated. Its null top-level price GET
    # count was a helper lookup error; the nested source report holds the true 3.
    # Correct only the exported audit with an explicit correction trail.
    audit=json.loads((target/'audit.json').read_text())
    if audit.get('new_price_get_invocations') is None:
        audit['new_price_get_invocations']=audit['price_summary']['new_price_get_invocations']
        audit['capture_correction']='top-level count copied from preserved nested price_summary; no source data or timestamps changed'
        (target/'audit.json').write_text(json.dumps(audit,indent=2)+'\n')
    manifest=dict(input_batch=str(batch.relative_to(ROOT)),input_sha256=hashlib.sha256(batch.read_bytes()).hexdigest(),
        source_observations=source_manifest['observations'],source_bundle=str(bundle.relative_to(ROOT)),
        financial_numerators='retained_recorded_annual_batch_not_refreshed',fresh_100_company_acceptance=False,
        files=[dict(file=name,bytes=len((target/name).read_bytes()),sha256=hashlib.sha256((target/name).read_bytes()).hexdigest())
            for name in ('report.json.gz','report.md','audit.json','zero-work-resume.json') if (target/name).exists()])
    (target/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    print(json.dumps(manifest))


if __name__=='__main__':main()
