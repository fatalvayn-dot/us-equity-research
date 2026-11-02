"""Finnhub reported-financial contracts; require explicit units and existing key.

No live Finnhub financial response has yet been accepted. Unsupported report
shapes or missing unit evidence fail closed rather than assuming dollars.
"""
import os
import re
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal
from urllib.parse import urlencode

from .companyfacts import TAGS, FORMS
from .models import Fact, Source, aware
from .providers import ProviderFailure, Status
from .transport import HttpTransport, strict_json

BASE_URL="https://finnhub.io/api/v1/stock/financials-reported"
SECTIONS={"assets":"bs","liabilities":"bs","revenue":"ic","net_income":"ic",
          "operating_cash_flow":"cf","capital_expenditure":"cf"}


@dataclass(frozen=True)
class FinnhubConfig:
    api_key: str | None = field(default=None,repr=False)

    def __post_init__(self):
        if self.api_key is not None and (not isinstance(self.api_key,str) or not self.api_key or
                any(ord(c)<33 or ord(c)>126 for c in self.api_key)):
            raise ValueError("invalid Finnhub credential configuration")

    @property
    def configured(self):return self.api_key is not None

    @classmethod
    def from_environment(cls,environ=None):
        env=os.environ if environ is None else environ
        primary,alternate=env.get("FINNHUB_API_KEY"),env.get("FINNHUB_TOKEN")
        if primary and alternate and primary!=alternate:
            raise ValueError("conflicting Finnhub credential settings")
        return cls(primary or alternate or None)


def canonical_cik(value):
    text=str(value) if type(value) is int else value
    if not isinstance(text,str) or not re.fullmatch(r"[0-9]{1,10}",text) or int(text)==0:
        raise ValueError("explicit canonical issuer identity required")
    return text.zfill(10)


def reported_url(cik,end,frequency):
    if frequency not in ("annual","quarterly") or canonical_cik(cik)!=cik or type(end) is not date:
        raise ValueError("exact CIK/date/frequency required")
    return BASE_URL+"?"+urlencode({"cik":cik,"freq":frequency,"from":end.isoformat(),"to":end.isoformat()})


def report_date(value):
    if not isinstance(value,str):raise ValueError("explicit report date required")
    return datetime.fromisoformat(value.replace("Z","+00:00")).date()


class FinnhubReported:
    source=Source.FINNHUB

    def __init__(self,config:FinnhubConfig,*,user_agent="US Equity Research",frequency="annual",transport=None,
                 ttl=timedelta(hours=6),clock=None):
        if frequency not in ("annual","quarterly") or ttl<=timedelta(0):raise ValueError("invalid frequency or TTL")
        self.config,self.frequency,self.ttl=config,frequency,ttl
        self.clock=clock or (lambda:datetime.now(timezone.utc))
        self.transport=transport
        if self.transport is None and config.configured:
            self.transport=HttpTransport(user_agent=user_agent,allowed_hosts={"finnhub.io"},
                                        auth_headers={"X-Finnhub-Token":config.api_key})
        self.memory={}

    def _check(self,spec):
        if not self.config.configured:raise ProviderFailure(Status.NOT_CONFIGURED)
        if spec.field not in TAGS or spec.field not in SECTIONS:raise ProviderFailure(Status.UNSUPPORTED_FIELD)
        tag,instant=TAGS[spec.field]
        if (spec.accounting_definition!="us-gaap:"+tag or spec.unit!="currency" or spec.currency is None
                or instant!=(spec.period_start is None)):
            raise ProviderFailure(Status.INVALID_DATA)
        if not instant:
            days=(spec.period_end-spec.period_start).days
            if not (330<=days<=400 if self.frequency=="annual" else 60<=days<=110):
                raise ProviderFailure(Status.UNSUPPORTED_FIELD)

    def prepare(self,query):
        self._check(query);self.snapshot(query.issuer_id,query.period_end)

    def snapshot(self,cik,end):
        if not self.config.configured:raise ProviderFailure(Status.NOT_CONFIGURED)
        url=reported_url(cik,end,self.frequency)
        if url in self.memory:
            response,payload=self.memory[url]
            if timedelta(0)<=self.clock()-response.retrieved_at<self.ttl:return response,payload
        response=self.transport.get(url)
        if response.url!=url or not aware(response.retrieved_at):raise ProviderFailure(Status.INVALID_DATA)
        payload=strict_json(response.body)
        try:
            if not isinstance(payload,dict):raise ValueError("invalid response")
            if payload.get("error"):
                message=str(payload["error"]).lower()
                status=(Status.RATE_LIMIT if any(s in message for s in ("rate limit","api limit","too many")) else
                        Status.ACCESS_DENIED if any(s in message for s in ("access","permission","api key","forbidden","unauthorized","premium")) else Status.API_ERROR)
                raise ProviderFailure(status)
            if canonical_cik(payload["cik"])!=cik:raise ProviderFailure(Status.SYMBOL_MISMATCH)
            if not isinstance(payload.get("data"),list):raise ValueError("unconfirmed report absence")
            for filing in payload["data"]:
                if not isinstance(filing,dict):raise ValueError("invalid report")
                if canonical_cik(filing["cik"])!=cik:raise ProviderFailure(Status.SYMBOL_MISMATCH)
        except (KeyError,ValueError,TypeError):raise ProviderFailure(Status.INVALID_DATA) from None
        self.memory[url]=(response,payload)
        return response,payload

    def fetch(self,request):
        self._check(request)
        response,payload=self.snapshot(request.issuer_id,request.period_end)
        if response.retrieved_at>request.as_of:raise ProviderFailure(Status.INVALID_DATA)
        tag,instant=TAGS[request.field];section=SECTIONS[request.field]
        matches=[]
        try:
            for filing in payload["data"]:
                end=report_date(filing["endDate"])
                if end!=request.period_end or filing.get("form") not in FORMS:continue
                if not instant and report_date(filing["startDate"])!=request.period_start:continue
                filed=report_date(filing["filedDate"])
                # Date-only API evidence gets the same conservative availability
                # rule as SEC. acceptedDate is not guessed to be UTC.
                available=datetime.combine(filed+timedelta(days=1),time(5),timezone.utc)
                if available>min(request.as_of,response.retrieved_at):continue
                report=filing["report"]
                if not isinstance(report,dict):raise ValueError("invalid statement map")
                if section not in report:raise ProviderFailure(Status.UNSUPPORTED_FIELD)
                rows=report[section]
                # Legacy dict-only values have no per-concept currency/units.
                if not isinstance(rows,list):raise ProviderFailure(Status.UNSUPPORTED_FIELD)
                for row in rows:
                    if not isinstance(row,dict):raise ValueError("invalid statement row")
                    concept=row.get("concept")
                    if concept not in ("us-gaap_"+tag,"us-gaap:"+tag):continue
                    if any(row.get(k) for k in ("dimensions","segment","context")):
                        raise ValueError("unverified consolidated context")
                    unit=row.get("unit")
                    if not isinstance(unit,str) or unit.upper()!=request.currency or row.get("scale",0)!=0:
                        raise ValueError("unverified units or scale")
                    value=row["value"]
                    if type(value) not in (int,Decimal):raise ValueError("invalid numeric fact")
                    fact=Fact(request.issuer_id,request.field,Decimal(value),Source.FINNHUB,request.period_start,end,
                              request.currency,"currency",response.retrieved_at,available,request.accounting_definition,
                              response.url,filing_accession=filing["accessNumber"],filed_on=filed,
                              raw_sha256=response.sha256,source_field=concept)
                    matches.append(fact)
        except (KeyError,TypeError,ValueError,OverflowError):raise ProviderFailure(Status.INVALID_DATA) from None
        if not matches:return None
        latest=max(f.filed_on for f in matches);matches=[f for f in matches if f.filed_on==latest]
        if len({f.value for f in matches})!=1:raise ProviderFailure(Status.INVALID_DATA)
        return max(matches,key=lambda f:f.filing_accession)
