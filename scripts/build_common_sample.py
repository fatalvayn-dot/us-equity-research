"""Rebuild exact sample admission from original recorded bodies; no network calls."""
import argparse,json
from datetime import datetime,timezone
from pathlib import Path
from equity_research.common_sample import verify_common_sample
from equity_research.evidence_bundle import read_bundle
from equity_research.submissions import submissions_url
from equity_research.mvp import save_json

ROOT=Path(__file__).resolve().parents[1]

def run(extra,state_dir,as_of):
    state=Path(state_dir);state.mkdir(parents=True,exist_ok=True)
    documents=json.loads((ROOT/'docs/evidence/mvp100/documents.json').read_text())['companies']
    selected=[r for r in documents if r.get('registered_share')]
    fresh=json.loads((Path(extra)/'collection.json').read_text())
    pool=[dict(symbol=r['symbol'],issuer_id=r['issuer_id']) for r in selected]+fresh['candidates']
    urls={url for r in selected for url in (submissions_url(r['issuer_id']),r['annual']['source_url'])}
    # Raw Git bundles are authoritative. Do not trust an operational SQLite
    # index for source reconstruction, especially after an interrupted workspace.
    responses=[response for response in read_bundle(ROOT/'tests/fixtures/mvp100-sources') if response.url in urls]
    responses.extend(read_bundle(Path(extra)/'source-bundle'))
    report=verify_common_sample(dict(companies=pool),responses,as_of=as_of)
    save_json(state/'report.json',report);save_json(state/'candidates.json',report['candidate_plan'])
    print(json.dumps(report['summary']),flush=True)
    for row in report['companies']:
        if row['status']!='verified_registered_common_sample':print(row['symbol'],row['blockers'],flush=True)
    return report


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--extra-state',default='data/common-extra');p.add_argument('--state-dir',default='data/common-plan');p.add_argument('--as-of')
    args=p.parse_args();run(args.extra_state,args.state_dir,datetime.fromisoformat(args.as_of) if args.as_of else datetime.now(timezone.utc))
