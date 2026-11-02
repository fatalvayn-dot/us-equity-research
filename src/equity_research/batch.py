"""Resumable field evidence, not universe acceptance or investment approval."""
import hashlib
import json
import re
import sqlite3
import uuid
from collections import Counter
from dataclasses import asdict,dataclass
from datetime import datetime,timedelta,timezone

from . import __version__
from .cache import decode_fact,encode
from .models import FactQuery,SOURCE_ORDER,aware
from .providers import ProviderFailure


def normalized(value):return json.loads(json.dumps(value,default=encode,sort_keys=True))
def packed(value):return json.dumps(value,default=encode,sort_keys=True,separators=(",",":"))
def digest(value):return hashlib.sha256(value.encode()).hexdigest()


@dataclass(frozen=True)
class CompanyTask:
    symbol: str
    issuer_id: str
    queries: tuple[FactQuery,...]
    scope_status: str = "pending_scope"
    scope_reason: str = "listing_and_legal_type_not_accepted"

    def __post_init__(self):
        if not re.fullmatch(r"[0-9]{10}",self.issuer_id) or int(self.issuer_id)==0 or not self.symbol.strip():
            raise ValueError("explicit issuer/symbol required")
        if self.scope_status not in ("pending_scope","out_of_scope") or not self.scope_reason.strip():
            raise ValueError("scope approval is not implemented; record pending or excluded")
        if not self.queries or any(q.issuer_id!=self.issuer_id for q in self.queries):
            raise ValueError("nonempty same-issuer queries required")
        if len({packed(asdict(q)) for q in self.queries})!=len(self.queries):
            raise ValueError("duplicate exact query")


class RunBusy(RuntimeError):pass


class BatchStore:
    def __init__(self,path):
        self.db=sqlite3.connect(path)
        with self.db:
            self.db.execute("CREATE TABLE IF NOT EXISTS batch_fields_v1 (key TEXT PRIMARY KEY, payload TEXT NOT NULL, checksum TEXT NOT NULL)")
            self.db.execute("CREATE TABLE IF NOT EXISTS batch_lease_v1 (singleton INTEGER PRIMARY KEY CHECK(singleton=1), owner TEXT NOT NULL, expires TEXT NOT NULL)")
        self.events=[]

    def acquire(self,now,ttl):
        if not aware(now) or ttl<=timedelta(0):raise ValueError("aware clock and positive lease required")
        now=now.astimezone(timezone.utc)
        owner=uuid.uuid4().hex
        with self.db:
            self.db.execute("BEGIN IMMEDIATE")
            existing=self.db.execute("SELECT expires FROM batch_lease_v1 WHERE singleton=1").fetchone()
            if existing and datetime.fromisoformat(existing[0])>now:raise RunBusy("checkpoint is in use")
            self.db.execute("INSERT OR REPLACE INTO batch_lease_v1 VALUES (1,?,?)",(owner,(now+ttl).isoformat()))
        return owner

    def renew(self,owner,now,ttl):
        now=now.astimezone(timezone.utc)
        with self.db:
            result=self.db.execute("UPDATE batch_lease_v1 SET expires=? WHERE singleton=1 AND owner=? AND expires>=?",((now+ttl).isoformat(),owner,now.isoformat()))
            if result.rowcount!=1:raise RunBusy("checkpoint lease lost")

    def release(self,owner):
        with self.db:self.db.execute("DELETE FROM batch_lease_v1 WHERE owner=?",(owner,))

    def read(self,key):
        row=self.db.execute("SELECT payload,checksum FROM batch_fields_v1 WHERE key=?",(key,)).fetchone()
        if row is None:return None
        try:
            if digest(row[0])!=row[1]:raise ValueError("invalid checksum")
            return json.loads(row[0])
        except ValueError:
            self.events.append({"key":key,"event":"invalid_checkpoint_checksum_or_json"})
            return None

    def write(self,key,result,owner,now,lease_ttl):
        now=now.astimezone(timezone.utc)
        payload=packed(result)
        with self.db:
            self.db.execute("BEGIN IMMEDIATE")
            lease=self.db.execute("SELECT owner,expires FROM batch_lease_v1 WHERE singleton=1").fetchone()
            if not lease or lease[0]!=owner or datetime.fromisoformat(lease[1])<now:raise RunBusy("checkpoint lease lost")
            self.db.execute("INSERT OR REPLACE INTO batch_fields_v1 VALUES (?,?,?)",(key,payload,digest(payload)))
            self.db.execute("UPDATE batch_lease_v1 SET expires=? WHERE owner=?",((now+lease_ttl).isoformat(),owner))

    def close(self):self.db.close()


class BatchRunner:
    def __init__(self,store,resolver_factory,*,clock=None,policy_version=__version__,
                 fact_ttl=timedelta(hours=6),retry_delay=timedelta(minutes=5),lease_ttl=timedelta(minutes=15)):
        if not policy_version or min(fact_ttl,retry_delay,lease_ttl)<=timedelta(0):raise ValueError("positive checkpoint policy required")
        self.store,self.factory=store,resolver_factory
        self.clock=clock or (lambda:datetime.now(timezone.utc))
        self.policy_version=policy_version
        self.fact_ttl,self.retry_delay,self.lease_ttl=fact_ttl,retry_delay,lease_ttl

    def key(self,company,query):
        return digest(packed({"company":{"symbol":company.symbol,"issuer_id":company.issuer_id},"query":asdict(query),"policy_version":self.policy_version}))

    def _validate(self,result,company,query,now):
        if result["schema_version"]!=1 or result["policy_version"]!=self.policy_version:raise ValueError("checkpoint version")
        if result["company"]!={"symbol":company.symbol,"issuer_id":company.issuer_id} or result["query"]!=normalized(asdict(query)):
            raise ValueError("checkpoint query/identity mismatch")
        completed=datetime.fromisoformat(result["completed_at"])
        if not aware(completed) or completed>now:raise ValueError("future/naive checkpoint")
        attempts=result["attempts"]
        if not isinstance(attempts,list):raise ValueError("invalid attempts")
        from .providers import Status
        if [a["source"] for a in attempts]!=[s.value for s in SOURCE_ORDER[:len(attempts)]]:raise ValueError("source order")
        if len(attempts)>len(SOURCE_ORDER):raise ValueError("extra source")
        for attempt in attempts:
            Status(attempt["status"])
            stamp=datetime.fromisoformat(attempt["attempted_at"])
            if not aware(stamp) or stamp>completed:raise ValueError("attempt chronology")
        if result["fact"] is not None:
            if result["state"] not in ("collected","stale_data") or not attempts or attempts[-1]["status"]!="valid" or any(a["status"]=="valid" for a in attempts[:-1]):
                raise ValueError("invalid success trail")
            fact=decode_fact(result["fact"])
            cutoff=datetime.fromisoformat(result["as_of"])
            if cutoff>completed or query.at(cutoff).rejection(fact) or fact.source.value!=attempts[-1]["source"]:
                raise ValueError("invalid accepted fact")
            observed=fact.data_observed_at or fact.retrieved_at
            if result["state"]=="stale_data":return now-completed<self.retry_delay
            return now-observed<self.fact_ttl
        if result["state"] not in ("pending_data","collection_error") or any(a["status"]=="valid" for a in attempts):
            raise ValueError("invalid pending trail")
        return now-completed<self.retry_delay

    def run(self,companies,*,max_new_fields=None):
        companies=tuple(companies);now=self.clock()
        if not aware(now) or (max_new_fields is not None and (type(max_new_fields) is not int or max_new_fields<0)):
            raise ValueError("aware clock and nonnegative work limit required")
        if len({c.issuer_id for c in companies})!=len(companies) or len({c.symbol for c in companies})!=len(companies):
            raise ValueError("duplicate issuer or symbol in company sample")
        for company in companies:
            for query in company.queries:query.at(now)
        owner=self.store.acquire(now,self.lease_ttl)
        output=[];new=0;reused=0;events_start=len(self.store.events)
        try:
            for company in companies:
                fields=[];resolver=None
                for query in company.queries:
                    now=self.clock();self.store.renew(owner,now,self.lease_ttl)
                    if company.scope_status=="out_of_scope":
                        fields.append({"query":normalized(asdict(query)),"state":"out_of_scope","fact":None,"attempts":[],"reused":False})
                        continue
                    key=self.key(company,query);result=self.store.read(key)
                    if result is not None:
                        try:
                            if not self._validate(result,company,query,now):result=None
                        except (ValueError,KeyError,TypeError,ArithmeticError):
                            self.store.events.append({"key":key,"event":"invalid_checkpoint_semantics"});result=None
                    if result is not None:
                        reused+=1;fields.append({**result,"reused":True});continue
                    if max_new_fields is not None and new>=max_new_fields:
                        fields.append({"query":normalized(asdict(query)),"state":"not_started","fact":None,"attempts":[],"reused":False});continue
                    result={"schema_version":1,"policy_version":self.policy_version,
                            "company":{"symbol":company.symbol,"issuer_id":company.issuer_id},
                            "query":normalized(asdict(query)),"fact":None,"attempts":[],"as_of":None}
                    try:
                        if resolver is None:resolver=self.factory(company)
                        resolution=resolver.resolve_current(query)
                        result.update(state="collected" if resolution.fact is not None else "pending_data",
                                      fact=normalized(asdict(resolution.fact)) if resolution.fact is not None else None,
                                      attempts=normalized([asdict(a) for a in resolution.attempts]),
                                      as_of=resolution.as_of.isoformat() if resolution.as_of is not None else None)
                    except Exception as exc:
                        # No exception message or credential-bearing object is persisted.
                        result.update(state="collection_error",error_type=type(exc).__name__)
                        if isinstance(exc,ProviderFailure):
                            result.update(failure_status=exc.status.value,
                                          failure_reason=exc.reason.value if exc.reason else None,
                                          http_status=exc.http_status)
                    now=self.clock();result["completed_at"]=now.isoformat()
                    try:
                        fresh=self._validate(result,company,query,now)
                        if not fresh and result["fact"] is not None:result["state"]="stale_data"
                    except (ValueError,KeyError,TypeError,ArithmeticError):
                        result.update(state="collection_error",error_type="InvalidResolution",fact=None,attempts=[],as_of=None)
                    self.store.write(key,result,owner,now,self.lease_ttl);new+=1
                    fields.append({**result,"reused":False})
                states=Counter(f["state"] for f in fields)
                readiness=("out_of_scope" if company.scope_status=="out_of_scope" else
                           "data_complete_scope_pending" if states["collected"]==len(fields) else "pending_fields_and_scope")
                output.append({"symbol":company.symbol,"issuer_id":company.issuer_id,"scope_status":company.scope_status,
                               "scope_reason":company.scope_reason,"readiness":readiness,"fields":fields})
        finally:self.store.release(owner)
        counts=Counter(f["state"] for c in output for f in c["fields"])
        return {"schema_version":1,"policy_version":self.policy_version,"generated_at":self.clock().isoformat(),
                "companies":output,"summary":{"companies":len(output),"field_states":dict(counts),"new_fields":new,"reused_fields":reused},
                "checkpoint_events":self.store.events[events_start:],"investment_approved":False,
                "hundred_company_accepted":False,"active_universe_accepted":False}


def load_plan(payload):
    """Only explicit dates and exact supported definitions; no fiscal inference."""
    from datetime import date
    from .companyfacts import TAGS
    if not isinstance(payload,dict) or payload.get("schema_version")!=1 or not isinstance(payload.get("companies"),list) or not payload["companies"]:
        raise ValueError("nonempty version 1 company plan required")
    companies=[]
    for row in payload["companies"]:
        end=date.fromisoformat(row["period_end"])
        start=date.fromisoformat(row["period_start"]) if row.get("period_start") else None
        fields=row["fields"]
        if not isinstance(fields,list) or not fields:raise ValueError("explicit field list required")
        queries=[]
        for field in fields:
            if field not in TAGS:raise ValueError("unsupported exact field")
            tag,instant=TAGS[field]
            if not instant and start is None:raise ValueError("explicit duration start required")
            queries.append(FactQuery(row["issuer_id"],field,None if instant else start,end,
                                     row.get("currency","USD"),"currency","us-gaap:"+tag))
        companies.append(CompanyTask(row["symbol"],row["issuer_id"],tuple(queries),
                         row.get("scope_status","pending_scope"),
                         row.get("scope_reason","listing_and_legal_type_not_accepted")))
    return tuple(companies)
