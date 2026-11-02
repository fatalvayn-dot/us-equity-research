"""Prepare instant queries from explicit submission dates; duration starts stay unresolved."""
import json
from pathlib import Path
root=Path(__file__).resolve().parents[1];evidence=root/'docs/evidence'
source=json.loads((evidence/'sample100-submissions-live.json').read_text())
rows=[];pending=[]
for company in source['companies']:
    annual=company.get('annual')
    if company['status']!='metadata_available_legal_type_pending' or annual is None:
        pending.append(dict(symbol=company['symbol'],issuer_id=company['issuer_id'],reason=company['status'] if annual else 'no_annual_in_recent_window'))
        continue
    rows.append(dict(symbol=company['symbol'],issuer_id=company['issuer_id'],period_end=annual['report_end'],
        fields=['assets','liabilities'],currency='USD',scope_status='pending_scope',
        scope_reason='legal_type_and_sector_model_not_accepted',
        period_evidence=dict(url=company['snapshot']['source_url'],sha256=company['snapshot']['raw_sha256'],
            retrieved_at=company['snapshot']['retrieved_at'],accession=annual['accession']),
        currency_note='USD is the requested unit, not inferred reporting currency; adapters must validate'))
report=dict(schema_version=1,companies=rows,pending_companies=pending,
    duration_start_dates_inferred=False,scope_approved=False,hundred_company_accepted=False)
(evidence/'sample-annual-end-plan.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(dict(instant_query_companies=len(rows),pending=len(pending),scope_approved=False)))
