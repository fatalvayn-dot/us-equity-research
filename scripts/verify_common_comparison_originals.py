"""Reconcile the new 17 issuers' paired operands to their original annual iXBRL."""
import gzip
import json
from collections import Counter
from datetime import date
from decimal import Decimal
from pathlib import Path

from equity_research.concept_diagnostics import inspect_concepts
from equity_research.evidence_bundle import read_bundle
from equity_research.mvp import save_json


def run(root=Path('.')):
    evidence=root/'docs/evidence/common-comparative100'
    audit=json.loads((evidence/'audit.json').read_text())
    candidates=json.loads((root/'docs/evidence/common-financial17/candidates.json').read_text())
    requested={r['issuer_id'] for r in candidates['companies']}
    plans={p['issuer_id']:p for p in audit['plans'] if p['issuer_id'] in requested}
    bodies={}
    for response in read_bundle(root/'tests/fixtures/common-extra-sources'):
        for cik,p in plans.items():
            ref=p['annual_source']
            if (response.url,response.sha256,response.retrieved_at.isoformat())==(ref['url'],ref['sha256'],ref['retrieved_at']):
                bodies[cik]=response
    checks=[]
    for side in ('current','prior'):
        batch=json.loads(gzip.decompress((evidence/(side+'-batch.json.gz')).read_bytes()))
        for company in batch['companies']:
            cik=company['issuer_id']
            if cik not in requested:continue
            fields=[f for f in company['fields'] if f.get('fact') and f['state']=='collected']
            if not fields:continue
            source=bodies[cik];q=fields[0]['query']
            original=inspect_concepts(source.body,cik=cik,
                concepts=[f['query']['accounting_definition'] for f in fields],
                period_start=date.fromisoformat(q['period_start']),period_end=date.fromisoformat(q['period_end']))
            for f,raw in zip(fields,original['concepts']):
                fact=f['fact']
                matched=raw['status']=='exact_original_value' and Decimal(raw['value'])==Decimal(fact['value'])
                checks.append(dict(symbol=company['symbol'],issuer_id=cik,side=side,field=f['query']['field'],
                    period_start=q['period_start'],period_end=q['period_end'],currency='USD',
                    selected_value=fact['value'],selected_source_url=fact['source_url'],selected_raw_sha256=fact['raw_sha256'],
                    selected_filing_accession=fact['filing_accession'],original=raw,
                    original_source_url=source.url,original_sha256=source.sha256,
                    original_retrieved_at=source.retrieved_at.isoformat(),
                    status='matched' if matched else 'original_unresolved_or_mismatch'))
    result=dict(evidence_mode='offline_original_document_reconciliation',new_http_requests=0,
        companies=len({r['issuer_id'] for r in checks}),checks=checks,
        summary=dict(Counter(r['status'] for r in checks)),mvp_accepted=False)
    save_json(evidence/'original-checks.json',result)
    print(json.dumps({k:v for k,v in result.items() if k!='checks'}))
    return result


if __name__=='__main__':run()
