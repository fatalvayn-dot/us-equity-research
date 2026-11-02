"""Original iXBRL concept/period diagnostics; never substitutes accounting concepts."""
import hashlib,re
from datetime import date
from decimal import Decimal,InvalidOperation,localcontext
from html.parser import HTMLParser


class Inventory(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.contexts={};self.units={};self.namespaces={};self.facts=[];self.conflict=False
        self.context=None;self.capture=None;self.unit=None;self.measure=False;self.stack=[]
    def handle_starttag(self,tag,attrs):
        attrs=dict(attrs);local=tag.rsplit(':',1)[-1]
        for key,value in attrs.items():
            if key.startswith('xmlns:'):
                prefix=key[6:]
                if prefix in self.namespaces and self.namespaces[prefix]!=value:self.conflict=True
                self.namespaces[prefix]=value
        if local=='context':self.context={'id':attrs.get('id'),'dimensional':False}
        elif self.context is not None:
            if local in ('segment','scenario','explicitmember','typedmember'):self.context['dimensional']=True
            if local in ('identifier','instant','startdate','enddate'):
                self.capture=local;self.context[local]=''
                if local=='identifier':self.context['scheme']=attrs.get('scheme')
        if local=='unit':self.unit={'id':attrs.get('id'),'measures':[],'compound':False}
        elif self.unit is not None:
            if local=='measure':self.measure=True;self.unit['measures'].append('')
            if local in ('divide','unitnumerator','unitdenominator'):self.unit['compound']=True
        if local=='nonfraction':self.stack.append({'attrs':attrs,'text':'','excluded':False})
        elif local=='exclude' and self.stack:self.stack[-1]['excluded']=True
    def handle_data(self,data):
        if self.context is not None and self.capture:self.context[self.capture]+=data
        if self.unit is not None and self.measure:self.unit['measures'][-1]+=data
        for fact in self.stack:fact['text']+=data
    def handle_endtag(self,tag):
        local=tag.rsplit(':',1)[-1]
        if local=='context' and self.context is not None:
            key=self.context['id']
            if not key:self.conflict=True
            if key in self.contexts and self.contexts[key]!=self.context:self.conflict=True
            self.contexts[key]=self.context;self.context=None;self.capture=None
        elif local in ('identifier','instant','startdate','enddate'):self.capture=None
        if local=='measure':self.measure=False
        if local=='unit' and self.unit is not None:
            key=self.unit['id']
            if not key:self.conflict=True
            if key in self.units and self.units[key]!=self.unit:self.conflict=True
            self.units[key]=self.unit;self.unit=None
        if local=='nonfraction':
            if not self.stack:self.conflict=True
            else:self.facts.append(self.stack.pop())


def number(fact,unit,namespaces):
    a=fact['attrs']
    if a.get('xsi:nil','false').lower() in ('true','1'):raise ValueError('nil')
    if fact['excluded'] or a.get('continuedat') or a.get('sign') not in (None,'-'):raise ValueError('unsupported presentation')
    if not unit or unit['compound'] or [s.strip() for s in unit['measures']]!=['iso4217:USD']:raise ValueError('unsupported unit')
    if a.get('format'):
        prefix,separator,local=a['format'].partition(':')
        if not separator or local.lower() not in ('num-dot-decimal','numdotdecimal'):raise ValueError('unsupported transform')
        if namespaces.get(prefix) not in ('http://www.xbrl.org/inlineXBRL/transformation/2020-02-12','http://www.xbrl.org/inlineXBRL/transformation/2022-02-16'):
            raise ValueError('unsupported transform namespace')
    text=fact['text'].strip()
    if not re.fullmatch(r'(?:[0-9]+|[0-9]{1,3}(?:,[0-9]{3})+)(?:\.[0-9]+)?',text):raise ValueError('unsupported numeric text')
    scale=int(a.get('scale','0'))
    if not -12<=scale<=12:raise ValueError('unsupported scale')
    digits=text.replace(',','').replace('.','')
    if len(digits)>100:raise ValueError('oversized numeric value')
    with localcontext() as ctx:
        ctx.prec=128
        value=Decimal(text.replace(',',''))*(Decimal(10)**scale)
    if a.get('sign')=='-':value=-value
    if not value.is_finite():raise ValueError('nonfinite')
    return value


def inspect_concepts(body,*,cik,concepts,period_start,period_end):
    """Keep exact, dimensional, period and presentation failures distinct."""
    if not isinstance(cik,str) or not re.fullmatch('[0-9]{10}',cik) or int(cik)==0:raise ValueError('canonical issuer required')
    if type(period_end) is not date or (period_start is not None and (type(period_start) is not date or period_start>=period_end)):raise ValueError('exact period required')
    p=Inventory();p.feed(body.decode('utf-8'));p.close()
    if p.conflict or p.stack or p.context is not None or p.unit is not None:raise ValueError('conflicting/truncated XBRL')
    gaap=p.namespaces.get('us-gaap','')
    if not re.fullmatch(r'https?://fasb.org/us-gaap/20[0-9]{2}',gaap):raise ValueError('unverified US GAAP namespace')
    if p.namespaces.get('iso4217')!='http://www.xbrl.org/2003/iso4217':raise ValueError('unverified currency namespace')
    results=[]
    for concept in concepts:
        if not re.fullmatch(r'us-gaap:[A-Za-z][A-Za-z0-9]*',concept):raise ValueError('explicit standard concept required')
        matches=[];exact=[];present=0;other_period=0;dimensional=0;unsupported=0
        for f in p.facts:
            a=f['attrs']
            if a.get('name','').lower()!=concept.lower():continue
            present+=1;c=p.contexts.get(a.get('contextref'))
            if not c or c.get('scheme')!='http://www.sec.gov/CIK' or c.get('identifier','').strip().zfill(10)!=cik:continue
            requested=(c.get('instant','').strip()==period_end.isoformat() and not c.get('startdate') if period_start is None else
                c.get('startdate','').strip()==period_start.isoformat() and c.get('enddate','').strip()==period_end.isoformat() and not c.get('instant'))
            if not requested:other_period+=1;continue
            if c['dimensional']:dimensional+=1;continue
            try:value=number(f,p.units.get(a.get('unitref')),p.namespaces)
            except (ValueError,InvalidOperation,TypeError):unsupported+=1;continue
            exact.append(value);matches.append(dict(context_id=a.get('contextref'),unit_id=a.get('unitref'),value=str(value)))
        unique=set(exact)
        status=('ambiguous_original_values' if len(unique)>1 else 'unsupported_numeric_or_unit' if unsupported else
            'exact_original_value' if len(unique)==1 else 'dimensional_only' if dimensional else
            'period_or_scope_mismatch' if present else 'concept_not_disclosed')
        results.append(dict(concept=concept,taxonomy_namespace=gaap,status=status,value=str(next(iter(unique))) if status=='exact_original_value' else None,currency='USD',
            matches=matches,present_facts=present,other_period_facts=other_period,dimensional_facts=dimensional,unsupported_facts=unsupported))
    return dict(issuer_id=cik,period_start=period_start.isoformat() if period_start else None,period_end=period_end.isoformat(),
        raw_sha256=hashlib.sha256(body).hexdigest(),concepts=results,automatic_substitution=False,scope_approved=False)
