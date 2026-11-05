"""Recorded original annual checks for all scored operands, no provider calls."""
import gzip,json
from collections import Counter
from datetime import date,datetime
from decimal import Decimal
from itertools import chain
from pathlib import Path

from equity_research.concept_diagnostics import inspect_concepts
from equity_research.evidence_bundle import read_bundle
from equity_research.filingcheck import filing_derived_liabilities
from equity_research.mvp import save_json


def run():
    root=Path(__file__).resolve().parents[1];dest=root/'docs/evidence/current-score100'
    report=json.loads(gzip.decompress((dest/'report.json.gz').read_bytes()))
    requested={c['issuer_id']:c for c in report['companies'] if c['total_score'] is not None}
    documents={}
    for path in ('docs/evidence/mvp100/documents.json','docs/evidence/common-financial17/documents.json.gz'):
        b=(root/path).read_bytes();cohort=json.loads(gzip.decompress(b) if path.endswith('.gz') else b)
        for c in cohort['companies']:
            if c['issuer_id'] in requested:
                if c['issuer_id'] in documents:raise ValueError('ambiguous original annual')
                documents[c['issuer_id']]=c
    needed={c['source_evidence']['url']:c for c in documents.values()};bodies={}
    for response in chain(read_bundle(root/'tests/fixtures/mvp100-sources'),read_bundle(root/'tests/fixtures/common-extra-sources')):
        row=needed.get(response.url)
        if row and (response.sha256,response.retrieved_at.isoformat())==(row['source_evidence']['sha256'],row['source_evidence']['retrieved_at']):bodies[row['issuer_id']]=response
    checks=[]
    for cik,c in requested.items():
        source=bodies[cik]
        confirmations=c['evidence']['financial_confirmations']
        derived=[x for x in confirmations if x.get('confirmation_method')=='original_filing_balance_equation']
        selected=[x['selected'] for x in confirmations if x not in derived]+[c['evidence']['growth']['inputs'][1]]
        groups={}
        for fact in selected:groups.setdefault((fact['period_start'],fact['period_end']),[]).append(fact)
        for (start,end),facts in groups.items():
            original=inspect_concepts(source.body,cik=cik,concepts=[f['accounting_definition'] for f in facts],
                period_start=date.fromisoformat(start) if start else None,period_end=date.fromisoformat(end))
            for fact,raw in zip(facts,original['concepts']):
                matched=raw['status']=='exact_original_value' and Decimal(raw['value'])==Decimal(fact['value'])
                checks.append(dict(symbol=c['symbol'],issuer_id=cik,field=fact['field'],period_start=start,period_end=end,
                    currency='USD',selected_value=fact['value'],original=raw,status='matched' if matched else 'unresolved_or_mismatch',
                    original_url=source.url,original_sha256=source.sha256,original_retrieved_at=source.retrieved_at.isoformat()))
        for item in derived:
            fact=item['selected'];proof=filing_derived_liabilities(source.body,cik=cik,period_end=date.fromisoformat(fact['period_end']))
            matched=Decimal(proof['value'])==Decimal(fact['value']) and proof=={k:v for k,v in item['confirmation'].items()
                if k not in ('source_url','retrieved_at')}
            checks.append(dict(symbol=c['symbol'],issuer_id=cik,field='liabilities',period_start=None,
                period_end=fact['period_end'],currency='USD',selected_value=fact['value'],original=proof,
                confirmation_method='original_filing_balance_equation',status='matched' if matched else 'unresolved_or_mismatch',
                original_url=source.url,original_sha256=source.sha256,original_retrieved_at=source.retrieved_at.isoformat()))
    result=dict(mode='recorded_original_annual_reconciliation',new_http_requests=0,scored_companies=len(requested),
        summary=dict(Counter(r['status'] for r in checks)),checks=checks,mvp_accepted=False)
    save_json(dest/'original-annual-checks.json',result)
    print(json.dumps({k:v for k,v in result.items() if k!='checks'}))
    return result


if __name__=='__main__':run()
