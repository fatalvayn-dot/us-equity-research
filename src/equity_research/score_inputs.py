"""Describe supplied score operands without turning report generation into freshness."""
import hashlib
import json
from collections import Counter
from datetime import datetime

from .cache import encode
from .models import aware


def score_input_provenance(financial, current, prior, *, as_of):
    """Called after batch validation; no caller freshness/approval flags are adopted."""
    if not aware(as_of):
        raise ValueError('aware score cutoff required')
    sources = {}
    financial_ids = {(c['issuer_id'], c['symbol']) for c in financial['companies']}
    for name, batch in (('financial', financial), ('current_comparison', current), ('prior_comparison', prior)):
        generated = datetime.fromisoformat(batch['generated_at'])
        if not aware(generated) or generated > as_of:
            raise ValueError('input batch generation exceeds score cutoff')
        observations = []; providers = Counter()
        for company in batch['companies']:
            for field in company['fields']:
                fact = field.get('fact')
                if fact is None or field['state'] != 'collected':
                    continue
                observed = datetime.fromisoformat(fact.get('data_observed_at') or fact['retrieved_at'])
                if not aware(observed) or observed > as_of:
                    raise ValueError('future selected input observation')
                observations.append(observed); providers[fact['source']] += 1
        identities = {(c['issuer_id'], c['symbol']) for c in batch['companies']}
        sources[name] = dict(
            sha256=hashlib.sha256(json.dumps(batch, default=encode, sort_keys=True, separators=(',', ':')).encode()).hexdigest(),
            generated_at=generated.isoformat(), candidates=len(identities), selected_facts=len(observations),
            selected_by_source=dict(providers),
            oldest_selected_observation=min(observations).isoformat() if observations else None,
            newest_selected_observation=max(observations).isoformat() if observations else None,
            missing_financial_identities=[dict(issuer_id=cik, symbol=symbol) for cik, symbol in sorted(financial_ids-identities)],
            additional_identities=[dict(issuer_id=cik, symbol=symbol) for cik, symbol in sorted(identities-financial_ids)])
    return dict(mode='supplied_financial_batches_with_independent_source_confirmations', batches=sources,
        original_per_fact_times_preserved=True, report_generation_is_source_refresh=False,
        all_100_financials_freshly_collected=False, full_live_acceptance=False)
