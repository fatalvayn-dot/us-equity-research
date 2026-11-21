"""Offline original-source replay, never a new live run or historical vintage."""
import argparse
import gzip
import json
import tempfile
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path

from equity_research.batch import BatchRunner, BatchStore, load_plan
from equity_research.cache import encode
from equity_research.companyfacts import SecCompanyFacts, companyfacts_url
from equity_research.comparative import comparison_plan, build_comparative_report, render_comparative_markdown
from equity_research.evidence_bundle import read_bundle
from equity_research.providers import ProviderFailure, Resolver
from equity_research.transport import Response
from equity_research.yahoo import YahooAssets


def run(documents, sources, output):
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    needed = {r['source_evidence']['url'] for r in documents['companies'] if r.get('period')}
    needed.update(companyfacts_url(r['issuer_id']) for r in documents['companies'] if r.get('period'))
    with tempfile.TemporaryDirectory() as temporary:
        index = {}; directory = Path(temporary)
        # Bound memory to one source body; immutable original bytes stay in the bundle.
        for response in read_bundle(sources):
            if response.url not in needed: continue
            path = directory / response.sha256
            path.write_bytes(response.body)
            index.setdefault(response.url, []).append((response.retrieved_at, response.sha256))
        def restore(url, sha=None, observed=None):
            rows = index.get(url, [])
            if sha is not None:
                rows = [r for r in rows if r[1] == sha and r[0] == datetime.fromisoformat(observed)]
            if not rows: return None
            stamp, digest = max(rows)
            return Response(url, (directory/digest).read_bytes(), stamp)
        cutoff = datetime.now(timezone.utc)
        if any(stamp > cutoff for rows in index.values() for stamp, _ in rows):
            raise ValueError('future source observation')
        plans = []; selected = {}; deferred = []
        for row in documents['companies']:
            if not row.get('period'):
                deferred.append(dict(symbol=row['symbol'], issuer_id=row['issuer_id'], status='verified_annual_period_unavailable')); continue
            evidence = row['source_evidence']
            doc = restore(evidence['url'], evidence['sha256'], evidence['retrieved_at'])
            financial = restore(companyfacts_url(row['issuer_id']))
            if doc is None or financial is None:
                deferred.append(dict(symbol=row['symbol'], issuer_id=row['issuer_id'], status='original_source_unavailable')); continue
            try:
                result = comparison_plan(doc, financial, issuer_id=row['issuer_id'], symbol=row['symbol'], annual=row['annual'], as_of=cutoff)
            except ProviderFailure as exc:
                deferred.append(dict(symbol=row['symbol'], issuer_id=row['issuer_id'], status=exc.status.value)); continue
            plans.append(result)
            if result['status'] == 'ready_for_ordered_collection': selected[row['issuer_id']] = financial
        # Actual adapter contracts and ordered resolver, using only recorded bytes.
        class ReplayTransport:
            max_bytes = 16_000_000
            def __init__(self, response): self.response = response
            def get(self, url):
                if url != self.response.url: raise ValueError('unrecorded replay URL')
                return self.response
        resolvers = {}
        for cik, response in selected.items():
            sec = SecCompanyFacts(ReplayTransport(response), clock=lambda:cutoff, ttl=timedelta.max)
            # Duration fields are locally unsupported before identity/network work.
            yahoo = YahooAssets(None, directory=None, symbol=next(p['symbol'] for p in plans if p['issuer_id'] == cik), clock=lambda:cutoff)
            resolvers[cik] = Resolver([yahoo, sec], clock=lambda:cutoff)
        batches = {}
        store = BatchStore(':memory:')
        try:
            for side in ('current', 'prior'):
                plan = dict(schema_version=1, companies=[p[side+'_plan']['companies'][0] for p in plans if p['status'] == 'ready_for_ordered_collection'])
                (output/(side+'-plan.json')).write_text(json.dumps(plan, indent=2)+'\n')
                batch = BatchRunner(store, lambda c:resolvers[c.issuer_id], clock=lambda:cutoff).run(load_plan(plan))
                batch.update(evidence_mode='offline_original_source_replay', new_http_requests=0)
                batches[side] = batch
                (output/(side+'-batch.json.gz')).write_bytes(gzip.compress(json.dumps(batch, default=encode, sort_keys=True).encode(), mtime=0))
        finally: store.close()
        report = build_comparative_report(batches['current'], batches['prior'])
        report.update(evidence_mode='offline_original_source_replay', new_http_requests=0, freshness_accepted=False)
        (output/'report.json.gz').write_bytes(gzip.compress(json.dumps(report, default=encode, sort_keys=True).encode(), mtime=0))
        audit = dict(schema_version=1, evidence_mode='offline_original_source_replay', new_http_requests=0,
                     candidates=len(documents['companies']), as_of=cutoff.isoformat(), plans=plans, deferred=deferred,
                     freshness_accepted=False, replay_cache_policy='recorded bytes retained regardless of age; no live freshness acceptance',
                     summary=report['summary'], plan_states=dict(Counter(p['status'] for p in plans)),
                     calculation_states=dict(Counter(c['status'] for r in report['companies'] for c in r['calculations'])),
                     current_facts=sum(c['accepted_fact_count'] for c in report['current_evidence']['companies']),
                     prior_facts=sum(c['accepted_fact_count'] for c in report['prior_evidence']['companies']),
                     mvp_accepted=False, source_priority='Yahoo->SEC->Nasdaq->Finnhub; stop at first valid')
        (output/'audit.json').write_text(json.dumps(audit, default=encode, indent=2)+'\n')
        (output/'report.md').write_text(render_comparative_markdown(report))
        return {k:v for k,v in audit.items() if k not in ('plans', 'deferred')}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--documents', default='docs/evidence/mvp100/documents.json')
    parser.add_argument('--sources', default='tests/fixtures/mvp100-sources')
    parser.add_argument('--output', default='docs/evidence/comparative100')
    args = parser.parse_args()
    print(json.dumps(run(json.loads(Path(args.documents).read_text()), args.sources, args.output), default=encode))
