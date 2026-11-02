"""Financial observation validation; missing is never zero."""
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Optional


@dataclass(frozen=True)
class Observation:
    ticker: str
    field: str
    value: str
    source: str
    period_end: str
    currency: str
    retrieved_at: str


def validate_observation(obs: Observation, expected_ticker: str) -> Optional[Decimal]:
    if obs.ticker.upper().strip() != expected_ticker.upper().strip():
        return None
    if not obs.field or not obs.source or not obs.currency:
        return None
    try:
        date.fromisoformat(obs.period_end)
        date.fromisoformat(obs.retrieved_at[:10])
        value = Decimal(obs.value)
    except (ValueError, InvalidOperation, TypeError):
        return None
    if not value.is_finite():
        return None
    return value


def first_valid_field(observations, ticker: str, field: str):
    """First valid observation wins; no cross-ticker or cross-field fallback."""
    for observation in observations:
        if observation.field != field:
            continue
        value = validate_observation(observation, ticker)
        if value is not None:
            return observation, value
    return None
