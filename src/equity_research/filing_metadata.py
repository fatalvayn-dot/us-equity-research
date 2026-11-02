"""Narrow registered-security corroboration; does not decide fund/legal status."""
import hashlib,re
from datetime import date
from html.parser import HTMLParser
from .providers import ProviderFailure,Status

TAGS=frozenset({'documenttype','documentperiodenddate','entitycentralindexkey',
    'security12btitle','securityexchangename','tradingsymbol','entityshellcompany',
    'entityinvestmentcompanytype','documentfiscalperiodfocus','documentfiscalyearfocus'})

class CoverParser(HTMLParser):
    def __init__(self,extra_concepts=()):
        super().__init__(convert_charrefs=True)
        self.extra_concepts=frozenset(c.lower() for c in extra_concepts);self.namespaces={}
        self.dei_namespaces=set();self.contexts={};self.context=None;self.capture=None;self.fact=None;self.fact_stack=[];self.facts=[];self.conflict=False
    def handle_starttag(self,tag,attrs):
        attrs=dict(attrs);local=tag.rsplit(':',1)[-1]
        for key,value in attrs.items():
            if key.startswith('xmlns:'):self.namespaces.setdefault(key[6:],set()).add(value)
        if 'xmlns:dei' in attrs:self.dei_namespaces.add(attrs['xmlns:dei'])
        if local=='context':self.context={'id':attrs.get('id'),'dimensional':False,'element_tag':tag}
        elif self.context is not None and local in ('identifier','startdate','enddate','instant'):
            self.capture=local;self.context[local]=''
            self.context[local+'_element_tag']=tag
            if local=='identifier':self.context['scheme']=attrs.get('scheme')
        if self.context is not None and local in ('segment','scenario','explicitmember','typedmember'):self.context['dimensional']=True
        if local=='nonnumeric':
            fact=None
            name=attrs.get('name','').lower()
            if (name.startswith('dei:') and name[4:] in TAGS) or name in self.extra_concepts:
                if attrs.get('continuedat'):self.conflict=True  # unsupported continuation is never guessed
                fact={'name':name.split(':',1)[1],'prefix':name.split(':',1)[0],'element_tag':tag,'context':attrs.get('contextref'),'text':'','nil':attrs.get('xsi:nil'),'format':attrs.get('format')}
            self.fact_stack.append(fact)
            self.fact=next((f for f in reversed(self.fact_stack) if f is not None),None)
        if local=='exclude' and self.fact is not None:self.conflict=True
    def handle_data(self,data):
        if self.context is not None and self.capture:self.context[self.capture]+=data
        for fact in self.fact_stack:
            if fact is not None:fact['text']+=data
    def handle_endtag(self,tag):
        local=tag.rsplit(':',1)[-1]
        if local=='context' and self.context is not None:
            key=self.context['id']
            if key in self.contexts and self.contexts[key]!=self.context:self.conflict=True
            self.contexts[key]=self.context;self.context=None;self.capture=None
        elif local in ('identifier','startdate','enddate','instant'):self.capture=None
        if local=='nonnumeric':
            if not self.fact_stack:self.conflict=True
            else:
                fact=self.fact_stack.pop()
                if fact is not None:self.facts.append(fact)
            self.fact=next((f for f in reversed(self.fact_stack) if f is not None),None)


def inline_date(text,format_label):
    if format_label in (None,''):return date.fromisoformat(text)
    if format_label.split(':')[-1]!='date-monthname-day-year-en':raise ValueError('unsupported inline date transformation')
    months=('January','February','March','April','May','June','July','August','September','October','November','December')
    match=re.fullmatch(r'([A-Za-z]+) ([0-9]{1,2}), ([0-9]{4})',text)
    if not match or match[1] not in months:raise ValueError('unsupported date text')
    return date(int(match[3]),months.index(match[1])+1,int(match[2]))


def filing_security_metadata(body,*,cik,symbol,report_end,document_type):
    """Exact symbol and same-context title/exchange required, including class dimensions."""
    try:
        if not re.fullmatch(r'[0-9]{10}',cik) or int(cik)==0 or not symbol or not isinstance(report_end,date):raise ValueError('identity')
        p=CoverParser();p.feed(body.decode('utf-8'));p.close()
        if p.conflict or p.fact is not None:raise ValueError('conflicting/truncated cover')
        if len(p.dei_namespaces)!=1 or not re.fullmatch(r'http://xbrl.sec.gov/dei/20[0-9]{2}',next(iter(p.dei_namespaces))):
            raise ValueError('unverified dei namespace')
        values={};all_values={}
        for fact in p.facts:
            context=p.contexts.get(fact['context'])
            if not context or context.get('scheme')!='http://www.sec.gov/CIK':continue
            if context.get('identifier','').strip().zfill(10)!=cik:continue
            if (context.get('enddate') or context.get('instant') or '').strip()!=report_end.isoformat():continue
            if fact['nil'] in ('true','1'):continue
            text=' '.join(fact['text'].split())
            if not text:continue
            if fact['name']=='documentperiodenddate':text=inline_date(text,fact['format']).isoformat()
            values.setdefault(fact['context'],{}).setdefault(fact['name'],set()).add(text)
            all_values.setdefault(fact['name'],set()).add(text)
        if all_values.get('documenttype')!={document_type} or all_values.get('documentperiodenddate')!={report_end.isoformat()}:
            raise ValueError('document mismatch')
        registered=[]
        for context,row in values.items():
            if row.get('tradingsymbol')!={symbol}:continue
            if len(row.get('security12btitle',set()))!=1 or len(row.get('securityexchangename',set()))!=1:continue
            title=next(iter(row['security12btitle']))
            if not re.search(r'\b(common|ordinary)\s+(stock|shares?)\b',title,re.I):continue
            if re.search(r'\b(preferred|depositary|depository|warrants?|units?|notes?|bonds?)\b',title,re.I):continue
            registered.append(dict(context_id=context,symbol=symbol,title=title,exchange=next(iter(row['securityexchangename']))))
        unique={(r['title'],r['exchange']) for r in registered}
        if len(unique)!=1:raise ValueError('missing or conflicting registered security')
        title,exchange=next(iter(unique))
        common=bool(re.search(r'\b(common|ordinary)\s+(stock|shares?)\b',title,re.I))
        forbidden=bool(re.search(r'\b(preferred|depositary|depository|warrants?|units?|notes?|bonds?)\b',title,re.I))
        return dict(issuer_id=cik,symbol=symbol,report_end=report_end.isoformat(),document_type=document_type,
            raw_sha256=hashlib.sha256(body).hexdigest(),registered_security=registered,
            explicit_common_share_title=common and not forbidden,
            entity_shell_labels=sorted(all_values.get('entityshellcompany',set())),
            investment_company_labels=sorted(all_values.get('entityinvestmentcompanytype',set())),
            legal_type_approved=False,scope_approved=False)
    except (UnicodeError,ValueError,KeyError,TypeError):raise ProviderFailure(Status.INVALID_DATA) from None
