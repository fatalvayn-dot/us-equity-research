"""Current public membership/registered-class evidence, separate from score approval."""
from collections import Counter
from datetime import datetime

from .common_sample import verify_common_sample
from .nasdaq import NasdaqDirectories, DIRECTORY_ENDPOINTS
from .providers import ProviderFailure
from .sec import DIRECTORY_URL
from .submissions import submissions_url


def collect_common_evidence(candidates, metadata, archive, transport_factory, *, clock, pulse):
    attempts = []
    if not any(r.get('annual') and r.get('status') == 'metadata_available_legal_type_pending' for r in metadata):
        companies = [dict(**c, status='review_required', blockers=['annual_metadata_unavailable'],
                          evidence_status='not_attempted', scope_approved=False,
                          investment_approved=False, total_score=None) for c in candidates]
        return dict(schema_version=1, as_of=clock(), companies=companies,
                    summary=dict(evaluated=len(companies), selected=0,
                                 states=dict(Counter(c['status'] for c in companies))),
                    target_sample_verified=False, hundred_common_share_sample_verified=False,
                    active_universe_accepted=False, mvp_accepted=False,
                    collection_attempts=[dict(source='membership', status='not_attempted',
                                              reason='annual_metadata_unavailable')])
    try:
        transport_factory(['www.sec.gov']).get(DIRECTORY_URL)
    except ProviderFailure as exc:
        attempts.append(dict(source='SEC', status=exc.status.value))
    directories = NasdaqDirectories(transport_factory(['www.nasdaqtrader.com', 'ftp.nasdaqtrader.com'], accept='text/plain'))
    try:
        directories.fetch()
    except ProviderFailure:
        pass  # Preserve typed attempts; valid archived evidence may still qualify.
    attempts.extend(directories.attempts)
    pulse()
    urls = {DIRECTORY_URL, *(u for group in DIRECTORY_ENDPOINTS.values() for u in group)}
    urls.update(submissions_url(c['issuer_id']) for c in candidates)
    urls.update(r['annual']['source_url'] for r in metadata if r.get('annual'))
    cutoff = clock()
    latest = {}
    for observation in archive.observations():
        stamp = datetime.fromisoformat(observation['retrieved_at'])
        url = observation['url']
        if url not in urls or stamp > cutoff:
            continue
        previous = latest.get(url)
        if previous is None or stamp > datetime.fromisoformat(previous['retrieved_at']):
            latest[url] = observation
        elif stamp == datetime.fromisoformat(previous['retrieved_at']) and observation['sha256'] != previous['sha256']:
            raise ValueError('conflicting common-share source observation')

    def responses():
        for o in latest.values():
            pulse()
            response = archive.get(o['url'], o['sha256'], datetime.fromisoformat(o['retrieved_at']))
            if response is None:
                raise ValueError('common-share source observation absent')
            yield response

    try:
        result = verify_common_sample(dict(companies=candidates), responses(), as_of=cutoff, target=len(candidates))
    except (ProviderFailure, KeyError, ValueError, TypeError) as exc:
        status = exc.status.value if isinstance(exc, ProviderFailure) else 'invalid_or_missing_evidence'
        companies = [dict(**c, status='review_required', blockers=['listing_identity_or_instrument_unverified'],
                          evidence_status=status, scope_approved=False, investment_approved=False, total_score=None)
                     for c in candidates]
        result = dict(schema_version=1, as_of=cutoff, companies=companies,
                      summary=dict(evaluated=len(companies), selected=0, states=dict(Counter(c['status'] for c in companies))),
                      target_sample_verified=False, hundred_common_share_sample_verified=False,
                      active_universe_accepted=False, mvp_accepted=False)
    result['collection_attempts'] = attempts
    return result
