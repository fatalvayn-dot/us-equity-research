"""Lease-protected raw filing checkpoints; parser outcomes never imply scope approval."""
import hashlib
from datetime import date,datetime,timedelta,timezone

from . import __version__
from .annual_period import annual_period
from .batch import BatchStore,RunBusy,packed
from .filing_metadata import filing_security_metadata
from .models import aware
from .providers import ProviderFailure,Status
from .submissions import ANNUAL_FORMS,submissions_url
from .transport import Response
import re


def document_key(cik,annual):
    submissions_url(cik)
    accession=annual['accession'];name=annual['primary_document']
    if not re.fullmatch(r'[0-9]{10}-[0-9]{2}-[0-9]{6}',accession):raise ValueError('invalid accession')
    if not re.fullmatch(r'[A-Za-z0-9_-][A-Za-z0-9_.-]*',name) or '..' in name:raise ValueError('unsafe document')
    expected=f'https://www.sec.gov/Archives/edgar/data/{int(cik)}/{accession.replace("-","")}/{name}'
    if annual['source_url']!=expected or annual['form'] not in ANNUAL_FORMS:raise ValueError('wrong filing identity/origin')
    if date.fromisoformat(annual['report_end'])>date.fromisoformat(annual['filed_on']):raise ValueError('invalid filing dates')
    return hashlib.sha256(packed(dict(issuer_id=cik,annual=annual)).encode()).hexdigest()


class FilingStore(BatchStore):
    def __init__(self,path):
        super().__init__(path)
        with self.db:self.db.execute('CREATE TABLE IF NOT EXISTS filing_documents_v1 (key TEXT PRIMARY KEY,url TEXT,body BLOB,sha256 TEXT,retrieved_at TEXT)')

    def get(self,cik,annual,now,ttl):
        key=document_key(cik,annual)
        row=self.db.execute('SELECT url,body,sha256,retrieved_at FROM filing_documents_v1 WHERE key=?',(key,)).fetchone()
        if row is None:return None
        try:
            response=Response(row[0],row[1],datetime.fromisoformat(row[3]))
            if response.url!=annual['source_url'] or response.sha256!=row[2] or not aware(response.retrieved_at):raise ValueError('invalid source checkpoint')
            if timedelta(0)<=now-response.retrieved_at<ttl:return response
        except (ValueError,TypeError):self.events.append(dict(key=key,event='invalid_document_checkpoint'))
        return None

    def put(self,cik,annual,response,owner,now,lease_ttl):
        key=document_key(cik,annual)
        if not aware(now) or not aware(response.retrieved_at) or response.retrieved_at>now or response.url!=annual['source_url']:
            raise ValueError('invalid source chronology/origin')
        now=now.astimezone(timezone.utc)
        with self.db:
            self.db.execute('BEGIN IMMEDIATE')
            lease=self.db.execute('SELECT owner,expires FROM batch_lease_v1 WHERE singleton=1').fetchone()
            if not lease or lease[0]!=owner or datetime.fromisoformat(lease[1])<now:raise RunBusy('document checkpoint lease lost')
            self.db.execute('INSERT OR REPLACE INTO filing_documents_v1 VALUES (?,?,?,?,?)',
                (key,response.url,response.body,response.sha256,response.retrieved_at.isoformat()))
            self.db.execute('UPDATE batch_lease_v1 SET expires=? WHERE owner=?',((now+lease_ttl).isoformat(),owner))


class DocumentRunner:
    def __init__(self,store,transport,*,clock=None,ttl=timedelta(hours=6),lease_ttl=timedelta(minutes=15)):
        if min(ttl,lease_ttl)<=timedelta(0):raise ValueError('positive checkpoint policy required')
        self.store,self.transport=store,transport
        self.clock=clock or (lambda:datetime.now(timezone.utc));self.ttl=ttl;self.lease_ttl=lease_ttl

    def run(self,companies,*,max_new_documents):
        companies=tuple(companies);now=self.clock()
        if not aware(now) or type(max_new_documents) is not int or max_new_documents<0:raise ValueError('aware clock and work bound required')
        if len({r['issuer_id'] for r in companies})!=len(companies) or len({r['symbol'] for r in companies})!=len(companies):raise ValueError('duplicate company')
        # Validate every address before any network request or lease acquisition.
        for row in companies:
            if row.get('annual'):
                document_key(row['issuer_id'],row['annual'])
                if date.fromisoformat(row['annual']['filed_on'])>now.date():raise ValueError('future filing')
        owner=self.store.acquire(now,self.lease_ttl);new=0;reused=0;output=[];events_start=len(self.store.events)
        try:
            for row in companies:
                now=self.clock();self.store.renew(owner,now,self.lease_ttl)
                result=dict(symbol=row['symbol'],issuer_id=row['issuer_id'],scope_approved=False)
                annual=row.get('annual')
                if not annual:result['state']='no_annual_in_recent_window'
                elif not annual['primary_document'].lower().endswith(('.htm','.html')):result['state']='unsupported_document_format'
                else:
                    response=self.store.get(row['issuer_id'],annual,now,self.ttl);cached=response is not None
                    if response is None and new>=max_new_documents:result['state']='not_started'
                    else:
                        try:
                            if response is None:
                                new+=1
                                response=self.transport.get(annual['source_url'])
                                self.store.put(row['issuer_id'],annual,response,owner,self.clock(),self.lease_ttl)
                            else:reused+=1
                            result.update(state='source_available',cached=cached,annual=annual,
                                source_evidence=dict(url=response.url,sha256=response.sha256,retrieved_at=response.retrieved_at.isoformat()))
                            args=dict(cik=row['issuer_id'],report_end=date.fromisoformat(annual['report_end']),document_type=annual['form'])
                            for field,parser in [('period',annual_period),('registered_share',filing_security_metadata)]:
                                try:result[field]=parser(response.body,**args,**({'symbol':row['symbol']} if field=='registered_share' else {}))
                                except ProviderFailure as exc:result[field+'_status']=exc.status.value
                        except ProviderFailure as exc:
                            result.update(state=exc.status.value,reason=exc.reason.value if exc.reason else None,http_status=exc.http_status)
                result['completed_at']=self.clock().isoformat()
                outcome_key='document-outcome:'+__version__+':'+row['issuer_id']
                self.store.write(outcome_key,result,owner,self.clock(),self.lease_ttl)
                output.append(result)
        finally:self.store.release(owner)
        return dict(companies=output,generated_at=self.clock().isoformat(),summary=dict(companies=len(output),new_documents=new,reused_documents=reused,
            periods=sum('period' in r for r in output),registered_shares=sum('registered_share' in r for r in output)),
            checkpoint_events=self.store.events[events_start:],scope_approved=False,hundred_company_accepted=False,investment_approved=False)
