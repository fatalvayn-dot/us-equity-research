"""Replay original annual documents without converting missing tags into negatives."""
import gzip
import json
from datetime import date, datetime
from pathlib import Path

from equity_research.legal_evidence import annual_legal_evidence
from equity_research.transport import Response

root = Path(__file__).resolve().parents[1]
evidence = root / 'docs/evidence'
source = json.loads((evidence/'annual-document-batch.json').read_text())
results = []
for row in source['companies']:
    saved = row.get('source_evidence')
    if not saved:
        continue
    response = Response(saved['url'], gzip.decompress((root/saved['fixture']).read_bytes()),
                        datetime.fromisoformat(saved['retrieved_at']))
    if response.sha256 != saved['sha256']:
        raise ValueError('original annual hash mismatch')
    result = annual_legal_evidence(response, cik=row['issuer_id'],
        report_end=date.fromisoformat(row['annual']['report_end']), document_type=row['annual']['form'],
        as_of=response.retrieved_at)
    results.append(dict(symbol=row['symbol'], **result))
report = dict(mode='recorded original annual-document replay, not fresh legal verification', companies=results,
    summary=dict(documents=len(results), reported_disclosures=sum(d['status']=='reported' for r in results for d in r['disclosures'].values()),
        unknown_tagged_disclosures=sum(d['status']=='unknown' for r in results for d in r['disclosures'].values())),
    new_financial_network_requests=0, legal_type_approved=False, hundred_company_accepted=False)
(evidence/'annual-legal-replay.json').write_text(json.dumps(report, indent=2)+'\n')
print(json.dumps(report['summary']))
