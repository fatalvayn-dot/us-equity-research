"""Exact public response observations; no credentials, headers or refreshed replay dates."""
import re,sqlite3
from datetime import datetime,timezone
from pathlib import Path
from urllib.parse import parse_qsl,urlsplit

from .models import aware
from .providers import ProviderFailure,Status
from .transport import HttpTransport,Response

PUBLIC_HOSTS=frozenset({'www.sec.gov','data.sec.gov','query1.finance.yahoo.com','api.nasdaq.com','www.nasdaq.com'})


def public_url(url):
    parts=urlsplit(url)
    if parts.scheme!='https' or parts.hostname not in PUBLIC_HOSTS or parts.port not in (None,443) or parts.username or parts.password or parts.fragment:
        raise ValueError('public source origin required')
    if any(ord(c)<32 for c in url):raise ValueError('invalid URL')
    for key,value in parse_qsl(parts.query,keep_blank_values=True):
        key=re.sub('[^a-z0-9]','',key.lower())
        if any(word in key for word in ('token','apikey','password','secret','authorization','crumb')) or key=='key':
            raise ValueError('credential-bearing URL cannot be archived')


class ResponseArchive:
    def __init__(self,path):
        Path(path).parent.mkdir(parents=True,exist_ok=True)
        self.db=sqlite3.connect(path)
        with self.db:
            self.db.execute('CREATE TABLE IF NOT EXISTS response_bodies_v1 (sha256 TEXT PRIMARY KEY,body BLOB NOT NULL)')
            self.db.execute('CREATE TABLE IF NOT EXISTS response_observations_v1 (url TEXT,sha256 TEXT,retrieved_at TEXT,PRIMARY KEY(url,sha256,retrieved_at))')
    def record(self,response):
        public_url(response.url)
        if not aware(response.retrieved_at) or type(response.body) is not bytes:raise ValueError('exact bytes and aware observation required')
        stamp=response.retrieved_at.astimezone(timezone.utc).isoformat()
        with self.db:
            existing=self.db.execute('SELECT body FROM response_bodies_v1 WHERE sha256=?',(response.sha256,)).fetchone()
            if existing and existing[0]!=response.body:raise ValueError('corrupt content-addressed body')
            self.db.execute('INSERT OR IGNORE INTO response_bodies_v1 VALUES (?,?)',(response.sha256,response.body))
            self.db.execute('INSERT OR IGNORE INTO response_observations_v1 VALUES (?,?,?)',(response.url,response.sha256,stamp))
    def get(self,url,sha256,observed_at=None):
        public_url(url)
        query='SELECT b.body,o.retrieved_at FROM response_observations_v1 o JOIN response_bodies_v1 b USING (sha256) WHERE o.url=? AND o.sha256=?'
        values=[url,sha256]
        if observed_at is not None:
            if not aware(observed_at):raise ValueError('aware observation required')
            query+=' AND o.retrieved_at=?';values.append(observed_at.astimezone(timezone.utc).isoformat())
        else:query+=' ORDER BY o.retrieved_at ASC'
        row=self.db.execute(query,values).fetchone()
        if row is None:return None
        r=Response(url,row[0],datetime.fromisoformat(row[1]))
        if r.sha256!=sha256 or not aware(r.retrieved_at):raise ValueError('archive integrity failure')
        return r
    def observations(self):
        return [dict(url=r[0],sha256=r[1],retrieved_at=r[2]) for r in self.db.execute('SELECT url,sha256,retrieved_at FROM response_observations_v1 ORDER BY url,retrieved_at')]
    def close(self):self.db.close()


class ArchivedTransport(HttpTransport):
    def __init__(self,*,archive,**kwargs):
        if kwargs.get('auth_headers') or not set(kwargs.get('allowed_hosts',())).issubset(PUBLIC_HOSTS):
            raise ValueError('only unauthenticated public sources can be archived')
        super().__init__(**kwargs);self.archive=archive
    def get(self,url):
        public_url(url)  # Reject credential URLs before any request or archive write.
        response=super().get(url)
        try:self.archive.record(response)
        except Exception:raise ProviderFailure(Status.EVIDENCE_ERROR) from None
        return response


from .companyfacts import SecCompanyFacts

class ArchivedCompanyFacts(SecCompanyFacts):
    def __init__(self,transport,*,archive,**kwargs):
        super().__init__(transport,**kwargs);self.archive=archive
    def snapshot(self,cik,*,refresh=False):
        result=super().snapshot(cik,refresh=refresh)
        try:self.archive.record(result[0])
        except Exception:raise ProviderFailure(Status.EVIDENCE_ERROR) from None
        return result
