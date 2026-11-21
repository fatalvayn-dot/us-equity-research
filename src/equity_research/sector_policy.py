"""Conservative SEC metadata routing, never legal classification or model approval."""
import re
from datetime import timedelta

from .calculations import calculate
from .models import aware
from .providers import ProviderFailure
from .submissions import parse_submissions, submissions_url
from .transport import Response

POLICY_VERSION = 'sec-sic-routing-v1'
SIC_REFERENCE = 'https://www.sec.gov/search-filings/standard-industrial-classification-sic-code-list'
BANK_CODES = frozenset({'6021', '6022', '6029', '6035', '6036'})
INSURANCE_CODES = frozenset({'6311', '6321', '6324', '6331', '6351', '6361', '6399'})

# Permanent user exclusion: deposit-taking banks, insurance carriers,
# insurance agents/brokers, mortgage banking and investment banking/brokers. SIC alone is a conservative
# filter, not a certification of participation-index eligibility.
def excluded_banking_or_insurance(sic):
    return isinstance(sic, str) and len(sic) == 4 and sic.isascii() and sic.isdigit() and (
        sic.startswith(('60', '63', '64')) or sic in {'6111', '6162', '6163', '6199', '6211'}
    )



def assess_profile(response, *, issuer_id, as_of, max_age=timedelta(hours=6)):
    """Bind current metadata to issuer and cutoff; stale snapshots cannot grant eligibility.

    SIC gives a conservative review route only. No code establishes absence of
    fund/BDC/REIT status or qualifies an issuer for a generic cash-flow model.
    """
    submissions_url(issuer_id)  # Require the same canonical identity as the adapter.
    if not aware(as_of) or not isinstance(max_age, timedelta) or max_age <= timedelta(0):
        raise ValueError('aware cutoff and positive metadata age required')
    result = dict(policy_version=POLICY_VERSION, issuer_id=issuer_id,
                  as_of=as_of.isoformat(), profile='unknown', status='metadata_unavailable',
                  evidence=None, sic_reference=SIC_REFERENCE, legal_type_approved=False,
                  sector_model_supported=False, generic_cash_flow_eligible=False,
                  scope_approved=False, investment_approved=False)
    if response is None:
        return result
    if not isinstance(response, Response):
        result['status'] = 'invalid_metadata'
        return result
    if response.url != submissions_url(issuer_id) or not aware(response.retrieved_at):
        result['status'] = 'invalid_metadata'
        return result
    result['evidence'] = dict(source_url=response.url, raw_sha256=response.sha256,
                              retrieved_at=response.retrieved_at.isoformat())
    if response.retrieved_at > as_of:
        result['status'] = 'future_metadata'
        return result
    if as_of - response.retrieved_at > max_age:
        result['status'] = 'stale_metadata'
        return result
    try:
        snapshot = parse_submissions(response, issuer_id)
    except ProviderFailure as exc:
        result.update(status='invalid_metadata', failure_status=exc.status.value)
        return result
    result['evidence'].update(sic_label=snapshot.sic_label,
                              sic_description=snapshot.sic_description,
                              entity_type_label=snapshot.entity_type_label)
    sic = snapshot.sic_label
    if not isinstance(sic, str) or not re.fullmatch(r'[0-9]{4}', sic) or not 100 <= int(sic) <= 8999:
        result['status'] = 'unknown_sic'
        return result
    if sic in BANK_CODES:
        profile = 'banking_signal'
    elif sic in INSURANCE_CODES:
        profile = 'insurance_signal'
    elif sic == '6798':
        profile = 'reit_signal'
    elif sic.startswith('67'):
        profile = 'investment_vehicle_review'  # Not proof of BDC/fund status.
    elif sic.startswith('6'):
        profile = 'finance_real_estate_review'
    else:
        profile = 'other_industry_review'  # Never proof that a generic model fits.
    result.update(profile=profile, status='metadata_signal_only')
    return result


def calculate_with_sector_guard(name, facts, *, metadata_response, issuer_id,
                                period_start, period_end, currency, as_of):
    """Expose exact arithmetic separately from withheld economic interpretation.

    Callers cannot provide a hand-approved profile. All routes remain unapproved
    until a sector model and security-scope evidence are separately validated.
    """
    profile = assess_profile(metadata_response, issuer_id=issuer_id, as_of=as_of)
    arithmetic = calculate(name, facts, issuer_id=issuer_id, period_start=period_start,
                           period_end=period_end, currency=currency, as_of=as_of)
    reason = ('sector_model_validation_pending' if profile['profile'] == 'other_industry_review'
              else 'specialized_model_required' if profile['profile'] != 'unknown'
              else 'profile_evidence_required')
    return dict(policy_version=POLICY_VERSION, profile=profile, arithmetic=arithmetic,
                interpretation_status=reason, interpreted_value=None,
                sector_model_supported=False, scope_approved=False,
                generic_cash_flow_eligible=False, investment_approved=False)
