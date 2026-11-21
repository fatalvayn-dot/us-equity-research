"""Revalidate recorded 100-company inputs, plus optional bounded fresh SEC sample."""
import argparse
import gzip
import json
import tempfile
from dataclasses import asdict
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

from equity_research.batch import BatchRunner, BatchStore, load_plan
from equity_research.cache import encode
from equity_research.companyfacts import SecCompanyFacts, companyfacts_url
from equity_research.concept_diagnostics import inspect_concepts
from equity_research.evidence_bundle import read_bundle, write_bundle
from equity_research.fields import SPECS
from equity_research.models import FactRequest
from equity_research.providers import Resolver, ProviderFailure, Status
from equity_research.yahoo import YahooAssets
from equity_research.nasdaq_financials import NasdaqFinancials
from equity_research.reporting import build_report, render_markdown
from equity_research.response_archive import ResponseArchive, ArchivedTransport
from equity_research.transport import Response

ROOT=Path(__file__).resolve().parents[1]
NEW_FIELDS=('current_assets','current_liabilities','cash_equivalents','operating_income','gross_profit')
SAMPLE=('AAPL','MSFT','NVDA')


def run(output, user_agent=None):
    output=Path(output);output.mkdir(parents=True,exist_ok=True)
    original=json.loads(gzip.decompress((ROOT/'docs/evidence/mvp100/batch.json.gz').read_bytes()))
    documents=json.loads((ROOT/'docs/evidence/mvp100/documents.json').read_text())['companies']
    docs={r['issuer_id']:r for r in documents}
    selected_docs={r['source_evidence']['url']:r['source_evidence'] for r in documents if r['symbol'] in SAMPLE}
    with tempfile.TemporaryDirectory() as tmp:
        tmp=Path(tmp);financial={};annuals={}
        for response in read_bundle(ROOT/'tests/fixtures/mvp100-sources'):
            if response.url in selected_docs:
                e=selected_docs[response.url]
                if (response.sha256,response.retrieved_at.isoformat())==(e['sha256'],e['retrieved_at']):
                    path=tmp/response.sha256;path.write_bytes(response.body)
                    annuals[response.url]=(path,response.retrieved_at)
            if response.url.startswith('https://data.sec.gov/api/xbrl/companyfacts/CIK'):
                cik=response.url.rsplit('CIK',1)[1].split('.')[0]
                if cik not in financial or response.retrieved_at>financial[cik][1]:
                    path=tmp/response.sha256;path.write_bytes(response.body)
                    financial[cik]=(path,response.retrieved_at)
        cutoff=datetime.now(timezone.utc)
        plans=[]
        for c in original['companies']:
            if not c['fields']:continue
            q=c['fields'][0]['query'];row=docs[c['issuer_id']]
            start=row.get('period',{}).get('period_start')
            plans.append(dict(symbol=c['symbol'],issuer_id=c['issuer_id'],period_start=start,
                period_end=q['period_end'],currency='USD',fields=[f for f in NEW_FIELDS if start or SPECS[f].instant]))
        class Replay:
            max_bytes=16_000_000
            def get(self,url):
                cik=url.rsplit('CIK',1)[1].split('.')[0]
                if cik not in financial:raise ProviderFailure(Status.EVIDENCE_ERROR)
                path,stamp=financial[cik]
                return Response(url,path.read_bytes(),stamp)
        def factory(c):
            return Resolver([YahooAssets(None,directory=None,symbol=c.symbol),
                SecCompanyFacts(Replay(),clock=lambda:cutoff,ttl=timedelta.max),
                NasdaqFinancials(None,directory=None,symbol=c.symbol)],clock=lambda:cutoff)
        store=BatchStore(':memory:')
        try:extra=BatchRunner(store,factory,clock=lambda:cutoff).run(load_plan(dict(schema_version=1,companies=plans)))
        finally:store.close()
        extra['evidence_mode']='offline_original_source_replay';extra['new_http_requests']=0
        by_cik={c['issuer_id']:c for c in extra['companies']}
        for c in original['companies']:
            c['fields'].extend(by_cik.get(c['issuer_id'],{}).get('fields',[]))
        original['generated_at']=cutoff.isoformat();original['evidence_mode']='offline_original_source_replay'
        report=build_report(original)
        previous_report=json.loads(gzip.decompress((ROOT/'docs/evidence/mvp100/report.json.gz').read_bytes()))
        profiles={c['issuer_id']:c.get('sector_profile') for c in previous_report['companies']}
        for c in report['companies']:
            if profiles.get(c['issuer_id']):c['sector_profile']=profiles[c['issuer_id']]
        report['sector_profile_evidence_mode']='preserved original metadata review labels; not a new source observation or model approval'
        report['evidence_mode']='offline_original_source_replay';report['fresh_live_acceptance']=False
        (output/'additional-batch.json.gz').write_bytes(gzip.compress(json.dumps(extra,default=encode,sort_keys=True).encode(),mtime=0))
        (output/'batch.json.gz').write_bytes(gzip.compress(json.dumps(original,default=encode,sort_keys=True).encode(),mtime=0))
        (output/'report.json.gz').write_bytes(gzip.compress(json.dumps(report,default=encode,sort_keys=True).encode(),mtime=0))
        (output/'report.md').write_text(render_markdown(report))
        audit=dict(recorded_summary=report['summary'],additional_fields=extra['summary'],new_http_requests_replay=0,
            additional_accepted_facts=sum(f['fact'] is not None for c in extra['companies'] for f in c['fields']),
            source_bundle='tests/fixtures/mvp100-sources/manifest.json',fresh_sample=[])
        if user_agent:
            archive=ResponseArchive(tmp/'live-private.sqlite')
            try:
                provider=SecCompanyFacts(ArchivedTransport(archive=archive,user_agent=user_agent,
                    allowed_hosts={'data.sec.gov'},max_attempts=2,timeout=10,budget=25))
                for symbol in SAMPLE:
                    row=next(c for c in documents if c['symbol']==symbol);cik=row['issuer_id']
                    response,_=provider.snapshot(cik);as_of=datetime.now(timezone.utc)
                    path,stamp=annuals[row['source_evidence']['url']];body=path.read_bytes()
                    archive.record(Response(row['source_evidence']['url'],body,stamp))
                    period=row['period'];observations=[]
                    for field in NEW_FIELDS:
                        spec=SPECS[field];start=None if spec.instant else date.fromisoformat(period['period_start'])
                        request=FactRequest(cik,field,start,date.fromisoformat(period['period_end']),'USD','currency',spec.accounting_definition,as_of)
                        fact=provider.fetch(request)
                        original_value=inspect_concepts(body,cik=cik,concepts=[spec.accounting_definition],period_start=start,period_end=request.period_end)['concepts'][0]
                        observations.append(dict(field=field,fact=asdict(fact) if fact else None,original=original_value,
                            matches=bool(fact and original_value['value'] is not None and fact.value==Decimal(original_value['value']))))
                    audit['fresh_sample'].append(dict(symbol=symbol,issuer_id=cik,annual_source=row['source_evidence'],observations=observations))
                bundle=write_bundle(archive,output/'live-sources')
                audit['fresh_source_observations']=sum(1 for _ in read_bundle(output/'live-sources'))
                audit['fresh_financial_get_invocations']=len(SAMPLE)
            finally:archive.close()
        (output/'audit.json').write_text(json.dumps(audit,default=encode,indent=2)+'\n')
        print(json.dumps({k:v for k,v in audit.items() if k!='fresh_sample'},default=encode))


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--output',default='data/liquidity-verification')
    parser.add_argument('--user-agent')
    args=parser.parse_args();run(args.output,args.user_agent)
