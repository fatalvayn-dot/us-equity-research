"""Deprecated starter compatibility; new code must use models/providers.

This API lacks accounting definitions and must never feed live scoring.
"""
from dataclasses import dataclass
from datetime import date
from math import isfinite
from typing import Optional

@dataclass(frozen=True)
class Observation:
    field: str
    value: float
    source: str
    as_of: date
    period_end: date
    currency: str
    issuer_id: str

    def valid(self, issuer_id: str, currency: str, min_period: date) -> bool:
        return (self.issuer_id == issuer_id and self.currency == currency
                and self.period_end >= min_period and self.as_of >= self.period_end
                and bool(self.source.strip()) and isfinite(self.value))


def first_valid(field: str, issuer_id: str, currency: str, min_period: date, providers):
    """Query providers in order; never query later providers after a valid observation."""
    attempts = []
    for name, provider in providers:
        try:
            obs = provider(field, issuer_id)
        except Exception as exc:
            attempts.append({'provider': name, 'status': 'error', 'detail': type(exc).__name__})
            continue
        if obs is None:
            attempts.append({'provider': name, 'status': 'missing'})
        elif obs.field == field and obs.source == name and obs.valid(issuer_id, currency, min_period):
            attempts.append({'provider': name, 'status': 'valid'})
            return obs, attempts
        else:
            attempts.append({'provider': name, 'status': 'invalid'})
    return None, attempts


def classify(stock_type: str, forbidden_primary_business: Optional[bool], severe_distress: Optional[bool], mandatory_fields_complete: bool):
    """Only proven exclusions; uncertainty cannot become approval."""
    if stock_type != 'common_stock':
        return 'out_of_scope'
    if forbidden_primary_business is True or severe_distress is True:
        return 'excluded_verified'
    if forbidden_primary_business is None or severe_distress is None or not mandatory_fields_complete:
        return 'pending_evidence'
    return 'eligible_for_scoring'
