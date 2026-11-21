"""SEC current submissions metadata, not legal-type approval or historical availability."""
import re
import sqlite3
from dataclasses import dataclass,replace
from datetime import date,datetime,timedelta,timezone
from pathlib import Path

from .models import aware
from .providers import ProviderFailure,Status
from .transport import Response,strict_json

ANNUAL_FORMS=frozenset({'10-K','20-F','40-F'})


def submissions_url(cik):
    if not isinstance(cik,str) or not re.fullmatch(r'[0-9]{10}',cik) or int(cik)==0:
        raise ValueError('canonical issuer required')
    return f'https://data.sec.gov/submissions/CIK{cik}.json'


@dataclass(frozen=True)
class AnnualFiling:
    accession: str
    form: str
    filed_on: date
    report_end: date
    primary_document: str
    source_url: str
    acceptance_label: str
    document_format: str="html"


@dataclass(frozen=True)
class SubmissionSnapshot:
    issuer_id: str
    name: str
    entity_type_label: str | None
    sic_label: str | None
    sic_description: str | None
    tickers: tuple[str,...]
    fiscal_year_end_label: str | None
    annual_filings: tuple[AnnualFiling,...]
    older_file_count: int
    source_url: str
    raw_sha256: str
    retrieved_at: datetime
    cached: bool=False

    def latest_annual(self):
        # A report's end is explicit. No start date or reporting currency inferred.
        if not self.annual_filings:return None
        return max(self.annual_filings,key=lambda f:(f.report_end,f.filed_on,f.accession))

    def readiness(self,symbol):
        if symbol not in self.tickers:return 'symbol_mismatch'
        return 'metadata_available_legal_type_pending'


def parse_submissions(response,cik):
    if response.url!=submissions_url(cik) or not aware(response.retrieved_at):raise ProviderFailure(Status.INVALID_DATA)
    p=strict_json(response.body)
    try:
        raw_cik=p['cik']
        if isinstance(raw_cik,bool) or not isinstance(raw_cik,(str,int)) or not re.fullmatch(r'[0-9]{1,10}',str(raw_cik)):
            raise ValueError('invalid response identity')
        if str(raw_cik).zfill(10)!=cik:raise ProviderFailure(Status.SYMBOL_MISMATCH)
        if not isinstance(p['name'],str) or not p['name'].strip():raise ValueError('missing issuer name')
        tickers=p['tickers']
        if not isinstance(tickers,list) or any(not isinstance(t,str) or not t.strip() or t!=t.strip() for t in tickers) or len(set(tickers))!=len(tickers):
            raise ValueError('invalid tickers')
        recent=p['filings']['recent'];older=p['filings']['files']
        if not isinstance(recent,dict) or not isinstance(older,list):raise ValueError('invalid history')
        keys=('accessionNumber','form','filingDate','reportDate','primaryDocument','acceptanceDateTime')
        if any(not isinstance(recent.get(k),list) for k in keys):raise ValueError('missing columns')
        n=len(recent[keys[0]])
        # Reject any column drift rather than zipping to the shortest list.
        if any(not isinstance(v,list) or len(v)!=n for v in recent.values()):raise ValueError('column length drift')
        seen=set();annual=[]
        for i in range(n):
            row={k:recent[k][i] for k in keys}
            if any(not isinstance(v,str) for v in row.values()):raise ValueError('invalid filing cell')
            accession=row['accessionNumber']
            if not re.fullmatch(r'[0-9]{10}-[0-9]{2}-[0-9]{6}',accession) or accession in seen:raise ValueError('ambiguous accession')
            seen.add(accession)
            if row['form'] not in ANNUAL_FORMS:continue
            filed=date.fromisoformat(row['filingDate']);end=date.fromisoformat(row['reportDate'])
            if end>filed or filed>response.retrieved_at.date():raise ValueError('future annual record')
            document=row['primaryDocument']
            if not re.fullmatch(r'[A-Za-z0-9_-][A-Za-z0-9_.-]*',document) or '..' in document:
                raise ValueError('unsafe primary document')
            url=f'https://www.sec.gov/Archives/edgar/data/{int(cik)}/{accession.replace("-","")}/{document}'
            annual.append(AnnualFiling(accession,row['form'],filed,end,document,url,row['acceptanceDateTime'],
                'html' if document.lower().endswith(('.htm','.html')) else 'unsupported'))
        def label(key):
            value=p.get(key)
            if value is not None and not isinstance(value,str):raise ValueError('invalid metadata label')
            return value
        return SubmissionSnapshot(cik,p['name'],label('entityType'),label('sic'),label('sicDescription'),tuple(tickers),
            label('fiscalYearEnd'),tuple(annual),len(older),response.url,response.sha256,response.retrieved_at)
    except (KeyError,TypeError,ValueError,OverflowError):raise ProviderFailure(Status.INVALID_DATA) from None


class SecSubmissions:
    def __init__(self,transport,*,cache_path=None,ttl=timedelta(hours=6),clock=None):
        if ttl<=timedelta(0):raise ValueError('positive metadata TTL required')
        self.transport=transport;self.ttl=ttl
        self.clock=clock or (lambda:datetime.now(timezone.utc))
        self.events=[];self.db=None
        if cache_path is not None:
            Path(cache_path).parent.mkdir(parents=True,exist_ok=True)
            self.db=sqlite3.connect(cache_path)
            with self.db:self.db.execute('CREATE TABLE IF NOT EXISTS submissions_v1 (cik TEXT PRIMARY KEY, url TEXT, body BLOB, sha256 TEXT, retrieved_at TEXT)')

    def fetch(self,cik):
        url=submissions_url(cik);now=self.clock()
        if not aware(now):raise ValueError('aware clock required')
        if self.db is not None:
            row=self.db.execute('SELECT url,body,sha256,retrieved_at FROM submissions_v1 WHERE cik=?',(cik,)).fetchone()
            if row:
                try:
                    response=Response(row[0],row[1],datetime.fromisoformat(row[3]))
                    if not aware(response.retrieved_at) or response.sha256!=row[2]:raise ValueError('cache integrity')
                    snapshot=parse_submissions(response,cik)
                    if timedelta(0)<=now-snapshot.retrieved_at<self.ttl:return replace(snapshot,cached=True)
                except (ProviderFailure,ValueError,TypeError):self.events.append(dict(issuer_id=cik,event='invalid_metadata_checkpoint'))
        response=self.transport.get(url)
        snapshot=parse_submissions(response,cik)
        if snapshot.retrieved_at>self.clock():raise ProviderFailure(Status.INVALID_DATA)
        if self.db is not None:
            with self.db:self.db.execute('INSERT OR REPLACE INTO submissions_v1 VALUES (?,?,?,?,?)',
                (cik,response.url,response.body,response.sha256,response.retrieved_at.isoformat()))
        return snapshot

    def close(self):
        if self.db is not None:self.db.close()
