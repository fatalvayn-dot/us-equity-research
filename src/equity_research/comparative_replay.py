"""Reproducible annual comparisons from recorded public bytes, never live acceptance."""
import re
import tempfile
from collections import Counter
from datetime import datetime, timedelta
from pathlib import Path

from .batch import BatchRunner, BatchStore, load_plan
from .comparative import comparison_plan, build_comparative_report
from .companyfacts import SecCompanyFacts, companyfacts_url
from .models import aware
from .mvp import validate_candidates
from .nasdaq_financials import NasdaqFinancials
from .providers import ProviderFailure, Resolver
from .transport import Response
from .yahoo import YahooAssets


def replay_comparisons(candidates, documents, responses, *, as_of):
    """Reparse exact annual bodies and select explicit adjacent full-year pairs.

    Sources may be older than a live cache TTL. Original dates/hashes are retained;
    no freshness, historical-vintage, common-share or economic-model approval is
    implied. Candidate order and unresolved candidates are retained in both sides.
    """
    rows = validate_candidates(candidates)
    if not aware(as_of):
        raise ValueError('explicit aware replay cutoff required')
    requested = {r['issuer_id']: r['symbol'] for r in rows}
    selected = {}
    for cohort in documents:
        for row in cohort['companies']:
            cik = row['issuer_id']
            if cik not in requested:
                continue
            if row['symbol'] != requested[cik] or cik in selected:
                raise ValueError('ambiguous document identity or symbol mismatch')
            selected[cik] = row
    needed = {companyfacts_url(cik) for cik in requested}
    needed.update(r['source_evidence']['url'] for r in selected.values() if r.get('period'))
    plans = []; deferred = []; discoveries = {}; snapshots = {}
    with tempfile.TemporaryDirectory() as temporary:
        folder = Path(temporary); index = {}
        # Stream only required bodies to disk; validate duplicate observation keys.
        for response in responses:
            if response.url not in needed:
                continue
            if not aware(response.retrieved_at):
                raise ValueError('aware source observation required')
            key = (response.url, response.retrieved_at)
            digest = response.sha256
            if key in index and index[key] != digest:
                raise ValueError('conflicting source observation')
            index[key] = digest
            (folder / digest).write_bytes(response.body)

        def restore(url, *, digest=None, observed=None):
            choices = [(stamp, sha) for (source, stamp), sha in index.items()
                       if source == url and stamp <= as_of
                       and (digest is None or digest == sha)
                       and (observed is None or observed == stamp)]
            if not choices:
                return None
            stamp, sha = max(choices)
            return Response(url, (folder / sha).read_bytes(), stamp)

        for candidate in rows:
            cik, symbol = candidate['issuer_id'], candidate['symbol']
            row = selected.get(cik)
            if row is None or not row.get('period'):
                deferred.append(dict(**candidate, status='verified_annual_period_unavailable'))
                continue
            evidence = row['source_evidence']
            if not isinstance(evidence.get('sha256'), str) or not re.fullmatch('[0-9a-f]{64}', evidence['sha256']):
                raise ValueError('exact original document digest required')
            observed = datetime.fromisoformat(evidence['retrieved_at'])
            if not aware(observed):
                raise ValueError('aware original document observation required')
            doc = restore(evidence['url'], digest=evidence['sha256'],
                          observed=observed)
            financial = restore(companyfacts_url(cik))
            if doc is None or financial is None:
                deferred.append(dict(**candidate, status='original_source_unavailable_at_cutoff'))
                continue
            try:
                result = comparison_plan(doc, financial, issuer_id=cik, symbol=symbol,
                                         annual=row['annual'], as_of=as_of)
            except ProviderFailure as exc:
                deferred.append(dict(**candidate, status=exc.status.value))
                continue
            plans.append(result)
            if result['status'] == 'ready_for_ordered_collection':
                discoveries[cik] = result
                snapshots[cik] = financial
        # No real HTTP transport or environment-based credentials are constructed.
        class ReplayTransport:
            max_bytes = 16_000_000
            def __init__(self, response):
                self.response = response
            def get(self, url):
                if url != self.response.url:
                    raise ValueError('unrecorded replay URL')
                return self.response

        resolvers = {}
        for cik, response in snapshots.items():
            symbol = requested[cik]
            sec = SecCompanyFacts(ReplayTransport(response), clock=lambda: as_of,
                                  ttl=timedelta.max)
            resolvers[cik] = Resolver([
                YahooAssets(None, directory=None, symbol=symbol, clock=lambda: as_of),
                sec,
                NasdaqFinancials(None, directory=None, symbol=symbol, clock=lambda: as_of),
            ], clock=lambda: as_of)
        # Finnhub remains explicitly unconfigured; unsupported Yahoo/Nasdaq duration
        # requests are decided locally. Later providers are untouched after success.
        # Infinite replay age is explicit here only; live BatchRunner TTL stays six hours.
        batches = {}; collection_plans = {}
        for side in ('current', 'prior'):
            plan = dict(schema_version=1, companies=[discoveries[r['issuer_id']][side+'_plan']['companies'][0]
                        for r in rows if r['issuer_id'] in discoveries])
            collection_plans[side] = plan
            store = BatchStore(':memory:')
            try:
                batch = (BatchRunner(store, lambda c: resolvers[c.issuer_id], clock=lambda: as_of,
                                      fact_ttl=timedelta.max)
                         .run(load_plan(plan)) if plan['companies'] else
                         dict(schema_version=1, generated_at=as_of.isoformat(), companies=[]))
            finally:
                store.close()
            by_cik = {c['issuer_id']: c for c in batch['companies']}
            batch['companies'] = [by_cik.get(r['issuer_id'], dict(**r, fields=[],
                scope_status='pending_scope', scope_reason='comparison_period_unresolved',
                pending_reason='annual_period_unresolved')) for r in rows]
            batch.setdefault('summary', {})
            batch['summary'].update(companies=len(rows), comparison_period_unresolved=len(rows)-len(discoveries))
            batch.update(evidence_mode='offline_original_source_replay', new_http_requests=0,
                         freshness_accepted=False)
            batches[side] = batch
        report = build_comparative_report(batches['current'], batches['prior'])
        report.update(evidence_mode='offline_original_source_replay', new_http_requests=0,
                      freshness_accepted=False)
        audit = dict(schema_version=1, candidates=len(rows), as_of=as_of.isoformat(),
            evidence_mode='offline_original_source_replay', new_http_requests=0,
            freshness_accepted=False, historical_vintage_accepted=False,
            replay_cache_policy='recorded bytes retain original dates; no live freshness acceptance',
            plans=plans, deferred=deferred, summary=report['summary'],
            plan_states=dict(Counter(p['status'] for p in plans)),
            calculation_states=dict(Counter(c['status'] for r in report['companies'] for c in r['calculations'])),
            current_facts=sum(c['accepted_fact_count'] for c in report['current_evidence']['companies']),
            prior_facts=sum(c['accepted_fact_count'] for c in report['prior_evidence']['companies']),
            source_priority='Yahoo->SEC->Nasdaq->Finnhub; stop at first valid',
            mvp_accepted=False)
        return dict(current_batch=batches['current'], prior_batch=batches['prior'],
                    current_plan=collection_plans['current'], prior_plan=collection_plans['prior'],
                    report=report, audit=audit)
