"""Replay recorded issuer metadata and calculations; no fresh/live acceptance."""
import gzip
import json
from collections import Counter
from datetime import date, datetime
from pathlib import Path

from equity_research.cache import decode_fact, encode
from equity_research.sector_policy import assess_profile, calculate_with_sector_guard
from equity_research.transport import Response

root = Path(__file__).resolve().parents[1]
evidence = root / 'docs/evidence'
source = json.loads((evidence / 'sample100-submissions-live.json').read_text())
responses = {}
profiles = []
for row in source['companies']:
    snapshot = row['snapshot']
    cik = row['issuer_id']
    body = gzip.decompress((root / f'tests/fixtures/submissions/CIK{cik}.json.gz').read_bytes())
    response = Response(snapshot['source_url'], body, datetime.fromisoformat(snapshot['retrieved_at']))
    if response.sha256 != snapshot['raw_sha256']:
        raise ValueError('recorded metadata hash mismatch')
    responses[cik] = response
    profiles.append(dict(symbol=row['symbol'], **assess_profile(response, issuer_id=cik, as_of=response.retrieved_at)))

recorded = json.loads((evidence / 'calculation-sample.json').read_text())
guarded = []
for row in recorded['calculations']:
    facts = {f['field']: decode_fact(f) for f in row['inputs']}
    # Missing operands remain missing; preserve the original exact calculation cutoff.
    got = calculate_with_sector_guard(row['calculation'], facts, metadata_response=responses[row['issuer_id']],
        issuer_id=row['issuer_id'], period_start=date.fromisoformat(row['period_start']),
        period_end=date.fromisoformat(row['period_end']), currency=row['input_currency'],
        as_of=datetime.fromisoformat(row['as_of']))
    guarded.append(dict(symbol=row['symbol'], **got))
report = dict(mode='recorded metadata and exact-input arithmetic replay; not live or historical-vintage acceptance',
    profiles=profiles, guarded_calculations=guarded,
    summary=dict(issuers=len(profiles), routes=dict(Counter(p['profile'] for p in profiles)),
        arithmetic_results=sum(g['arithmetic']['value'] is not None for g in guarded),
        interpreted_results=sum(g['interpreted_value'] is not None for g in guarded)),
    new_network_requests=0, sector_model_accepted=False, hundred_company_financial_accepted=False)
(evidence / 'sector-policy-replay.json').write_text(json.dumps(report, default=encode, indent=2) + '\n')
print(json.dumps(report['summary']))
