"""Collect explicit replacement covers and current public membership evidence, no scoring."""
import argparse,json,gzip
from datetime import datetime,timezone,timedelta
from pathlib import Path
from equity_research.batch import BatchStore
from equity_research.evidence_bundle import write_bundle
from equity_research.mvp import save_json
from equity_research.nasdaq import NasdaqDirectories,DIRECTORY_ENDPOINTS,parse_directory as parse_listing
from equity_research.prices import cached_response
from equity_research.providers import ProviderFailure
from equity_research.response_archive import ResponseArchive,ArchivedTransport
from equity_research.sec import DIRECTORY_URL,parse_directory
from equity_research.submissions import submissions_url,parse_submissions
from equity_research.transport import RateLimiter

SYMBOLS=('ADBE','INTU','NOW','SNPS','CDNS','FTNT','WDAY','ADSK','ROP','MCHP','MPWR','ON','TER','SWKS','NTAP','AKAM','FFIV','TYL')

def run(path,user_agent):
    path=Path(path);path.mkdir(parents=True,exist_ok=True)
    lock=BatchStore(path/'run-lock.sqlite');archive=ResponseArchive(path/'sources.sqlite');owner=None
    now=lambda:datetime.now(timezone.utc)
    calls=0;events=[]
    try:
        owner=lock.acquire(now(),timedelta(minutes=15));limiter=RateLimiter(.6)
        class Recording(ArchivedTransport):
            def get(self,url):
                nonlocal calls
                lock.renew(owner,now(),timedelta(minutes=15))
                cached=cached_response(archive,url,now(),timedelta(hours=6))
                if cached is not None:return cached
                calls+=1
                return super().get(url)
        def transport(hosts):return Recording(archive=archive,user_agent=user_agent,allowed_hosts=hosts,limiter=limiter,max_attempts=2,timeout=10,budget=25)
        listing=NasdaqDirectories(transport({'www.nasdaqtrader.com','ftp.nasdaqtrader.com'}))
        # Reuse still-valid original official membership observations without
        # rewriting their dates. Fresh retrieval failure must not fabricate data.
        root=Path(__file__).resolve().parents[1]
        for row in json.loads((root/'docs/evidence/scope-primary-snapshots.json').read_text())['sources']:
            if 'nasdaqtrader.com' not in row['url']:continue
            from equity_research.transport import Response
            response=Response(row['url'],gzip.decompress((root/row['fixture']).read_bytes()),datetime.fromisoformat(row['retrieved_at']))
            if response.sha256!=row['sha256']:raise ValueError('listing seed hash mismatch')
            archive.record(response)
        cached_listings=[]
        for name,urls in DIRECTORY_ENDPOINTS.items():
            available=[cached_response(archive,url,now(),timedelta(days=4)) for url in urls]
            available=[r for r in available if r is not None]
            if available:
                response=max(available,key=lambda r:r.retrieved_at);parse_listing(response,name);cached_listings.append(response)
        if len(cached_listings)!=2:listing.fetch()
        else:
            listing.attempts=[dict(url=r.url,status='valid_recorded_membership',http_requested=False,retrieved_at=r.retrieved_at) for r in cached_listings]
        sec=transport({'www.sec.gov','data.sec.gov'})
        identity=parse_directory(sec.get(DIRECTORY_URL));candidates=[]
        for symbol in SYMBOLS:
            entry=identity.lookup(symbol)
            if entry is None:
                events.append(dict(symbol=symbol,status='identity_not_found'));continue
            row=dict(symbol=symbol,issuer_id=entry.issuer.cik);candidates.append(row)
            try:
                response=sec.get(submissions_url(row['issuer_id']));snapshot=parse_submissions(response,row['issuer_id'])
                if symbol not in snapshot.tickers:raise ValueError('metadata symbol mismatch')
                annual=snapshot.latest_annual()
                if annual is None:events.append(dict(**row,status='no_annual_in_recent_window'));continue
                filing=sec.get(annual.source_url)
                events.append(dict(**row,status='source_bodies_collected',filing_url=filing.url,raw_sha256=filing.sha256))
            except (ProviderFailure,ValueError,KeyError) as exc:
                events.append(dict(**row,status=exc.status.value if isinstance(exc,ProviderFailure) else 'invalid_data'))
            print(json.dumps(events[-1]),flush=True)
        write_bundle(archive,path/'source-bundle')
        save_json(path/'collection.json',dict(candidates=candidates,events=events,new_get_invocations=calls,listing_attempts=listing.attempts,as_of=now(),mvp_accepted=False))
    finally:
        if owner is not None:lock.release(owner)
        archive.close();lock.close()

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--state-dir',default='data/common-extra');p.add_argument('--user-agent',required=True)
    args=p.parse_args();run(args.state_dir,args.user_agent)
