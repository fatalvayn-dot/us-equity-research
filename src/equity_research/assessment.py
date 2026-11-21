"""Versioned, non-compensating financial review signals from exact statement facts.

These are screening hypotheses, not bankruptcy findings or an approved sector
model. No signal-free result constitutes an investment recommendation.
"""
from dataclasses import asdict
from datetime import date, timedelta
import re

from .fields import SPECS
from .models import Fact, FactRequest, aware

POLICY_VERSION = 'financial-review-v1'
REFERENCE = 'https://www.sec.gov/about/reports-publications/beginners-guide-financial-statements'
CHECKS = (
    ('balance_deficit', ('assets', 'liabilities'), 'critical_review',
     'Reported liabilities exceed reported assets; inspect equity, buybacks and obligations. This alone does not establish insolvency.'),
    ('loss_and_operating_cash_outflow', ('net_income', 'operating_cash_flow'), 'critical_review',
     'NetIncomeLoss and operating cash flow are both negative for the same annual period; review funding and cash runway.'),
    ('operating_loss', ('operating_income',), 'watch',
     'Reported operating income is negative; inspect persistence and exceptional items.'),
    ('current_balance_shortfall', ('current_assets', 'current_liabilities'), 'watch',
     'Current assets are below current liabilities; inspect cash conversion and maturities. This is not an insolvency test.'),
)


def assess_financials(facts, *, issuer_id, period_start, period_end, currency, as_of):
    """Revalidate operands; missing, stale or invalid evidence never clears a check.

    Annual results are limited to 350--380 days and 550-day period-end age.
    Neither a recent retrieval nor a complete numeric screen proves the latest
    filing, sector suitability, going-concern opinion or debt-service capacity.
    """
    if not aware(as_of) or (period_end is not None and type(period_end) is not date):
        raise ValueError('aware cutoff and exact date required')
    if (not isinstance(issuer_id, str) or not re.fullmatch(r'[0-9]{10}', issuer_id) or int(issuer_id) == 0
            or not isinstance(currency, str) or not re.fullmatch(r'[A-Z]{3}', currency)):
        raise ValueError('canonical issuer and currency required')
    if period_start is not None and (type(period_start) is not date or period_end is None or period_start >= period_end):
        raise ValueError('ordered exact dates required')
    result = dict(policy_version=POLICY_VERSION, issuer_id=issuer_id,
                  as_of=as_of.isoformat(), checks=[], quantitative_gate='unresolved',
                  critical_flags=[], watch_flags=[], unresolved_checks=[],
                  risk_assessment_status='qualitative_and_sector_review_required',
                  overall_risk_cleared=False, investment_approved=False,
                  reference=REFERENCE,
                  limitations=['annual_statement_screen_not_latest_filing_confirmation',
                      'no_debt_maturity_covenant_or_going_concern_review',
                      'no_sector_or_security_scope_approval'])
    for name, fields, severity, explanation in CHECKS:
        row = dict(check=name, severity=severity, explanation=explanation,
                   status='unresolved', triggered=None, inputs=[], missing_fields=[], rejections=[])
        for field in fields:
            fact = facts.get(field)
            if fact is None:
                row['missing_fields'].append(field)
                continue
            spec = SPECS[field]
            reason = None
            if period_end is None:
                reason = 'period_unresolved'
            elif period_end > as_of.date():
                reason = 'future_financial_period'
            elif not spec.instant and (period_start is None or not 350 <= (period_end-period_start).days+1 <= 380):
                reason = 'explicit_full_annual_period_required'
            elif as_of.date() - period_end > timedelta(days=550):
                reason = 'stale_financial_period'
            elif not isinstance(fact, Fact):
                reason = 'invalid_fact_type'
            else:
                request = FactRequest(issuer_id, field, None if spec.instant else period_start,
                                      period_end, currency, 'currency', spec.accounting_definition, as_of)
                reason = request.rejection(fact)
                if not reason and fact.raw_sha256 is None:
                    reason = 'missing_raw_source_hash'
                if not reason and spec.instant and fact.value < 0:
                    reason = 'unsupported_balance_sign'
            if reason:
                row['rejections'].append(dict(field=field, reason=reason))
            else:
                row['inputs'].append(asdict(fact))
        if not row['missing_fields'] and not row['rejections']:
            values = [facts[field].value for field in fields]
            trigger = (values[1] > values[0] if name == 'balance_deficit' else
                       all(v < 0 for v in values) if name == 'loss_and_operating_cash_outflow' else
                       values[0] < 0 if name == 'operating_loss' else values[0] < values[1])
            row.update(status='triggered' if trigger else 'not_triggered', triggered=trigger)
        result['checks'].append(row)
        if row['status'] == 'unresolved': result['unresolved_checks'].append(name)
        elif row['triggered']:
            result['critical_flags' if severity == 'critical_review' else 'watch_flags'].append(name)
    # A critical flag wins even when other checks are missing or favorable.
    result['quantitative_gate'] = ('critical_review_required' if result['critical_flags'] else
                                   'unresolved' if result['unresolved_checks'] else 'no_screen_trigger')
    return result
