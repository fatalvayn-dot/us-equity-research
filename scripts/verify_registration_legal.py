"""Replay two freshly recorded official registration covers, not universe approval."""
import gzip
import json
from datetime import date, datetime
from pathlib import Path

from equity_research.legal_evidence import registration_legal_evidence
from equity_research.transport import Response

root = Path(__file__).resolve().parents[1]
manifest = json.loads((root/'docs/evidence/registration-source-manifest.json').read_text())
results = []
for row in manifest['observations']:
    response = Response(row['source_url'], gzip.decompress((root/row['fixture']).read_bytes()),
                        datetime.fromisoformat(row['retrieved_at']))
    if response.sha256 != row['raw_sha256']:
        raise ValueError('original registration response hash mismatch')
    result = registration_legal_evidence(response, cik=row['issuer_id'],
        disclosure_date=date.fromisoformat(row['disclosure_date']), document_type=row['document_type'],
        as_of=response.retrieved_at)
    results.append(dict(label=row['label'], **result))
report = dict(mode='replay of two official issuer documents downloaded in this session', companies=results,
    summary=dict(documents=len(results), reported_flags=sum(d['status']=='reported' for r in results for k,d in r['disclosures'].items() if k in ('business_development_company','registered_closed_end_fund'))),
    replay_network_requests=0, original_document_downloads=2, financial_values_validated=False,
    legal_type_approved=False, hundred_company_accepted=False)
(root/'docs/evidence/registration-legal-replay.json').write_text(json.dumps(report, indent=2)+'\n')
print(json.dumps(report['summary']))
