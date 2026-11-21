"""Explicit annual document contexts only; no calendar-derived fiscal starts."""
import hashlib,re
from datetime import date
from .filing_metadata import CoverParser,inline_date
from .providers import ProviderFailure,Status


def annual_period(body,*,cik,report_end,document_type):
    try:
        if not isinstance(cik,str) or not re.fullmatch(r'[0-9]{10}',cik) or int(cik)==0:
            raise ValueError('canonical issuer required')
        if document_type not in ('10-K','20-F','40-F') or type(report_end) is not date:raise ValueError('annual identity required')
        p=CoverParser();p.feed(body.decode('utf-8'));p.close()
        if p.conflict or p.context is not None or p.fact is not None:raise ValueError('conflicting/truncated context')
        if len(p.dei_namespaces)!=1 or not re.fullmatch(r'http://xbrl.sec.gov/dei/20[0-9]{2}',next(iter(p.dei_namespaces))):
            raise ValueError('dei namespace required')
        # Current annual duration must be shared by the document type and FY
        # focus facts. Prior years and segment/security-class contexts cannot win.
        contexts={}
        for fact in p.facts:
            if fact['nil'] in ('true','1'):continue
            c=p.contexts.get(fact['context'])
            if not c or c['dimensional'] or c.get('scheme')!='http://www.sec.gov/CIK':continue
            if c.get('identifier','').strip().zfill(10)!=cik or c.get('enddate','').strip()!=report_end.isoformat():continue
            text=' '.join(fact['text'].split())
            if fact['name']=='documentperiodenddate':text=inline_date(text,fact['format']).isoformat()
            contexts.setdefault(fact['context'],{}).setdefault(fact['name'],set()).add(text)
        candidates=[]
        for context,row in contexts.items():
            if row.get('documenttype')!={document_type} or row.get('documentfiscalperiodfocus')!={'FY'}:continue
            if row.get('documentperiodenddate')!={report_end.isoformat()}:continue
            c=p.contexts[context];start=date.fromisoformat(c['startdate'].strip());end=date.fromisoformat(c['enddate'].strip())
            if not start<end or (end-start).days>550:raise ValueError('implausible document duration')
            candidates.append((start,end,context))
        if len({(s,e) for s,e,c in candidates})!=1:raise ValueError('missing/ambiguous annual document context')
        start,end,_=candidates[0]
        return dict(issuer_id=cik,document_type=document_type,period_start=start.isoformat(),period_end=end.isoformat(),
            context_ids=sorted(c for s,e,c in candidates),raw_sha256=hashlib.sha256(body).hexdigest(),
            evidence_basis='non-dimensional issuer duration shared by DocumentType, DocumentFiscalPeriodFocus=FY and DocumentPeriodEndDate',
            calendar_start_inferred=False,financial_values_validated=False,scope_approved=False)
    except (UnicodeError,KeyError,ValueError,TypeError):raise ProviderFailure(Status.INVALID_DATA) from None
