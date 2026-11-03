"""Resumable live metadata -> explicit periods -> ordered facts -> sourced reports."""
import json
import os
import re
import tempfile
from collections import Counter
from dataclasses import asdict
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from .batch import BatchRunner, BatchStore, load_plan
from .cache import encode
from .documents import DocumentRunner, FilingStore
from .fields import SPECS
from .pipeline import research_resolver
from .providers import ProviderFailure, Status
from .reporting import build_report, render_markdown
from .response_archive import ResponseArchive, ArchivedTransport
from .sec import SecDirectory
from .sector_policy import assess_profile
from .submissions import SecSubmissions
from .transport import RateLimiter, Response

FIELDS = ('revenue','assets','liabilities','net_income','operating_cash_flow','capital_expenditure',
          'revenue_total','profit_loss','productive_asset_cash_payments',
          'current_assets','current_liabilities','cash_equivalents','operating_income','gross_profit')


def save_json(path, payload):
    save_text(path, json.dumps(payload, default=encode, indent=2)+'\n')


def save_text(path, content):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True);temporary=None
    try:
        with tempfile.NamedTemporaryFile(mode='w',encoding='utf-8',dir=path.parent,delete=False) as f:
            temporary=f.name;f.write(content);f.flush();os.fsync(f.fileno())
        os.replace(temporary,path)
    finally:
        if temporary and os.path.exists(temporary):os.unlink(temporary)


def validate_candidates(payload):
    rows=payload['companies']
    if not isinstance(rows,list) or not 1<=len(rows)<=100:
        raise ValueError('MVP requires 1..100 explicit candidates')
    symbols=set();ciks=set()
    for row in rows:
        cik=row['issuer_id'];symbol=row['symbol']
        if not isinstance(cik,str) or not re.fullmatch(r'[0-9]{10}',cik) or int(cik)==0 or not isinstance(symbol,str) or not symbol or symbol!=symbol.strip():
            raise ValueError('exact company identity required')
        if cik in ciks or symbol in symbols:raise ValueError('duplicate issuer or symbol')
        symbols.add(symbol);ciks.add(cik)
    return [dict(symbol=r['symbol'],issuer_id=r['issuer_id']) for r in rows]


def financial_plan(metadata, documents):
    """Explicit annual end supports instants; durations require original document start."""
    by_cik={r['issuer_id']:r for r in documents['companies']}
    plans=[];unresolved=[];deferred={}
    for row in metadata:
        base=dict(symbol=row['symbol'],issuer_id=row['issuer_id'],scope_status='pending_scope',
                  scope_reason='active_common_share_and_sector_model_review_required')
        if row['status']!='metadata_available_legal_type_pending':
            unresolved.append(dict(**base,fields=[],pending_reason='symbol_mismatch' if row['status']=='symbol_mismatch' else 'metadata_unavailable'))
            continue
        annual=row.get('annual')
        if not annual:
            unresolved.append(dict(**base,fields=[],pending_reason='no_annual_in_recent_window'))
            continue
        doc=by_cik.get(row['issuer_id'],{});period=doc.get('period')
        if period and (period['issuer_id']!=row['issuer_id'] or period['period_end']!=annual['report_end']):
            raise ValueError('document period identity mismatch')
        start=period['period_start'] if period else None
        fields=list(FIELDS) if start else [f for f in FIELDS if SPECS[f].instant]
        if not start:deferred[row['issuer_id']]=[f for f in FIELDS if f not in fields]
        plans.append(dict(**base,period_start=start,period_end=annual['report_end'],currency='USD',fields=fields))
    return dict(schema_version=1,companies=plans),unresolved,deferred


def archive_coverage(batch, archive):
    rows=[]
    for company in batch['companies']:
        for field in company['fields']:
            fact=field.get('fact')
            if not fact:continue
            refs=[('financial',fact['source_url'],fact['raw_sha256'],fact.get('data_observed_at') or fact['retrieved_at'])]
            for prefix in ('identity','unit'):
                if fact.get(prefix+'_evidence_url'):
                    refs.append((prefix,fact[prefix+'_evidence_url'],fact[prefix+'_evidence_sha256'],fact[prefix+'_observed_at']))
            found=[]
            for kind,url,sha,stamp in refs:
                try:ok=archive.get(url,sha,datetime.fromisoformat(stamp)) is not None
                except (ValueError,TypeError):ok=False
                found.append(dict(kind=kind,url=url,sha256=sha,observed_at=stamp,archived=ok))
            rows.append(dict(symbol=company['symbol'],field=fact['field'],references=found))
    return dict(facts=rows,all_references_archived=bool(rows) and all(ref['archived'] for r in rows for ref in r['references']),
                financial_facts=len(rows))


def run_mvp(payload, *, state_dir, user_agent, max_new_documents=100, max_new_fields=None, progress=None, seed_bundles=()):
    candidates=validate_candidates(payload)
    if type(max_new_documents) is not int or not 0<=max_new_documents<=100 or (max_new_fields is not None and (type(max_new_fields) is not int or max_new_fields<0)):
        raise ValueError('bounded document/field work required')
    root=Path(state_dir)
    seed_bundles=tuple(Path(p).resolve() for p in seed_bundles)
    if any(bundle==root.resolve() or bundle in root.resolve().parents for bundle in seed_bundles):
        raise ValueError('working state must not overwrite an input source bundle')
    root.mkdir(parents=True,exist_ok=True)
    lock=BatchStore(root/'run-lock.sqlite');owner=None;archive=None;client=None;documents=None;store=None
    clock=lambda:datetime.now(timezone.utc)
    ttl=timedelta(minutes=15);counts=Counter();limiters={}
    try:
        owner=lock.acquire(clock(),ttl)
        def pulse():lock.renew(owner,clock(),ttl)
        archive=ResponseArchive(root/'responses.sqlite')
        from .evidence_bundle import read_bundle
        from .prices import cached_response
        for bundle in seed_bundles:
            for response in read_bundle(bundle):
                pulse()
                if timedelta(0)<=clock()-response.retrieved_at<=timedelta(hours=6):
                    archive.record(response);counts['seeded_public_observations']+=1
                else:counts['seed_observations_outside_freshness']+=1
        class Recording(ArchivedTransport):
            def get(self,url):
                pulse()
                cached=cached_response(archive,url,clock(),timedelta(hours=6))
                if cached is not None:
                    counts['archived_transport_reuses']+=1
                    return cached
                counts['public_transport_get_calls']+=1
                if progress and counts['public_transport_get_calls']%25==0:
                    progress(dict(phase='public_requests',calls=counts['public_transport_get_calls']))
                return super().get(url)
        def http(hosts,accept='application/json'):
            group='sec' if set(hosts).issubset({'www.sec.gov','data.sec.gov'}) else ','.join(sorted(hosts))
            limiter=limiters.setdefault(group,RateLimiter())
            return Recording(archive=archive,user_agent=user_agent,allowed_hosts=set(hosts),accept=accept,limiter=limiter)
        client=SecSubmissions(http(['data.sec.gov']),cache_path=root/'submissions.sqlite')
        metadata=[]
        for row in candidates:
            pulse();out=dict(row)
            try:
                snapshot=client.fetch(row['issuer_id'])
                if snapshot.cached:
                    saved=client.db.execute('SELECT url,body,sha256,retrieved_at FROM submissions_v1 WHERE cik=?',(row['issuer_id'],)).fetchone()
                    response=Response(saved[0],saved[1],datetime.fromisoformat(saved[3]))
                    if response.sha256!=snapshot.raw_sha256:raise ProviderFailure(Status.EVIDENCE_ERROR)
                    archive.record(response)
                annual=snapshot.latest_annual()
                out.update(status=snapshot.readiness(row['symbol']),snapshot=asdict(snapshot),annual=asdict(annual) if annual else None)
            except ProviderFailure as exc:
                out.update(status=exc.status.value,http_status=exc.http_status)
            metadata.append(out);save_json(root/'metadata.json',dict(companies=metadata))
            if progress:progress(dict(phase='metadata',completed=len(metadata),total=len(candidates)))
        # Only metadata with an exact symbol match can drive financial-period collection.
        normalized=json.loads(json.dumps(metadata,default=encode))
        doc_rows=[r for r in normalized if r['status']=='metadata_available_legal_type_pending']
        class ArchivedFilings(FilingStore):
            def get(self,*args):
                response=super().get(*args)
                if response is not None:archive.record(response)
                return response
        documents=ArchivedFilings(root/'documents.sqlite')
        docs=DocumentRunner(documents,http(['www.sec.gov'],accept='text/html')).run(doc_rows,max_new_documents=max_new_documents)
        save_json(root/'documents.json',docs);pulse()
        if progress:progress(dict(phase='documents',summary=docs['summary']))
        plan,unresolved,deferred=financial_plan(normalized,docs);save_json(root/'plan.json',plan)
        directory=None
        def factory(company):
            nonlocal directory
            pulse()
            if directory is None:directory=SecDirectory(http(['www.sec.gov'])).fetch()
            if directory.lookup(company.symbol,expected_cik=company.issuer_id) is None:
                raise ProviderFailure(Status.SYMBOL_MISMATCH)
            return research_resolver(directory=directory,symbol=company.symbol,user_agent=user_agent,
                cache_dir=root/'companyfacts',response_archive=archive,transport_factory=http)
        store=BatchStore(root/'financial.sqlite')
        if plan['companies']:
            batch=BatchRunner(store,factory).run(load_plan(plan),max_new_fields=max_new_fields)
        else:
            batch=dict(schema_version=1,generated_at=clock().isoformat(),companies=[],summary={})
        for c in batch['companies']:c['deferred_fields']=deferred.get(c['issuer_id'],[])
        batch['companies'].extend(unresolved)
        batch['companies'].sort(key=lambda c:next(i for i,r in enumerate(candidates) if r['issuer_id']==c['issuer_id']))
        batch['summary'].update(companies=len(batch['companies']),financial_query_companies=len(plan['companies']),period_unresolved_companies=len(unresolved))
        save_json(root/'batch.json',batch)
        # Final complete metadata snapshot accompanies the completed batch;
        # intermediate progress files must not be exported as final coverage.
        save_json(root/'metadata.json',dict(companies=normalized));pulse()
        coverage=archive_coverage(batch,archive);save_json(root/'archive-coverage.json',coverage)
        report=build_report(batch)
        report['report_generation_network_requests']=report.pop('new_network_requests')
        report['collection_mode']='live_source_collection' if counts['public_transport_get_calls'] else 'cached_or_unattempted_collection'
        metadata_by_cik={r['issuer_id']:r for r in normalized}
        for company in report['companies']:
            meta=metadata_by_cik[company['issuer_id']]
            snapshot=meta.get('snapshot') if meta['status']=='metadata_available_legal_type_pending' else None
            source=(archive.get(snapshot['source_url'],snapshot['raw_sha256'],datetime.fromisoformat(snapshot['retrieved_at']))
                    if snapshot else None)
            company['sector_profile']=assess_profile(source,issuer_id=company['issuer_id'],as_of=datetime.fromisoformat(report['as_of']))
        report['pipeline']=dict(requested_candidates=len(candidates),metadata_states=dict(Counter(r['status'] for r in metadata)),
            annual_document_summary=docs['summary'],financial_query_companies=len(plan['companies']),
            companies_with_financial_facts=sum(c['accepted_fact_count']>0 for c in report['companies']),
            period_unresolved_companies=len(unresolved),deferred_duration_fields=sum(len(v) for v in deferred.values()),
            public_transport_get_calls=counts['public_transport_get_calls'],
            seeded_public_observations=counts['seeded_public_observations'],
            seed_observations_outside_freshness=counts['seed_observations_outside_freshness'],
            archived_transport_reuses=counts['archived_transport_reuses'],
            call_measure='public transport GET invocations, excluding internal retries and private Finnhub transport',
            all_financial_references_archived=coverage['all_references_archived'],
            archived_financial_facts=coverage['financial_facts'])
        save_json(root/'report.json',report);save_text(root/'report.md',render_markdown(report))
        if progress:progress(dict(phase='report',summary=report['summary'],pipeline=report['pipeline']))
        return report
    finally:
        for resource in (store,documents,client,archive):
            if resource is not None:resource.close()
        if owner:lock.release(owner)
        lock.close()
