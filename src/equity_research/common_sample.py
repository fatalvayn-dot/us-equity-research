"""Source-bound common-share sample admission, separate from financial model approval."""
from collections import Counter
from dataclasses import asdict
from datetime import datetime,timedelta
import re

from .filing_metadata import CoverParser,filing_security_metadata
from .legal_evidence import registered_legal_contraindications
from .models import aware
from .nasdaq import DIRECTORY_ENDPOINTS,parse_directory as parse_listing
from .prices import price_url
from .providers import ProviderFailure
from .scope import audit_sample
from .sec import DIRECTORY_URL,parse_directory
from .submissions import submissions_url,parse_submissions

POLICY='registered-common-sample-v1'
MAX_AGE=timedelta(days=4)
TRANSFORMS={
    'date-month-day-year':{'http://www.xbrl.org/inlineXBRL/transformation/2020-02-12','http://www.xbrl.org/inlineXBRL/transformation/2022-02-16'},
    'date-monthname-day-year-en':{'http://www.xbrl.org/inlineXBRL/transformation/2020-02-12','http://www.xbrl.org/inlineXBRL/transformation/2022-02-16'},
    'datemonthdayyearen':{'http://www.xbrl.org/inlineXBRL/transformation/2011-07-31','http://www.xbrl.org/inlineXBRL/transformation/2015-02-26'}}


def candidate_pool(payload):
    rows=payload['companies']
    if not isinstance(rows,list) or not 1<=len(rows)<=125:raise ValueError('1..125 explicit pool candidates required')
    result=[]
    for row in rows:
        cik,symbol=row['issuer_id'],row['symbol']
        if not isinstance(cik,str) or not re.fullmatch(r'[0-9]{10}',cik) or int(cik)==0:raise ValueError('canonical issuer required')
        price_url(symbol);result.append(dict(symbol=symbol,issuer_id=cik))
    if len({r['symbol'] for r in result})!=len(result) or len({r['issuer_id'] for r in result})!=len(result):
        raise ValueError('duplicate candidate issuer or symbol')
    return result


def strict_cover(response):
    p=CoverParser();p.feed(response.body.decode('utf-8'));p.close()
    if p.conflict or p.context is not None or p.fact_stack:raise ValueError('incomplete original cover')
    if p.namespaces.get('xbrli')!={'http://www.xbrl.org/2003/instance'}:raise ValueError('unverified context namespace')
    if p.namespaces.get('ix') not in ({'http://www.xbrl.org/2013/inlineXBRL'},{'http://www.xbrl.org/2008/inlineXBRL'}):
        raise ValueError('unverified inline namespace')
    for f in p.facts:
        if f['element_tag']!='ix:nonnumeric' or f['nil'] not in (None,'true','false','0','1'):raise ValueError('unverified cover fact')
        if f['name']=='documentperiodenddate' and f['format']:
            prefix,sep,local=f['format'].partition(':')
            bound=p.namespaces.get(prefix,set())
            if not sep or len(bound)!=1 or not bound.issubset(TRANSFORMS.get(local,set())):
                raise ValueError('unverified date transformation namespace')
    return p


def verify_common_sample(payload,responses,*,as_of,target=100):
    rows=candidate_pool(payload)
    if not aware(as_of) or type(target) is not int or not 1<=target<=100:raise ValueError('aware cutoff and target 1..100 required')
    sources={}
    for r in responses:
        if '/api/xbrl/companyfacts/' in r.url or 'finance.yahoo.com/' in r.url:continue
        if not aware(r.retrieved_at):raise ValueError('aware source timestamps required')
        if r.retrieved_at>as_of:continue
        old=sources.get(r.url)
        if old is None or old.retrieved_at<r.retrieved_at:sources[r.url]=r
        elif old.retrieved_at==r.retrieved_at and old.sha256!=r.sha256:raise ValueError('conflicting source observation')
    identity=parse_directory(sources[DIRECTORY_URL]);parts=[]
    for name,urls in DIRECTORY_ENDPOINTS.items():
        available=[sources[url] for url in urls if url in sources]
        if not available:raise ValueError('both original listing directories required')
        parts.append(parse_listing(max(available,key=lambda r:r.retrieved_at),name))
    listing=audit_sample(rows,parts,identity,as_of=as_of,max_age=MAX_AGE)
    companies=[];selected=[]
    for candidate,membership in zip(rows,listing['companies']):
        cik,symbol=candidate['issuer_id'],candidate['symbol']
        row=dict(**candidate,status='review_required',blockers=[],listing=membership,
            scope_approved=False,sector_model_supported=False,investment_approved=False,total_score=None)
        companies.append(row)
        if membership['scope_status']!='listing_evidence_complete_legal_type_pending':
            row['blockers']=['listing_identity_or_instrument_unverified'];continue
        try:
            metadata=sources[submissions_url(cik)]
            if not timedelta(0)<=as_of-metadata.retrieved_at<=MAX_AGE:raise ValueError('stale metadata')
            snapshot=parse_submissions(metadata,cik)
            if symbol not in snapshot.tickers:raise ValueError('metadata symbol mismatch')
            if snapshot.entity_type_label not in ('operating','other') or not snapshot.sic_label or snapshot.sic_label in ('6722','6726','6770','6799'):
                row['blockers']=['issuer_or_investment_company_model_review'];continue
            annual=snapshot.latest_annual()
            if annual is None:row['blockers']=['annual_cover_unavailable'];continue
            if not timedelta(0)<=as_of.date()-annual.report_end<=timedelta(days=550):raise ValueError('stale annual cover')
            filing=sources[annual.source_url]
            if filing.retrieved_at.date()<annual.filed_on:raise ValueError('filing observation precedes filing date')
            p=strict_cover(filing)
            exchange=identity.lookup(symbol,expected_cik=cik).exchange_label
            cover=filing_security_metadata(filing.body,cik=cik,symbol=symbol,report_end=annual.report_end,
                                           document_type=annual.form,expected_exchange=exchange)
            legal=registered_legal_contraindications(filing,cik)
            if legal['blocked']:row['blockers']=['reported_fund_bdc_or_shell'];continue
            row.update(status='verified_registered_common_sample',
                cover=cover,legal_disclosure_review=legal,
                metadata=dict(url=metadata.url,raw_sha256=metadata.sha256,retrieved_at=metadata.retrieved_at,
                    sic=snapshot.sic_label,entity_type=snapshot.entity_type_label,annual=asdict(annual)),
                filing_source=dict(url=filing.url,raw_sha256=filing.sha256,retrieved_at=filing.retrieved_at),
                limitations=['directory membership and exact registered class, not guaranteed tradability',
                    'fund flags absent remain unknown; no legal opinion or economic-model approval'])
            if len(selected)<target:selected.append(candidate)
        except (ProviderFailure,ValueError,KeyError,TypeError,UnicodeError) as exc:
            row['blockers']=['original_cover_metadata_context_or_period_unverified']
            row['provider_status']=exc.status.value if isinstance(exc,ProviderFailure) else 'invalid_data'
    return dict(schema_version=1,policy=POLICY,as_of=as_of,target=target,companies=companies,
        candidate_plan=dict(companies=selected),summary=dict(evaluated=len(companies),selected=len(selected),
            states=dict(Counter(c['status'] for c in companies))),
        target_sample_verified=len(selected)==target,
        hundred_common_share_sample_verified=target==100 and len(selected)==100,
        active_universe_accepted=False,mvp_accepted=False,
        limitations=['sample membership only; financial, price, sector and risk acceptance remain separate',
            'no fabricated scores or active-trading guarantee'])
