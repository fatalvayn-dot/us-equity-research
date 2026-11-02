"""Bounded live market refresh followed by a 100-candidate recorded-financial score run."""
import argparse
import gzip
import json
from datetime import datetime,timezone,timedelta
from pathlib import Path

from equity_research.batch import BatchStore
from equity_research.evidence_bundle import read_bundle,write_bundle
from equity_research.market_history import history_url
from equity_research.mvp import save_json,save_text
from equity_research.prices import cached_response,PRICE_TTL,price_url
from equity_research.providers import ProviderFailure
from equity_research.response_archive import ResponseArchive,ArchivedTransport
from equity_research.scoring import build_score_report,render_score_markdown
from equity_research.sec import DIRECTORY_URL
from verify_valuation_inputs import run as refresh_valuation_inputs

ROOT=Path(__file__).resolve().parents[1]
SAMPLE=[dict(symbol='AAPL',issuer_id='0000320193'),dict(symbol='MSFT',issuer_id='0000789019'),dict(symbol='NVDA',issuer_id='0001045810')]


def run(state_dir,user_agent):
    state=Path(state_dir);state.mkdir(parents=True,exist_ok=True)
    lock=BatchStore(state/'run-lock.sqlite');owner=None;archive=None
    try:
        owner=lock.acquire(datetime.now(timezone.utc),timedelta(minutes=15))
        fundamental_state=state/'fundamentals';fundamental_state.mkdir(parents=True,exist_ok=True)
        # Seed original observations without changing their times. The existing
        # live collector refreshes expired SEC/quote data; a six-hour-old fixture
        # must not permanently prevent future live runs from collecting inputs.
        seed=ResponseArchive(fundamental_state/'sources.sqlite')
        price_seed=ResponseArchive(fundamental_state/'prices/sources.sqlite')
        try:
            for response in read_bundle(ROOT/'tests/fixtures/valuation-sources'):
                seed.record(response)
                if response.url==DIRECTORY_URL or response.url in {price_url(r['symbol']) for r in SAMPLE}:price_seed.record(response)
            if (state/'prices/sources.sqlite').exists():
                old_prices=ResponseArchive(state/'prices/sources.sqlite')
                try:
                    for item in old_prices.observations():price_seed.record(old_prices.get(item['url'],item['sha256'],datetime.fromisoformat(item['retrieved_at'])))
                finally:old_prices.close()
        finally:seed.close();price_seed.close()
        refresh_valuation_inputs(fundamental_state,user_agent)
        prices=json.loads((fundamental_state/'prices/report.json').read_text())
        fundamental_audit=json.loads((fundamental_state/'audit.json').read_text())
        archive=ResponseArchive(state/'market-sources.sqlite')
        price_archive=ResponseArchive(fundamental_state/'prices/sources.sqlite')
        try:
            for row in price_archive.observations():archive.record(price_archive.get(row['url'],row['sha256'],datetime.fromisoformat(row['retrieved_at'])))
        finally:price_archive.close()
        transport=ArchivedTransport(archive=archive,user_agent=user_agent,allowed_hosts={'query1.finance.yahoo.com'},timeout=10,budget=25,max_attempts=2)
        calls=0;events=[]
        for row in prices['companies']:
            if row['price'] is None:
                events.append(dict(symbol=row['symbol'],status='price_unavailable_history_unattempted'));continue
            url=history_url(row['symbol']);now=datetime.now(timezone.utc)
            response=cached_response(archive,url,now,PRICE_TTL)
            if response is not None and response.retrieved_at<datetime.fromisoformat(row['price']['market_at']):response=None
            try:
                if response is None:calls+=1;response=transport.get(url)
                events.append(dict(symbol=row['symbol'],status='history_body_collected',raw_sha256=response.sha256,retrieved_at=response.retrieved_at.isoformat()))
            except ProviderFailure as exc:events.append(dict(symbol=row['symbol'],status=exc.status.value))
            print(json.dumps(events[-1]),flush=True)
        bundle=state/'market-bundle';write_bundle(archive,bundle)
        def read(path):return json.loads(gzip.decompress(path.read_bytes()))
        cutoff=datetime.now(timezone.utc)
        responses=list(read_bundle(fundamental_state/'source-bundle'))+list(read_bundle(bundle))
        report=build_score_report(read(ROOT/'docs/evidence/liquidity100/batch.json.gz'),
            read(ROOT/'docs/evidence/comparative100/current-batch.json.gz'),read(ROOT/'docs/evidence/comparative100/prior-batch.json.gz'),responses,as_of=cutoff)
        save_json(state/'report.json',report);save_text(state/'report.md',render_score_markdown(report))
        save_json(state/'audit.json',dict(evidence_cutoff=cutoff,history_get_invocations=calls,
            sec_source_get_invocations=fundamental_audit['source_get_invocations'],
            quote_get_invocations=fundamental_audit['new_price_get_invocations'],identity_get_invocations=fundamental_audit['new_identity_get_invocations'],
            events=events,mode='live_market_refresh_with_recorded_financial_inputs',fresh_100_company_acceptance=False))
        print(json.dumps(report['summary']),flush=True)
    finally:
        if archive is not None:archive.close()
        if owner is not None:lock.release(owner)
        lock.close()


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--user-agent',required=True);parser.add_argument('--state-dir',default='data/research-score')
    args=parser.parse_args();run(args.state_dir,args.user_agent)
