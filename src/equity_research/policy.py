"""Scoring specification only. No unvalidated financial score is produced."""
from types import MappingProxyType

SCORE_WEIGHTS = MappingProxyType({
    "financial_strength": 20,
    "valuation": 20,
    "growth": 20,
    "profitability": 15,
    "cash_flow": 15,
    "risk": 10,
})


def analysis_status(*, in_scope: bool, complete: bool, sector_model_supported: bool) -> str:
    if not in_scope:
        return "out_of_scope"
    if not complete:
        return "pending_data"
    if not sector_model_supported:
        return "unsupported_sector_model"
    return "ready_for_model_validation"
