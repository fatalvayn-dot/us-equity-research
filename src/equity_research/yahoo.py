"""Conservative Yahoo TotalAssets adapter; duration mappings are unsupported."""
import re
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from urllib.parse import quote, urlencode

from .models import Fact, Source, aware
from .providers import ProviderFailure, Status
from .sec import DIRECTORY_URL, DirectorySnapshot
from .transport import strict_json


def assets_url(symbol, year):
    if not isinstance(symbol, str) or not re.fullmatch(r"[A-Z0-9][A-Z0-9.\-^=]{0,19}",symbol):
        raise ValueError("explicit Yahoo symbol required; no punctuation aliasing")
    start=int(datetime(year-1,1,1,tzinfo=timezone.utc).timestamp())
    end=int(datetime(year+1,1,1,tzinfo=timezone.utc).timestamp())
    params=urlencode({"symbol":symbol,"type":"annualTotalAssets","period1":start,"period2":end})
    return "https://query1.finance.yahoo.com/ws/fundamentals-timeseries/v1/finance/timeseries/"+quote(symbol,safe="")+"?"+params


class YahooAssets:
    source = Source.YAHOO

    def __init__(self, transport, *, directory: DirectorySnapshot, symbol: str, clock=None,
                 ttl=timedelta(hours=6), identity_ttl=timedelta(days=1)):
        if ttl <= timedelta(0) or identity_ttl <= timedelta(0):
            raise ValueError("positive data and identity TTLs required")
        self.transport,self.directory,self.symbol=transport,directory,symbol
        self.clock=clock or (lambda:datetime.now(timezone.utc))
        self.ttl,self.identity_ttl=ttl,identity_ttl
        self.memory={}

    def _check(self, spec):
        if spec.field!="assets":
            raise ProviderFailure(Status.UNSUPPORTED_FIELD)
        if (spec.period_start is not None or spec.unit!="currency" or spec.currency is None
                or spec.accounting_definition!="us-gaap:Assets"):
            raise ProviderFailure(Status.INVALID_DATA)
        now=self.clock()
        if (self.directory.source_url!=DIRECTORY_URL or not aware(self.directory.retrieved_at)
                or not timedelta(0)<=now-self.directory.retrieved_at<=self.identity_ttl):
            raise ProviderFailure(Status.INVALID_DATA)
        entry=self.directory.lookup(self.symbol,expected_cik=spec.issuer_id)
        if entry is None:
            raise ProviderFailure(Status.SYMBOL_MISMATCH)

    def prepare(self, query):
        self._check(query)
        self.snapshot(query.period_end.year)

    def snapshot(self, year):
        url=assets_url(self.symbol,year)
        if url in self.memory:
            response,payload=self.memory[url]
            if timedelta(0)<=self.clock()-response.retrieved_at<self.ttl:
                return response,payload
        response=self.transport.get(url)
        if response.url!=url or not aware(response.retrieved_at):
            raise ProviderFailure(Status.INVALID_DATA)
        payload=strict_json(response.body)
        if not isinstance(payload,dict) or not isinstance(payload.get("timeseries"),dict):
            raise ProviderFailure(Status.INVALID_DATA)
        data=payload["timeseries"]
        if data.get("error"):
            error=data["error"]
            code=str(error.get("code","")).lower() if isinstance(error,dict) else ""
            status=Status.ACCESS_DENIED if code in ("unauthorized","forbidden") else Status.RATE_LIMIT if code in ("too many requests","ratelimit") else Status.API_ERROR
            raise ProviderFailure(status)
        if not isinstance(data.get("result"),list) or not data["result"]:
            # Empty or absent result does not establish successful field absence.
            raise ProviderFailure(Status.INVALID_DATA)
        self.memory[url]=(response,data["result"])
        return self.memory[url]

    def fetch(self, request):
        self._check(request)
        response,series=self.snapshot(request.period_end.year)
        if response.retrieved_at>request.as_of:
            raise ProviderFailure(Status.INVALID_DATA)
        values=[];same_month=False
        try:
            for item in series:
                if not isinstance(item,dict) or not isinstance(item.get("meta"),dict):
                    raise ValueError("invalid series")
                meta=item["meta"]
                if meta.get("symbol")!=[self.symbol]:
                    raise ProviderFailure(Status.SYMBOL_MISMATCH)
                if meta.get("type")!=["annualTotalAssets"]:
                    raise ValueError("unexpected financial concept")
                rows=item.get("annualTotalAssets")
                if not isinstance(rows,list):
                    raise ValueError("unconfirmed field absence")
                for row in rows:
                    end=date.fromisoformat(row["asOfDate"])
                    if end!=request.period_end:
                        same_month |= (end.year,end.month)==(request.period_end.year,request.period_end.month)
                        continue
                    if row.get("periodType")!="12M" or row.get("currencyCode")!=request.currency:
                        raise ValueError("period/currency mismatch")
                    value=row["reportedValue"]["raw"]
                    if type(value) not in (int,Decimal):
                        raise ValueError("invalid financial number")
                    value=Decimal(value)
                    if not value.is_finite():
                        raise ValueError("nonfinite financial number")
                    values.append(value)
        except (ValueError,KeyError,TypeError):
            raise ProviderFailure(Status.INVALID_DATA) from None
        if not values:
            if same_month:
                raise ProviderFailure(Status.PERIOD_MISMATCH)
            return None
        if len(set(values))!=1:
            raise ProviderFailure(Status.INVALID_DATA)
        return Fact(request.issuer_id,"assets",values[0],Source.YAHOO,None,request.period_end,
                    request.currency,"currency",response.retrieved_at,response.retrieved_at,
                    "us-gaap:Assets",response.url,raw_sha256=response.sha256,
                    source_field="annualTotalAssets",identity_evidence_url=self.directory.source_url,
                    identity_evidence_sha256=self.directory.sha256,
                    identity_observed_at=self.directory.retrieved_at)
