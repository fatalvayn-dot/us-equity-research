"""Explicit annual comparison plans and sourced growth; no fiscal-date guesses."""
from .turkish import label, calculation_label
from dataclasses import asdict
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal, localcontext

from .annual_period import annual_period
from .companyfacts import SecCompanyFacts, companyfacts_url
from .documents import document_key
from .fields import SPECS
from .models import Fact, FactRequest, Source, aware
from .providers import ProviderFailure, Status

DURATION_FIELDS = tuple(name for name, spec in SPECS.items() if not spec.instant)


def comparable_periods(current_start, current_end, prior_start, prior_end):
    """Consecutive literal full-year durations, including 52/53-week calendars.

    This conservative policy excludes transition/stub years. It does not prove
    stable business perimeter, accounting policy or investment suitability.
    """
    if any(type(d) is not date for d in (current_start, current_end, prior_start, prior_end)):
        return False
    current_days = (current_end - current_start).days + 1
    prior_days = (prior_end - prior_start).days + 1
    return (350 <= current_days <= 380 and 350 <= prior_days <= 380
            and abs(current_days - prior_days) <= 7
            and current_start - prior_end == timedelta(days=1))


def comparison_plan(document, financial, *, issuer_id, symbol, annual, as_of, currency='USD'):
    """Discover periods only; numeric field winners still use the ordered resolver.

    Reparse the original annual to anchor the current duration. Discover the
    prior start/end from literal rows in that same accession, never from fy/fp,
    calendar frames, or subtracting a year. No source is counted as attempted.
    """
    document_key(issuer_id, annual)
    if (not isinstance(symbol, str) or not symbol.strip() or not aware(as_of)
            or not aware(document.retrieved_at) or not aware(financial.retrieved_at)
            or max(document.retrieved_at, financial.retrieved_at) > as_of
            or document.url != annual['source_url'] or currency != 'USD'):
        raise ProviderFailure(Status.INVALID_DATA)
    _, payload = SecCompanyFacts._parse(financial, issuer_id)
    period = annual_period(document.body, cik=issuer_id,
                           report_end=date.fromisoformat(annual['report_end']), document_type=annual['form'])
    start, end = (date.fromisoformat(period[k]) for k in ('period_start', 'period_end'))
    result = dict(issuer_id=issuer_id, symbol=symbol, status='prior_period_unresolved',
                  current_period=period, prior_period=None, fields=[], field_states={},
                  discovery_source=dict(url=financial.url, sha256=financial.sha256,
                                        retrieved_at=financial.retrieved_at.isoformat()),
                  annual_source=dict(url=document.url, sha256=document.sha256,
                                     retrieved_at=document.retrieved_at.isoformat()),
                  annual_accession=annual['accession'], as_of=as_of.isoformat(),
                  provider_attempts=[], financial_values_selected=False, scope_approved=False,
                  sector_model_supported=False, investment_approved=False)
    taxonomy = payload['facts'].get('us-gaap', {})
    if not isinstance(taxonomy, dict):
        raise ProviderFailure(Status.INVALID_DATA)
    candidates = {}
    for field in DURATION_FIELDS:
        spec = SPECS[field]
        concept = taxonomy.get(spec.tag)
        if concept is None:
            result['field_states'][field] = 'concept_absent'; continue
        try:
            rows = concept['units'].get(currency, [])
            if not isinstance(rows, list): raise ValueError('rows required')
            current = []; prior = {}
            for row in rows:
                if not isinstance(row, dict): raise ValueError('row required')
                if row.get('accn') != annual['accession'] or row.get('form') not in ('10-K', '10-K/A'):
                    continue
                if 'start' not in row: continue
                s, e = date.fromisoformat(row['start']), date.fromisoformat(row['end'])
                filed = date.fromisoformat(row['filed'])
                available = datetime.combine(filed + timedelta(days=1), time(5), timezone.utc)
                value = row['val']
                if (type(value) not in (int, Decimal) or not Decimal(value).is_finite()
                        or filed != date.fromisoformat(annual['filed_on']) or filed < e
                        or available > min(as_of, financial.retrieved_at)):
                    raise ValueError('invalid annual row')
                if (s, e) == (start, end): current.append(Decimal(value))
                elif comparable_periods(start, end, s, e):
                    prior.setdefault((s, e), set()).add(Decimal(value))
            if not current: state = 'current_value_absent_in_annual'
            elif len(set(current)) != 1: state = 'conflicting_current_values'
            elif len(prior) != 1: state = 'prior_period_absent_or_ambiguous'
            elif len(next(iter(prior.values()))) != 1: state = 'conflicting_prior_values'
            else:
                candidates[field] = next(iter(prior)); state = 'explicit_comparable_period'
            result['field_states'][field] = state
        except (ValueError, TypeError, KeyError, ArithmeticError):
            result['field_states'][field] = 'invalid_concept_evidence'
    if len(set(candidates.values())) > 1:
        result['status'] = 'conflicting_prior_periods'; return result
    if candidates:
        ps, pe = next(iter(candidates.values()))
        result.update(status='ready_for_ordered_collection', fields=list(candidates),
                      prior_period=dict(period_start=ps.isoformat(), period_end=pe.isoformat()),
                      current_plan=_plan(symbol, issuer_id, start, end, currency, candidates),
                      prior_plan=_plan(symbol, issuer_id, ps, pe, currency, candidates))
    return result


def _plan(symbol, cik, start, end, currency, fields):
    return dict(schema_version=1, companies=[dict(symbol=symbol, issuer_id=cik,
                period_start=start.isoformat(), period_end=end.isoformat(), currency=currency,
                fields=list(fields), scope_status='pending_scope',
                scope_reason='active_common_share_and_sector_model_review_required')])


def calculate_growth(current, prior, *, as_of):
    """Exact (current / prior) - 1, subject to conservative comparability rules."""
    if not aware(as_of): raise ValueError('aware cutoff required')
    result = dict(status='pending_data', value=None, unit='ratio',
                  formula='current / prior - 1', inputs=[], as_of=as_of.isoformat(),
                  scope_approved=False, sector_model_supported=False, investment_approved=False,
                  economic_comparability='business_perimeter_and_policy_review_required')
    if current is None or prior is None: return result
    if not isinstance(current, Fact) or not isinstance(prior, Fact):
        result['status'] = 'invalid_inputs'; return result
    spec = SPECS.get(current.field)
    if spec is None or spec.instant:
        result['status'] = 'unsupported_field'; return result
    for fact in (current, prior):
        try:
            request = FactRequest(current.issuer_id, current.field, fact.period_start, fact.period_end,
                                  current.currency, 'currency', spec.accounting_definition, as_of)
            rejected = request.rejection(fact)
        except ValueError:
            rejected = 'invalid_chronology'
        if rejected or fact.raw_sha256 is None:
            result['status'] = 'invalid_inputs'; return result
    if not comparable_periods(current.period_start, current.period_end, prior.period_start, prior.period_end):
        result['status'] = 'incomparable_periods'; return result
    if (current.source is Source.SEC and prior.source is Source.SEC
            and (not current.filing_accession or current.filing_accession != prior.filing_accession
                 or current.raw_sha256 != prior.raw_sha256 or current.retrieved_at != prior.retrieved_at
                 or current.filed_on is None or current.filed_on != prior.filed_on
                 or current.source_url != companyfacts_url(current.issuer_id) or prior.source_url != current.source_url)):
        result['status'] = 'inconsistent_sec_filing_vintage'; return result
    result.update(field=current.field, issuer_id=current.issuer_id, input_currency=current.currency,
                  semantic_model_review=spec.requires_semantic_model_review,
                  inputs=[asdict(current), asdict(prior)])
    if prior.value <= 0:
        result['status'] = 'nonpositive_base'; return result
    magnitude = max(max(len(v.as_tuple().digits), abs(v.adjusted())) for v in (current.value, prior.value))
    if magnitude > 1000:
        result['status'] = 'unsupported_magnitude'; return result
    with localcontext() as ctx:
        ctx.prec = max(50, magnitude * 2 + 20)
        value = current.value / prior.value - 1
    result.update(status='calculated_arithmetic_only', value=value)
    return result


def build_comparative_report(current_batch, prior_batch):
    """Revalidate both ordered collection trails before joining exact issuers."""
    from .reporting import build_report
    current_report, prior_report = build_report(current_batch), build_report(prior_batch)
    prior_companies = {c['issuer_id']: c for c in prior_report['companies']}
    if set(prior_companies) != {c['issuer_id'] for c in current_report['companies']}:
        raise ValueError('same explicit issuer set required')
    cutoff = max(datetime.fromisoformat(r['as_of']) for r in (current_report, prior_report))
    companies = []
    for current in current_report['companies']:
        prior = prior_companies[current['issuer_id']]
        row = dict(symbol=current['symbol'], issuer_id=current['issuer_id'], calculations=[],
                   status='review_required', total_score=None, rank=None)
        if (current['symbol'] != prior['symbol'] or any(c['status'] in ('invalid_evidence', 'out_of_scope', 'period_unresolved') for c in (current, prior))):
            row['status'] = 'invalid_or_ineligible_evidence'
        else:
            cf = {f['query']['field']: f['fact'] for f in current['fields']}
            pf = {f['query']['field']: f['fact'] for f in prior['fields']}
            for field in sorted(set(cf) | set(pf)):
                if field not in DURATION_FIELDS: continue
                def fact(raw):
                    if raw is None: return None
                    # build_report emits dataclass-native values, not JSON strings.
                    return Fact(**raw)
                calculation = calculate_growth(fact(cf.get(field)), fact(pf.get(field)), as_of=cutoff)
                calculation['field'] = field
                row['calculations'].append(calculation)
        companies.append(row)
    return dict(schema_version=1, report_kind='ordered_source_comparative_arithmetic',
                as_of=cutoff.isoformat(), companies=companies,
                summary=dict(companies=len(companies), arithmetic_results=sum(r['value'] is not None for c in companies for r in c['calculations']), scored_companies=0),
                current_evidence=current_report, prior_evidence=prior_report, ranking=[], mvp_accepted=False)


def render_comparative_markdown(report):
    import html
    def cell(value):
        return html.escape(label(value)).replace('|', '&#124;').replace('\n', ' ')
    lines = ['# Yıllık karşılaştırma girdileri', '', 'Kaynaklara dayalı aritmetik hesaplamalardır. Sektör ve iş modeli karşılaştırılabilirliği incelemesi ile ilk sürümün kabulü bekleniyor.', '',
             f"Kaynak verilerinin kesim zamanı: {cell(report['as_of'])}", '',
             '| Sembol | Alan | Büyüme oranı | Durum |', '| --- | --- | ---: | --- |']
    for row in report['companies']:
        for calculation in row['calculations']:
            lines.append('| '+' | '.join(cell(v) for v in (row['symbol'], calculation['field'],
                calculation['value'] if calculation['value'] is not None else 'unavailable', calculation['status']))+' |')
    lines.extend(['', 'Formül: cari dönem / önceki dönem − 1. Tüm girdi değerleri, dönemler, muhasebe tanımları, para birimleri, kaynak bağlantıları, ham kaynak özetleri ve yapılan kaynak denemeleri JSON raporunda korunmuştur. Yatırım puanı veya sıralama üretilmemiştir.', ''])
    return '\n'.join(lines).rstrip()+'\n'
