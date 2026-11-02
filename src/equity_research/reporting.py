"""Deterministic research reports from resumable collection evidence, never filled scores."""
import html
import re
from collections import Counter
from dataclasses import asdict
from datetime import date, datetime

from .cache import decode_fact
from .calculations import CALCULATIONS, calculate
from .fields import SPECS
from .models import Fact, FactRequest, SOURCE_ORDER, aware
from .policy import SCORE_WEIGHTS
from .providers import Status
from .assessment import assess_financials


def _stamp(value):
    stamp = datetime.fromisoformat(value)
    if not aware(stamp):
        raise ValueError('aware evidence timestamp required')
    return stamp


def _field(row, issuer_id, cutoff):
    if row['state'] not in ('collected', 'pending_data', 'collection_error', 'stale_data', 'not_started', 'out_of_scope'):
        raise ValueError('unknown collection state')
    q = row['query']
    spec = SPECS[q['field']]
    if q['issuer_id'] != issuer_id or q['accounting_definition'] != spec.accounting_definition or q['unit'] != 'currency':
        raise ValueError('query identity or definition mismatch')
    end = date.fromisoformat(q['period_end'])
    start = date.fromisoformat(q['period_start']) if q['period_start'] else None
    if spec.instant != (start is None) or (start is not None and start >= end):
        raise ValueError('invalid query period')
    if not re.fullmatch('[A-Z]{3}', q['currency']):
        raise ValueError('invalid query currency')
    attempts = row['attempts']
    if not isinstance(attempts, list) or len(attempts) > len(SOURCE_ORDER):
        raise ValueError('invalid provider attempts')
    if [a['source'] for a in attempts] != [s.value for s in SOURCE_ORDER[:len(attempts)]]:
        raise ValueError('source order or unattempted provider invented')
    for a in attempts:
        Status(a['status'])
        if _stamp(a['attempted_at']) > cutoff:
            raise ValueError('future provider attempt')
    raw = row.get('fact')
    accepted = None
    if raw is not None:
        if row['state'] != 'collected' or not attempts or attempts[-1]['status'] != 'valid' or any(a['status'] == 'valid' for a in attempts[:-1]):
            raise ValueError('invalid first-valid result')
        fact = decode_fact(raw)
        observed_cutoff = _stamp(row['as_of'])
        if observed_cutoff > cutoff or fact.source.value != attempts[-1]['source']:
            raise ValueError('source or cutoff mismatch')
        request = FactRequest(issuer_id, q['field'], start, end, q['currency'], q['unit'], q['accounting_definition'], observed_cutoff)
        if request.rejection(fact) or fact.raw_sha256 is None:
            raise ValueError('financial fact rejected or source hash absent')
        accepted = fact
    elif any(a['status'] == 'valid' for a in attempts) or row['state'] == 'collected':
        raise ValueError('valid outcome without a fact')
    return dict(query=q, state=row['state'], fact=asdict(accepted) if accepted else None,
                attempts=attempts, as_of=row.get('as_of'), reused=row.get('reused',False),
                error_type=row.get('error_type'), failure_status=row.get('failure_status'),
                failure_reason=row.get('failure_reason'), http_status=row.get('http_status')), accepted


def build_report(batch):
    if not isinstance(batch, dict) or batch.get('schema_version') != 1 or not isinstance(batch.get('companies'), list) or not batch['companies']:
        raise ValueError('nonempty version-1 batch required')
    cutoff = _stamp(batch['generated_at'])
    companies = []
    identities = set()
    for company in batch['companies']:
        identity = (company['symbol'], company['issuer_id'])
        if identity in identities or any(cik == identity[1] for _, cik in identities):
            raise ValueError('duplicate issuer would inflate company coverage')
        identities.add(identity)
        result = dict(symbol=company['symbol'], issuer_id=company['issuer_id'], fields=[], calculations=[],
                      total_score=None, rank=None, status='review_required', evidence_errors=[],
                      scope_approved=False, sector_model_supported=False, investment_approved=False)
        scores = {name: dict(weight=weight, score=None, status='sector_model_and_scope_review_required')
                  for name, weight in SCORE_WEIGHTS.items()}
        scores['valuation']['status'] = 'market_price_shares_and_valuation_model_required'
        scores['growth']['status'] = 'comparable_prior_period_and_model_required'
        scores['risk']['status'] = 'validated_risk_model_required'
        result['score_components'] = scores
        try:
            if not re.fullmatch(r'[0-9]{10}', company['issuer_id']) or int(company['issuer_id']) == 0 or not company['symbol'].strip():
                raise ValueError('canonical company identity required')
            scope = company['scope_status']
            if scope not in ('pending_scope', 'out_of_scope'):
                raise ValueError('unverified scope approval cannot enter a report')
            result['scope_status'] = scope
            result['scope_reason'] = company['scope_reason']
            result['deferred_fields'] = company.get('deferred_fields', [])
            if not company['fields'] and company.get('pending_reason') in (
                    'metadata_unavailable', 'symbol_mismatch', 'no_annual_in_recent_window', 'annual_period_unresolved'):
                result.update(status='period_unresolved', pending_reason=company['pending_reason'], accepted_fact_count=0)
                companies.append(result)
                continue
            facts = {}; contexts = set(); starts = set(); seen = set()
            if not company['fields']:
                raise ValueError('explicit requested fields required')
            for row in company['fields']:
                name = row['query']['field']
                if name in seen:
                    raise ValueError('duplicate field or mixed periods require a separate report')
                seen.add(name)
                output, fact = _field(row, company['issuer_id'], cutoff)
                result['fields'].append(output)
                q = output['query']
                contexts.add((q['period_end'], q['currency']))
                if q['period_start']:
                    starts.add(q['period_start'])
                if fact:
                    facts[name] = fact
            if len(contexts) != 1 or len(starts) > 1:
                raise ValueError('mixed financial contexts')
            end, currency = next(iter(contexts))
            result.update(period_start=next(iter(starts), None), period_end=end, currency=currency)
            if scope != 'out_of_scope':
                for name in CALCULATIONS:
                    if not starts and any(not SPECS[f].instant for f in CALCULATIONS[name].fields):continue
                    result['calculations'].append(calculate(name, facts, issuer_id=company['issuer_id'],
                        period_start=date.fromisoformat(result['period_start']) if starts else None, period_end=date.fromisoformat(end),
                        currency=currency, as_of=cutoff))
            result['accepted_fact_count'] = len(facts)
            result['status'] = 'out_of_scope' if scope == 'out_of_scope' else 'review_required'
        except (ValueError, KeyError, TypeError, ArithmeticError):
            # Never echo raw exceptions, credentials or unverified numeric results.
            result.update(status='invalid_evidence', fields=[], calculations=[], accepted_fact_count=0)
            result['evidence_errors'].append('identity_period_definition_chronology_or_provider_contract_failed')
        companies.append(result)
    for company in companies:
        # Use only the freshly validated fields above, never caller-supplied
        # risk flags, scores, profiles or model approvals from the batch.
        facts = {f['query']['field']: Fact(**f['fact']) for f in company['fields'] if f['fact']}
        # Invalid company identities must remain isolated report errors, rather
        # than aborting all other companies during assessment validation.
        if company['status'] == 'invalid_evidence':
            company['financial_assessment'] = dict(policy_version='financial-review-v1',
                quantitative_gate='invalid_evidence', checks=[], overall_risk_cleared=False,
                investment_approved=False)
        else:
            company['financial_assessment'] = assess_financials(facts,
                issuer_id=company['issuer_id'],
                period_start=date.fromisoformat(company['period_start']) if company.get('period_start') else None,
                period_end=date.fromisoformat(company['period_end']) if company.get('period_end') else None,
                currency=company.get('currency', 'USD'), as_of=cutoff)
        gate = company['financial_assessment']['quantitative_gate']
        company['score_blockers'] = ['verified_common_share_scope_required', 'accepted_sector_model_required',
            'source_bound_valuation_required', 'complete_validated_score_components_required',
            'qualitative_risk_review_required']
        if gate != 'no_screen_trigger': company['score_blockers'].insert(0, gate)
        company['score_components']['risk']['status'] = gate if gate != 'no_screen_trigger' else 'qualitative_and_sector_review_required'
    states = Counter(c['status'] for c in companies)
    return dict(schema_version=1, report_kind='research_readiness_with_exact_arithmetic', as_of=cutoff.isoformat(),
                companies=companies, ranking=[], score_weights=dict(SCORE_WEIGHTS),
                summary=dict(companies=len(companies), company_states=dict(states),
                    accepted_facts=sum(c['accepted_fact_count'] for c in companies),
                    arithmetic_results=sum(r['value'] is not None for c in companies for r in c['calculations']),
                    scored_companies=0),
                financial_review_summary=dict(Counter(c['financial_assessment']['quantitative_gate'] for c in companies)),
                mvp_accepted=False, hundred_company_accepted=False,
                acceptance_gaps=['100_company_live_financial_run', 'verified_common_share_scope',
                                 'validated_sector_scoring', 'market_price_and_prior_period_inputs'],
                new_network_requests=0)


def render_markdown(report):
    def cell(value):
        return html.escape(str(value)).replace('|', '&#124;').replace('\n', ' ')
    lines = ['# US Equity Research', '', f"Evidence cutoff: {cell(report['as_of'])}", '',
             'MVP acceptance: pending. Unavailable scores are not zero and companies remain unranked.', '',
             '| Symbol | CIK | Period end | Accepted facts | Arithmetic results | Status | Score / 100 |',
             '| --- | --- | --- | ---: | ---: | --- | --- |']
    for c in report['companies']:
        count = sum(r['value'] is not None for r in c['calculations'])
        lines.append('| '+' | '.join(cell(v) for v in (c['symbol'], c['issuer_id'], c.get('period_end','unknown'), c['accepted_fact_count'], count, c['status'], 'unavailable'))+' |')
    for c in report['companies']:
        lines.extend(['', '## '+cell(c['symbol']), '', 'Scope: '+cell(c.get('scope_reason','invalid evidence')), ''])
        if c.get('sector_profile'):
            lines.extend(['Sector review: '+cell(c['sector_profile']['profile'])+' ('+cell(c['sector_profile']['status'])+').', ''])
        if c.get('pending_reason'):
            lines.extend(['', 'Unattempted financial collection: '+cell(c['pending_reason'])+'.', ''])
        if c.get('deferred_fields'):
            lines.extend(['', 'Unattempted duration fields (period unresolved): '+cell(', '.join(c['deferred_fields']))+'.', ''])
        if c.get('financial_assessment'):
            assessment = c['financial_assessment']
            lines.extend(['Financial review gate: '+cell(assessment['quantitative_gate'])+'.', '',
                          '| Financial check | Result | Interpretation |', '| --- | --- | --- |'])
            for check in assessment['checks']:
                reason = check['explanation']
                if check['missing_fields']: reason += ' Missing: '+', '.join(check['missing_fields'])+'.'
                if check['rejections']: reason += ' Rejected: '+', '.join(r['field']+': '+r['reason'] for r in check['rejections'])+'.'
                lines.append('| '+' | '.join(cell(v) for v in (check['check'], check['status'], reason))+' |')
            lines.extend(['', 'Scoring withheld: '+cell('; '.join(c['score_blockers']))+'.', ''])
        lines.extend(['| Field | Value and currency | Source | Period | Definition | Raw SHA-256 | Observed at | Attempts |',
                      '| --- | --- | --- | --- | --- | --- | --- | --- |'])
        for f in c['fields']:
            fact = f['fact']; q = f['query']
            attempts = '; '.join(a['source']+': '+a['status'] for a in f['attempts']) or 'not attempted'
            source = fact['source_url'] if fact else 'unavailable'
            lines.append('| '+' | '.join(cell(v) for v in (q['field'], str(fact['value'])+' '+fact['currency'] if fact else 'unavailable', source,
                (q['period_start'] or 'instant')+' / '+q['period_end'], q['accounting_definition'], fact['raw_sha256'] if fact else '',
                fact['retrieved_at'] if fact else '', attempts))+' |')
        lines.extend(['', '| Calculation | Value | Unit | Status |', '| --- | --- | --- | --- |'])
        for r in c['calculations']:
            lines.append('| '+' | '.join(cell(v) for v in (r['formula'], r['value'] if r['value'] is not None else 'unavailable', r['unit'], r['status']))+' |')
        lines.extend(['', 'Score components: '+ '; '.join(cell(k)+': '+cell(v['status']) for k,v in c['score_components'].items())+'.', ''])
    return '\n'.join(lines).rstrip()+'\n'
