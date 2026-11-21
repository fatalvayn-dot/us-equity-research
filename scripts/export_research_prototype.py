"""Rebuild the portable 100-candidate research browser from dated raw-backed input."""
import gzip
import hashlib
import json
from collections import Counter
from pathlib import Path

from equity_research.cache import encode
from equity_research.reporting import build_report
from equity_research.report_html import render_html

ROOT=Path(__file__).resolve().parents[1]


def main():
    source=ROOT/'docs/evidence/liquidity100/batch.json.gz'
    report=build_report(json.loads(gzip.decompress(source.read_bytes())))
    target=ROOT/'docs/evidence/risk100';target.mkdir(parents=True,exist_ok=True)
    page=render_html(report).encode()
    (target/'report.html').write_bytes(page)
    companies=[dict(symbol=c['symbol'],issuer_id=c['issuer_id'],assessment=c['financial_assessment'],
                    score_blockers=c['score_blockers'],total_score=c['total_score']) for c in report['companies']]
    body=json.dumps(dict(source_batch=str(source.relative_to(ROOT)),
        source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),as_of=report['as_of'],
        mode='recorded_evidence_reassessment_no_network',mvp_accepted=False,
        financial_review_summary=report['financial_review_summary'],companies=companies),default=encode,indent=2).encode()
    (target/'assessment.json.gz').write_bytes(gzip.compress(body,mtime=0))
    checks=Counter(check['check'] for c in companies for check in c['assessment']['checks'] if check['triggered'])
    manifest=dict(summary=report['summary'],financial_review_summary=report['financial_review_summary'],
        triggered_checks=dict(checks),new_network_requests=0,fresh_live_acceptance=False,
        files=[dict(file=n,bytes=len((target/n).read_bytes()),sha256=hashlib.sha256((target/n).read_bytes()).hexdigest())
               for n in ('report.html','assessment.json.gz')])
    (target/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    print(json.dumps(manifest))


if __name__=='__main__':main()
