"""Export five exact original-filing liability equation proofs; no network."""
import gzip
import json
import tempfile
from datetime import date
from itertools import chain
from pathlib import Path

from equity_research.evidence_bundle import read_bundle,write_bundle
from equity_research.filingcheck import filing_derived_liabilities
from equity_research.mvp import save_json
from equity_research.response_archive import ResponseArchive

ROOT=Path(__file__).resolve().parents[1]
SYMBOLS=frozenset({'AMD','INTC','ADI','CDNS','ADSK'})


def read(path):
    body=path.read_bytes()
    return json.loads(gzip.decompress(body) if path.suffix=='.gz' else body)


def run():
    documents={}
    for path in (ROOT/'docs/evidence/mvp100/documents.json',
                 ROOT/'docs/evidence/common-financial17/documents.json.gz'):
        for row in read(path)['companies']:
            if row['symbol'] in SYMBOLS:
                if row['symbol'] in documents:raise ValueError('ambiguous annual document')
                documents[row['symbol']]=row
    if set(documents)!=SYMBOLS:raise ValueError('five annual documents required')
    wanted={row['source_evidence']['url']:row for row in documents.values()};responses={}
    bundles=(ROOT/'tests/fixtures/mvp100-sources',ROOT/'tests/fixtures/common-extra-sources')
    for response in chain.from_iterable(read_bundle(path) for path in bundles):
        document=wanted.get(response.url)
        if document is None:continue
        expected=document['source_evidence']
        if response.sha256!=expected['sha256'] or response.retrieved_at.isoformat()!=expected['retrieved_at']:
            raise ValueError('annual source observation differs')
        if response.url in responses:raise ValueError('duplicate annual source observation')
        responses[response.url]=response
    if set(responses)!=set(wanted):raise ValueError('annual source body missing')
    batch=read(ROOT/'docs/evidence/common-financial100/batch.json.gz')
    selected={row['symbol']:next(field['fact'] for field in row['fields']
        if field['query']['field']=='liabilities') for row in batch['companies'] if row['symbol'] in SYMBOLS}
    checks=[]
    for symbol in sorted(SYMBOLS):
        document=documents[symbol];response=responses[document['source_evidence']['url']]
        proof=filing_derived_liabilities(response.body,cik=document['issuer_id'],
            period_end=date.fromisoformat(document['annual']['report_end']))
        fact=selected[symbol]
        if proof['value']!=fact['value']:raise ValueError('selected liabilities do not match equation')
        checks.append(dict(symbol=symbol,issuer_id=document['issuer_id'],selected=fact,
            confirmation=dict(**proof,source_url=response.url,retrieved_at=response.retrieved_at.isoformat()),
            status='matched'))
    target=ROOT/'tests/fixtures/liability-equation5-sources'
    with tempfile.TemporaryDirectory() as folder:
        archive=ResponseArchive(Path(folder)/'sources.sqlite')
        try:
            for response in responses.values():archive.record(response)
            manifest=write_bundle(archive,target)
        finally:archive.close()
    result=dict(schema_version=1,mode='recorded_original_filing_balance_equation_confirmation',
        companies=checks,summary=dict(candidates=5,matched=5,rejected=0),new_http_requests=0,
        source_bundle=manifest,automatic_substitution=False,mvp_accepted=False,
        hundred_active_common_shares_accepted=False)
    output=ROOT/'docs/evidence/liability-equation5';output.mkdir(parents=True,exist_ok=True)
    save_json(output/'report.json',result)
    print(json.dumps(result['summary']))
    return result


if __name__=='__main__':run()
