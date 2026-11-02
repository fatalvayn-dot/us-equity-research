"""Opt-in live bounded/resume diagnostic; never investment/100-company acceptance."""
import argparse
import contextlib
import io
import json
import sys
from collections import Counter
from datetime import datetime,timezone
from pathlib import Path
from unittest.mock import patch
from urllib.parse import urlsplit

from equity_research.__main__ import main
from equity_research.transport import HttpTransport

parser=argparse.ArgumentParser()
parser.add_argument('--user-agent',required=True)
parser.add_argument('--checkpoint',required=True)
args=parser.parse_args()
if Path(args.checkpoint).exists():parser.error('use a new checkpoint for this diagnostic')
root=Path(__file__).resolve().parents[1]
evidence=root/'docs/evidence'
original=json.loads((evidence/'companyfacts-live.json').read_text())
rows=[]
for company in original['companies']:
    duration=next(m for m in company['metrics'] if m['field']=='net_income')
    rows.append(dict(symbol=company['symbol'],issuer_id=company['cik'],fields=[m['field'] for m in company['metrics']],
        period_start=duration['period_start'],period_end=duration['period_end'],scope_status='pending_scope',
        scope_reason='active_listing_and_legal_common_share_evidence_pending'))
plan=evidence/'batch-three-plan.json'
plan.write_text(json.dumps(dict(schema_version=1,companies=rows),indent=2)+'\n')
requests=[]
get=HttpTransport.get

def observed(self,url):
    requests.append(urlsplit(url).hostname)
    return get(self,url)

runs=[]
for name,budget in [('bounded',3),('resumed',None),('reused',None)]:
    output=evidence/f'batch-three-{name}.json'
    argv=['equity-research','research-batch','--plan',str(plan),'--checkpoint',args.checkpoint,
          '--user-agent',args.user_agent,'--output',str(output)]
    if budget is not None:argv.extend(['--max-new-fields',str(budget)])
    before=len(requests);exit_code=0
    with patch.object(sys,'argv',argv),patch.object(HttpTransport,'get',observed),contextlib.redirect_stdout(io.StringIO()):
        try:main()
        except SystemExit as exc:exit_code=exc.code
    report=json.loads(output.read_text())
    runs.append(dict(name=name,exit_code=exit_code,summary=report['summary'],
                     transport_get_calls_by_host=dict(Counter(requests[before:]))))
result=dict(recorded_at=datetime.now(timezone.utc).isoformat(),runs=runs,
    request_measure='HttpTransport.get calls, excluding internal retries; provider disk-cache hits have no GET',
    third_run_zero_transport_calls=not runs[2]['transport_get_calls_by_host'],
    live_financial_acceptance=False,hundred_company_accepted=False,active_universe_accepted=False)
(evidence/'batch-resume-live.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result,indent=2))
if not result['third_run_zero_transport_calls']:raise SystemExit(1)
