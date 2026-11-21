"""Recorded filing cover checks; explicitly no new live filing download."""
import gzip,json
from datetime import date
from pathlib import Path
from equity_research.filing_metadata import filing_security_metadata

root=Path(__file__).resolve().parents[1]
source=json.loads((root/'docs/evidence/companyfacts-live.json').read_text())
periods={'AAPL':'2026-06-27','MSFT':'2026-09-30','NVDA':'2026-07-26'}
results=[]
for company in source['companies']:
    evidence=company['filing_reconciliation']
    body=gzip.decompress((root/evidence['fixture']).read_bytes())
    result=filing_security_metadata(body,cik=company['cik'],symbol=company['symbol'],
        report_end=date.fromisoformat(periods[company['symbol']]),document_type='10-Q')
    if result['raw_sha256']!=evidence['sha256']:raise ValueError('original filing checksum differs')
    result['source_evidence']={k:evidence[k] for k in ('url','sha256','retrieved_at','fixture')}
    results.append(result)
payload=dict(mode='recorded original quarterly filing replay; no new live filing request',companies=results,
    note='Cover dates are quarterly document dates, not the prior annual balance-sheet comparison date. Raw checkbox labels are not interpreted as booleans.',
    scope_approved=False,hundred_company_accepted=False)
(root/'docs/evidence/registered-share-replay.json').write_text(json.dumps(payload,indent=2)+'\n')
print(json.dumps(dict(recorded_filings=len(results),common_titles=len(results),scope_approved=False)))
