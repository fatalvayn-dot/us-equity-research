"""Bounded three-company source check, plus deterministic report from archived bodies.

No installed credentials, authenticated endpoints or access workarounds. Working
SQLite checkpoints remain ignored; only exported public response evidence is portable.
"""
import argparse
import gzip
import json
import re
from datetime import datetime,timezone
from pathlib import Path

from equity_research.cache import encode
from equity_research.companyfacts import companyfacts_url
from equity_research.evidence_bundle import read_bundle,write_bundle
from equity_research.mvp import save_json,save_text
from equity_research.prices import run_prices,cached_response
from equity_research.providers import ProviderFailure,Status
from equity_research.response_archive import ResponseArchive,ArchivedTransport
from equity_research.submissions import submissions_url,parse_submissions
from equity_research.transport import RateLimiter,strict_json
from equity_research.valuation import disclosed_shares,build_valuation_report,render_valuation_markdown,SNAPSHOT_TTL

ROOT=Path(__file__).resolve().parents[1]
SAMPLE=[dict(symbol='AAPL',issuer_id='0000320193'),dict(symbol='MSFT',issuer_id='0000789019'),dict(symbol='NVDA',issuer_id='0001045810')]


def _run(state_dir,user_agent):
    state_dir=Path(state_dir);state_dir.mkdir(parents=True,exist_ok=True)
    archive=ResponseArchive(state_dir/'sources.sqlite');events=[];calls=0
    limiter=RateLimiter(0.6)
    transports={host:ArchivedTransport(archive=archive,user_agent=user_agent,allowed_hosts={host},
        limiter=limiter,timeout=10,budget=25,max_attempts=2) for host in ('data.sec.gov','www.sec.gov')}
    def get(url,host):
        nonlocal calls
        cached=cached_response(archive,url,datetime.now(timezone.utc),SNAPSHOT_TTL)
        if cached is not None:return cached
        calls+=1
        return transports[host].get(url)
    try:
        for row in SAMPLE:
            cik=row['issuer_id']
            try:
                cf=get(companyfacts_url(cik),'data.sec.gov')
                shares=disclosed_shares(cf,cik=cik,as_of=datetime.now(timezone.utc))
                if shares is None:raise ProviderFailure(Status.MISSING)
                meta=get(submissions_url(cik),'data.sec.gov');parse_submissions(meta,cik)
                recent=strict_json(meta.body)['filings']['recent'];i=recent['accessionNumber'].index(shares['accession'])
                document=recent['primaryDocument'][i]
                if not re.fullmatch(r'[A-Za-z0-9_-][A-Za-z0-9_.-]*',document) or '..' in document:raise ValueError('unsafe document')
                url=f'https://www.sec.gov/Archives/edgar/data/{int(cik)}/{shares["accession"].replace("-", "")}/{document}'
                get(url,'www.sec.gov')
                events.append(dict(**row,status='source_bodies_collected',share_date=shares['end'].isoformat()))
            except (ProviderFailure,ValueError,KeyError) as exc:
                events.append(dict(**row,status='source_collection_failed',provider_status=exc.status.value if isinstance(exc,ProviderFailure) else 'invalid_data'))
            print(json.dumps(events[-1]),flush=True)
        try:
            prices=run_prices(dict(companies=SAMPLE),state_dir=state_dir/'prices',user_agent=user_agent,max_new_prices=3)
            price_archive=ResponseArchive(state_dir/'prices/sources.sqlite')
            try:
                for item in price_archive.observations():
                    archive.record(price_archive.get(item['url'],item['sha256'],datetime.fromisoformat(item['retrieved_at'])))
            finally:price_archive.close()
        except ProviderFailure as exc:
            prices=dict(summary=dict(collected_prices=0),provider_status=exc.status.value)
        cutoff=datetime.now(timezone.utc)
        bundle=state_dir/'source-bundle';write_bundle(archive,bundle)
        batch=json.loads(gzip.decompress((ROOT/'docs/evidence/liquidity100/batch.json.gz').read_bytes()))
        report=build_valuation_report(batch,read_bundle(bundle),as_of=cutoff)
        save_json(state_dir/'report.json',report);save_text(state_dir/'report.md',render_valuation_markdown(report))
        save_json(state_dir/'audit.json',dict(source_get_invocations=calls,collection=events,
            price_summary=prices['summary'],new_price_get_invocations=prices['summary'].get('new_price_get_invocations'),
            new_identity_get_invocations=prices.get('new_identity_get_invocations'),evidence_cutoff=cutoff.isoformat(),
            financial_input_mode='retained_recorded_annual_batch_not_refreshed',fresh_100_company_acceptance=False))
        print(json.dumps(report['summary']),flush=True)
    finally:archive.close()


def run(state_dir,user_agent):
    from equity_research.batch import BatchStore
    from datetime import timedelta
    path=Path(state_dir);path.mkdir(parents=True,exist_ok=True)
    lock=BatchStore(path/'run-lock.sqlite');owner=None
    try:
        owner=lock.acquire(datetime.now(timezone.utc),timedelta(minutes=15))
        _run(path,user_agent)
    finally:
        if owner is not None:lock.release(owner)
        lock.close()


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--state-dir',default='data/valuation-sample')
    parser.add_argument('--user-agent',required=True)
    args=parser.parse_args();run(args.state_dir,args.user_agent)
