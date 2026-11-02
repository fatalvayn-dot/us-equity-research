"""Source overlay and deterministic pilot-score artifacts, without cache databases."""
import gzip
import hashlib
import json
import shutil
from datetime import datetime
from pathlib import Path

from equity_research.cache import encode
from equity_research.evidence_bundle import read_bundle
from equity_research.scoring import build_score_report,render_score_markdown
from equity_research.score_html import render_score_html

ROOT=Path(__file__).resolve().parents[1]


def main():
    state=ROOT/'data/research-score';target=ROOT/'docs/evidence/score-pilot';target.mkdir(parents=True,exist_ok=True)
    bundle=ROOT/'tests/fixtures/score-market-sources';bundle.mkdir(parents=True,exist_ok=True)
    manifest=json.loads((state/'market-bundle/manifest.json').read_text())
    for name in ['manifest.json']+[p['file'] for p in manifest['parts']]:shutil.copy2(state/'market-bundle'/name,bundle/name)
    audit_path=target/'audit.json' if (target/'audit.json').exists() else state/'audit.json'
    audit=json.loads(audit_path.read_text())
    paths=['docs/evidence/liquidity100/batch.json.gz','docs/evidence/comparative100/current-batch.json.gz','docs/evidence/comparative100/prior-batch.json.gz']
    batches=[json.loads(gzip.decompress((ROOT/p).read_bytes())) for p in paths]
    responses=list(read_bundle(ROOT/'tests/fixtures/valuation-sources'))+list(read_bundle(bundle))
    report=build_score_report(*batches,responses,as_of=datetime.fromisoformat(audit['evidence_cutoff']))
    (target/'report.json.gz').write_bytes(gzip.compress((json.dumps(report,default=encode,indent=2)+'\n').encode(),mtime=0))
    (target/'report.md').write_text(render_score_markdown(report))
    (target/'report.html').write_text(render_score_html(report))
    if audit_path!=target/'audit.json':shutil.copy2(audit_path,target/'audit.json')
    evidence=dict(financial_inputs=[dict(file=p,sha256=hashlib.sha256((ROOT/p).read_bytes()).hexdigest()) for p in paths],
        raw_source_bundles=['tests/fixtures/valuation-sources','tests/fixtures/score-market-sources'],
        source_mode='live_market_overlay_plus_recorded_financial_evidence',mvp_accepted=False,
        files=[dict(file=n,bytes=len((target/n).read_bytes()),sha256=hashlib.sha256((target/n).read_bytes()).hexdigest())
            for n in ('report.json.gz','report.md','report.html','audit.json','zero-work-resume.json','live-helper-validation.json') if (target/n).exists()])
    (target/'manifest.json').write_text(json.dumps(evidence,indent=2)+'\n')
    print(json.dumps(report['summary']))


if __name__=='__main__':main()
