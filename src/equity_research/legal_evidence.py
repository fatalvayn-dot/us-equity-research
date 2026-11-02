"""Literal annual-document legal-status disclosures, never a legal/scope approval."""
import re
from datetime import date

from .annual_period import annual_period
from .filing_metadata import CoverParser
from .models import aware
from .providers import ProviderFailure, Status
from .transport import Response

CONCEPTS = {
    'investment_company_type': 'dei:entityinvcompanytype',
    'business_development_company': 'cef:businessdevelopmentcompanyflag',
    'registered_closed_end_fund': 'cef:registeredclosedendfundflag',
}
INVESTMENT_TYPES = frozenset({'N-1A', 'N-1', 'N-2', 'N-3', 'N-4', 'N-5', 'N-6', 'S-1 or S-3', 'S-6'})


def annual_legal_evidence(response, *, cik, report_end, document_type, as_of):
    """Only facts sharing an explicitly verified annual document context may win.

    No tag means unknown. A reported false flag is a disclosure for that report,
    not proof of common-share eligibility or permanent absence of BDC/fund status.
    Unsupported transforms, namespaces and conflicting duplicates yield no value.
    """
    if not isinstance(response, Response) or not aware(as_of) or not aware(response.retrieved_at):
        raise ValueError('source response and aware timestamps required')
    if not isinstance(cik, str) or not re.fullmatch(r'[0-9]{10}', cik) or int(cik) == 0:
        raise ValueError('canonical issuer required')
    if response.retrieved_at > as_of:
        raise ProviderFailure(Status.INVALID_DATA)
    pattern = rf'https://www\.sec\.gov/Archives/edgar/data/{int(cik)}/[0-9]{{18}}/[A-Za-z0-9_-][A-Za-z0-9_.-]*\.html?'
    if not re.fullmatch(pattern, response.url) or '..' in response.url:
        raise ProviderFailure(Status.INVALID_DATA)
    period = annual_period(response.body, cik=cik, report_end=report_end, document_type=document_type)
    p = CoverParser(extra_concepts=CONCEPTS.values())
    try:
        p.feed(response.body.decode('utf-8')); p.close()
    except (UnicodeError, ValueError):
        raise ProviderFailure(Status.INVALID_DATA) from None
    if p.conflict or p.fact_stack or p.context is not None:
        raise ProviderFailure(Status.INVALID_DATA)
    if p.namespaces.get('xbrli') != {'http://www.xbrl.org/2003/instance'} or p.namespaces.get('ix') not in (
            {'http://www.xbrl.org/2013/inlineXBRL'}, {'http://www.xbrl.org/2008/inlineXBRL'}):
        raise ProviderFailure(Status.INVALID_DATA)
    for key in period['context_ids']:
        c = p.contexts[key]
        if c.get('element_tag') != 'xbrli:context' or any(c.get(k+'_element_tag') != 'xbrli:'+k for k in ('identifier', 'startdate', 'enddate')):
            raise ProviderFailure(Status.INVALID_DATA)
    if any(f['element_tag'] != 'ix:nonnumeric' for f in p.facts if f['context'] in period['context_ids']
           and f['name'] in ('documenttype', 'documentfiscalperiodfocus', 'documentperiodenddate')):
        raise ProviderFailure(Status.INVALID_DATA)
    results = _disclosures(p, period['context_ids'])
    return dict(issuer_id=cik, document_type=document_type, report_end=report_end.isoformat(),
                period_start=period['period_start'], source_url=response.url,
                raw_sha256=response.sha256, retrieved_at=response.retrieved_at.isoformat(),
                as_of=as_of.isoformat(), disclosures=results,
                legal_type_approved=False, scope_approved=False, investment_approved=False,
                evidence_basis='literal tagged disclosures in verified non-dimensional annual document contexts')


def _boolean(text, format_label, namespaces):
    if not format_label:
        if text in ('true', '1', 'false', '0'):
            return text in ('true', '1')
        raise ValueError('unsupported literal boolean')
    prefix, local = format_label.split(':')
    bound = namespaces.get(prefix, set())
    if bound == {'http://www.sec.gov/inlineXBRL/transformation/2015-08-31'} and local == 'boolballotbox':
        return {'☐': False, '☑': True, '☒': True}[text]
    if bound in ({'http://www.xbrl.org/inlineXBRL/transformation/2020-02-12'},
                 {'http://www.xbrl.org/inlineXBRL/transformation/2022-02-16'}):
        if local in ('fixed-true', 'fixed-false'):
            return local == 'fixed-true'
    raise ValueError('unsupported boolean transform')


def _disclosures(p, context_ids, *, allow_transforms=False):
    results = {}
    for field, concept in CONCEPTS.items():
        prefix, local = concept.split(':')
        candidates = [f for f in p.facts if f['prefix'] == prefix and f['name'] == local
                      and f['context'] in context_ids]
        evidence = []
        decoded = []
        invalid = False
        for f in candidates:
            evidence.append(dict(context_id=f['context'], concept=concept,
                                 raw_text=f['text'], nil=f['nil'], format=f['format']))
            if f['nil'] in ('true', '1'):
                continue
            if f['element_tag'] != 'ix:nonnumeric' or f['nil'] not in (None, 'false', '0') or (f['format'] and not allow_transforms):
                invalid = True; continue
            namespaces = p.namespaces.get(prefix, set())
            if len(namespaces) != 1 or not re.fullmatch(rf'http://xbrl\.sec\.gov/{prefix}/20[0-9]{{2}}', next(iter(namespaces), '')):
                invalid = True; continue
            text = ' '.join(f['text'].split())
            if field == 'investment_company_type':
                if text not in INVESTMENT_TYPES or f['format']:
                    invalid = True; continue
                decoded.append(text)
            else:
                try:
                    decoded.append(_boolean(text, f['format'], p.namespaces))
                except (ValueError, KeyError):
                    invalid = True
        unique = set(decoded)
        status = ('unsupported_encoding_or_value' if invalid else 'conflicting' if len(unique) > 1
                  else 'reported' if unique else 'unknown')
        results[field] = dict(status=status, value=next(iter(unique)) if status == 'reported' else None,
                              evidence=evidence)
    results['reit'] = dict(status='unsupported_requires_document_review', value=None, evidence=[])
    return results


def registration_legal_evidence(response, *, cik, disclosure_date, document_type, as_of):
    """N-2 cover disclosures have same-day durations, never inferred fiscal periods.

    document_type is the literal cover label; an EDGAR POS EX amendment may
    still contain DocumentType=N-2. This does not identify its EDGAR form code.
    """
    if not isinstance(response, Response) or not aware(as_of) or not aware(response.retrieved_at):
        raise ValueError('source response and aware timestamps required')
    if not isinstance(cik, str) or not re.fullmatch(r'[0-9]{10}', cik) or int(cik) == 0:
        raise ValueError('canonical issuer required')
    if type(disclosure_date) is not date or document_type not in ('N-2', 'N-2/A', 'N-2ASR'):
        raise ValueError('explicit registration cover type and disclosure date required')
    pattern = rf'https://www\.sec\.gov/Archives/edgar/data/{int(cik)}/[0-9]{{18}}/[A-Za-z0-9_-][A-Za-z0-9_.-]*\.html?'
    if response.retrieved_at > as_of or disclosure_date > response.retrieved_at.date() or not re.fullmatch(pattern, response.url) or '..' in response.url:
        raise ProviderFailure(Status.INVALID_DATA)
    p = CoverParser(extra_concepts=CONCEPTS.values())
    try:
        p.feed(response.body.decode('utf-8')); p.close()
    except (UnicodeError, ValueError):
        raise ProviderFailure(Status.INVALID_DATA) from None
    if p.conflict or p.fact_stack or p.context is not None:
        raise ProviderFailure(Status.INVALID_DATA)
    for prefix, uri in [('xbrli', 'http://www.xbrl.org/2003/instance'),
                        ('ix', 'http://www.xbrl.org/2013/inlineXBRL')]:
        if p.namespaces.get(prefix) != {uri}:
            raise ProviderFailure(Status.INVALID_DATA)
    dei = p.namespaces.get('dei', set())
    if len(dei) != 1 or not re.fullmatch(r'http://xbrl\.sec\.gov/dei/20[0-9]{2}', next(iter(dei), '')):
        raise ProviderFailure(Status.INVALID_DATA)
    selected = []
    for key, c in p.contexts.items():
        if c['dimensional'] or c.get('element_tag') != 'xbrli:context' or c.get('scheme') != 'http://www.sec.gov/CIK':
            continue
        if c.get('identifier', '').strip().zfill(10) != cik:
            continue
        if any(c.get(k+'_element_tag') != 'xbrli:'+k for k in ('identifier', 'startdate', 'enddate')):
            continue
        if c.get('startdate', '').strip() != disclosure_date.isoformat() or c.get('enddate', '').strip() != disclosure_date.isoformat():
            continue
        anchors = {}
        for f in p.facts:
            if f['context'] != key or f['prefix'] != 'dei' or f['element_tag'] != 'ix:nonnumeric' or f['format'] or f['nil'] not in (None, 'false', '0'):
                continue
            anchors.setdefault(f['name'], set()).add(' '.join(f['text'].split()))
        if anchors.get('documenttype') == {document_type} and anchors.get('entitycentralindexkey') == {cik}:
            selected.append(key)
    if not selected:
        raise ProviderFailure(Status.INVALID_DATA)
    results = _disclosures(p, selected, allow_transforms=True)
    return dict(issuer_id=cik, document_type=document_type, disclosure_date=disclosure_date.isoformat(),
                context_ids=sorted(selected), source_url=response.url,
                raw_sha256=response.sha256, retrieved_at=response.retrieved_at.isoformat(),
                as_of=as_of.isoformat(), disclosures=results,
                legal_type_approved=False, scope_approved=False, investment_approved=False,
                fiscal_period_inferred=False,
                evidence_basis='literal registration disclosures sharing issuer/document-type same-day duration context')
