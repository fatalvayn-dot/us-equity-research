"""Sample reconciliation against primary listing evidence; no legal-type guesses."""
from collections import Counter,defaultdict
from dataclasses import asdict
from datetime import timedelta

from .nasdaq import UniverseStatus,build_universe
from .models import aware


def audit_sample(companies,snapshots,identity,*,as_of,max_age=timedelta(days=4)):
    """Return one explicit disposition per requested symbol/CIK, never approve."""
    if not aware(as_of):raise ValueError('aware observation time required')
    companies=tuple(companies)
    if not companies or any(not isinstance(c,dict) or not isinstance(c.get('symbol'),str) or
                            not isinstance(c.get('issuer_id'),str) for c in companies):
        raise ValueError('explicit sample identities required')
    if len({c['symbol'] for c in companies})!=len(companies) or len({c['issuer_id'] for c in companies})!=len(companies):
        raise ValueError('duplicate sample symbol/issuer')
    for c in companies:
        if len(c['issuer_id'])!=10 or not c['issuer_id'].isascii() or not c['issuer_id'].isdigit() or int(c['issuer_id'])==0:
            raise ValueError('canonical sample issuer required')
    classified=build_universe(tuple(snapshots),identity,as_of=as_of,max_age=max_age)
    index=defaultdict(list)
    for row in classified:
        for alias in set(row.listing.aliases):index[alias].append(row)
    source_index={s.source_url:s for s in snapshots}
    output=[]
    excluded={UniverseStatus.EXCLUDED_INSTRUMENT,UniverseStatus.OUT_OF_SCOPE_EXCHANGE,UniverseStatus.TEST_ISSUE}
    for company in companies:
        matches=index[company['symbol']]
        state='pending_scope';reason='no_exact_listing_alias';evidence=[]
        if len(matches)>1:reason='ambiguous_listing_alias'
        elif len(matches)==1:
            row=matches[0];snapshot=source_index[row.source_url]
            evidence=[dict(source_url=row.source_url,raw_sha256=row.raw_sha256,
                retrieved_at=snapshot.retrieved_at.isoformat(),created_on=snapshot.created_on.isoformat(),
                creation_label=snapshot.creation_label,listing=asdict(row.listing),
                listing_classification=row.status.value,classification_reason=row.reason,
                matched_issuer_id=row.issuer_id)]
            fresh=(snapshot.retrieved_at<=as_of and as_of-snapshot.retrieved_at<=max_age
                   and timedelta(0)<=as_of.date()-snapshot.created_on<=max_age)
            if not fresh:reason='stale_or_future_source'
            elif row.status in excluded:
                state='out_of_scope';reason=row.reason
            elif row.status is UniverseStatus.CANDIDATE:
                if row.issuer_id!=company['issuer_id']:reason='sample_cik_disagrees_with_listing_identity'
                else:
                    state='listing_evidence_complete_legal_type_pending'
                    reason='primary_listing_flags_and_exact_identity_match; fund_legal_type_not_independently_verified'
            else:reason=row.reason
        output.append(dict(symbol=company['symbol'],issuer_id=company['issuer_id'],scope_status=state,
            scope_reason=reason,evidence=evidence,scope_approved=False))
    return dict(schema_version=1,observed_at=as_of.isoformat(),companies=output,
        identity_evidence=dict(url=identity.source_url,sha256=identity.sha256,retrieved_at=identity.retrieved_at.isoformat()),
        summary=dict(companies=len(output),states=dict(Counter(r['scope_status'] for r in output)),approved=0),
        active_universe_accepted=False,hundred_company_accepted=False,investment_approved=False)
