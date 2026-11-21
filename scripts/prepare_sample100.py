"""Reproducible audit queue from recorded discovery; no universe approval."""
import gzip
import hashlib
import json
import re
from pathlib import Path

root=Path(__file__).resolve().parents[1]
evidence=root/'docs/evidence'
sec_bytes=(root/'tests/fixtures/sec-directory-recorded.json').read_bytes()
sec=json.loads(sec_bytes);mapping={row[2]:dict(zip(sec['fields'],row)) for row in sec['data']}
raw=gzip.decompress((root/'tests/fixtures/nasdaq-discovery-diagnostic.json.gz').read_bytes())
rows=json.loads(raw)['data']['table']['rows']
known={row['symbol']:row for row in json.loads((evidence/'batch-three-plan.json').read_text())['companies']}
selected=[];seen=set()
for row in rows:
    symbol=row['symbol'].strip();entry=mapping.get(symbol);name=row['name']
    # Explicit name hints select an audit queue, not a positive security classifier.
    if not entry or entry['exchange'] not in ('Nasdaq','NYSE','NYSE American'):continue
    if not re.search(r'\b(common stock|ordinary shares)\b',name,re.I):continue
    if re.search(r'\b(fund|ETF|preferred|warrant|units?|rights?|depositary)\b',name,re.I):continue
    cik=str(entry['cik']).zfill(10)
    if cik in seen:continue
    seen.add(cik)
    selected.append(dict(symbol=symbol,issuer_id=cik,discovery_name=name,sec_name=entry['name'],
        sec_exchange_label=entry['exchange'],scope_status='pending_scope',
        missing_scope_evidence=['current primary listing','legal common-share class','ETF/fund exclusion','test/security activity status'],
        period_start=known.get(symbol,{}).get('period_start'),period_end=known.get(symbol,{}).get('period_end'),
        period_status='previously_checked_sample' if symbol in known else 'not_verified'))
    if len(selected)==100:break
assert len(selected)==100 and len(seen)==100
result=dict(schema_version=1,selection='first 100 unique SEC CIKs in recorded Nasdaq source order with explicit common/ordinary name hints; no representative or sector-balanced claim',
    source_evidence=['nasdaq-discovery-live.json','sec-directory-live.json'],
    source_hashes=dict(nasdaq=hashlib.sha256(raw).hexdigest(),sec=hashlib.sha256(sec_bytes).hexdigest()),
    companies=selected,summary=dict(candidates=len(selected),scope_approved=0,
        explicit_periods=sum(c['period_end'] is not None for c in selected),financially_tested_as_batch100=0),
    active_universe_accepted=False,hundred_company_accepted=False)
(evidence/'sample100-audit-queue.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result['summary']))
