"""Nasdaq instant balance-sheet facts with separate explicit unit evidence."""
import re
from datetime import datetime,timedelta,timezone
from decimal import Decimal
from html.parser import HTMLParser

from .models import Fact,Source,aware
from .providers import ProviderFailure,Status
from .sec import DIRECTORY_URL
from .transport import strict_json

LABELS={"assets":("Total Assets","us-gaap:Assets"),"liabilities":("Total Liabilities","us-gaap:Liabilities")}


def financial_urls(symbol):
    if not isinstance(symbol,str) or not re.fullmatch(r"[A-Z0-9][A-Z0-9.\-]{0,19}",symbol):
        raise ValueError("explicit Nasdaq symbol required")
    return (f"https://api.nasdaq.com/api/company/{symbol}/financials?frequency=1",
            f"https://www.nasdaq.com/market-activity/stocks/{symbol.lower()}/financials")


class UnitPage(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True);self.text=[];self.title=[];self.ignored=0;self.heading=0
    def handle_starttag(self,tag,attrs):
        if tag in ("script","style"):self.ignored+=1
        if tag in ("title","h1"):self.heading+=1
    def handle_endtag(self,tag):
        if tag in ("script","style"):self.ignored=max(0,self.ignored-1)
        if tag in ("title","h1"):self.heading=max(0,self.heading-1)
    def handle_data(self,data):
        if not self.ignored:
            self.text.append(data)
            if self.heading:self.title.append(data)


def parse_units(response,symbol):
    if response.url!=financial_urls(symbol)[1] or not aware(response.retrieved_at):
        raise ProviderFailure(Status.INVALID_DATA)
    try:
        parser=UnitPage();parser.feed(response.body.decode("utf-8"))
        title=" ".join(parser.title)
        if not re.search(r"(?<![A-Z0-9])"+re.escape(symbol)+r"(?![A-Z0-9])",title) or "financial" not in title.lower():
            raise ProviderFailure(Status.SYMBOL_MISMATCH)
        labels=set(re.findall(r"\bIn\s+([A-Z]{3})\s+(Thousands|Millions|Billions)\b"," ".join(parser.text)))
        if len(labels)!=1:raise ValueError("absent or ambiguous monetary unit")
        currency,scale=labels.pop()
        return currency,{"Thousands":Decimal(1000),"Millions":Decimal(1000000),"Billions":Decimal(1000000000)}[scale]
    except (ValueError,UnicodeError):raise ProviderFailure(Status.INVALID_DATA) from None


def monetary_value(raw,multiplier):
    if raw is None or raw in ("","--","—","N/A"):return None
    if not isinstance(raw,str):raise ProviderFailure(Status.INVALID_DATA)
    value=raw.strip();negative=value.startswith("(") and value.endswith(")")
    if negative:value=value[1:-1]
    if not re.fullmatch(r"-?\$?(?:[0-9]+|[1-9][0-9]{0,2}(?:,[0-9]{3})+)(?:\.[0-9]+)?",value):
        raise ProviderFailure(Status.INVALID_DATA)
    number=Decimal(value.replace("$","").replace(",",""))
    if negative:
        if number<0:raise ProviderFailure(Status.INVALID_DATA)
        number=-number
    return number*multiplier


class NasdaqFinancials:
    source=Source.NASDAQ

    def __init__(self,transport,*,directory,symbol,clock=None,ttl=timedelta(hours=6),identity_ttl=timedelta(days=1)):
        if ttl<=timedelta(0) or identity_ttl<=timedelta(0):raise ValueError("positive TTL required")
        financial_urls(symbol)
        self.transport,self.directory,self.symbol=transport,directory,symbol
        self.clock=clock or (lambda:datetime.now(timezone.utc))
        self.ttl,self.identity_ttl=ttl,identity_ttl;self.memory=None

    def _check(self,spec):
        if spec.field not in LABELS:raise ProviderFailure(Status.UNSUPPORTED_FIELD)
        if (spec.period_start is not None or spec.unit!="currency" or spec.currency is None or spec.accounting_definition!=LABELS[spec.field][1]):
            raise ProviderFailure(Status.INVALID_DATA)
        if (self.directory.source_url!=DIRECTORY_URL or not aware(self.directory.retrieved_at)
                or not timedelta(0)<=self.clock()-self.directory.retrieved_at<=self.identity_ttl):
            raise ProviderFailure(Status.INVALID_DATA)
        if self.directory.lookup(self.symbol,expected_cik=spec.issuer_id) is None:
            raise ProviderFailure(Status.SYMBOL_MISMATCH)

    def prepare(self,spec):self._check(spec);self.snapshot()

    def snapshot(self):
        if self.memory is not None:
            data,units,currency,scale,payload=self.memory
            if all(timedelta(0)<=self.clock()-r.retrieved_at<self.ttl for r in (data,units)):
                return self.memory
        data_url,unit_url=financial_urls(self.symbol)
        units=self.transport.get(unit_url);currency,scale=parse_units(units,self.symbol)
        data=self.transport.get(data_url)
        if data.url!=data_url or not aware(data.retrieved_at):raise ProviderFailure(Status.INVALID_DATA)
        payload=strict_json(data.body)
        try:
            code=payload["status"]["rCode"]
            if code!=200:raise ProviderFailure(Status.RATE_LIMIT if code==429 else Status.ACCESS_DENIED if code in (401,403) else Status.API_ERROR)
            payload=payload["data"]
            if payload["symbol"]!=self.symbol:raise ProviderFailure(Status.SYMBOL_MISMATCH)
            if not isinstance(payload.get("balanceSheetTable"),dict):raise ProviderFailure(Status.UNSUPPORTED_FIELD)
        except (KeyError,TypeError):raise ProviderFailure(Status.INVALID_DATA) from None
        self.memory=(data,units,currency,scale,payload)
        return self.memory

    def fetch(self,request):
        self._check(request)
        data,units,currency,multiplier,payload=self.snapshot()
        completed=max(data.retrieved_at,units.retrieved_at)
        if completed>request.as_of or currency!=request.currency:raise ProviderFailure(Status.INVALID_DATA)
        try:
            table=payload["balanceSheetTable"];headers=table["headers"];rows=table["rows"]
            if not isinstance(headers,dict) or not isinstance(rows,list) or headers.get("value1")!="Period Ending:":
                raise ValueError("invalid balance sheet schema")
            dates={}
            for column,label in headers.items():
                if column=="value1":continue
                if not re.fullmatch(r"value[0-9]+",column):raise ValueError("unknown table column")
                end=datetime.strptime(label,"%m/%d/%Y").date()
                if end in dates.values():raise ValueError("ambiguous reporting columns")
                dates[column]=end
            columns=[c for c,end in dates.items() if end==request.period_end]
            if not columns:
                if any((d.year,d.month)==(request.period_end.year,request.period_end.month) for d in dates.values()):
                    raise ProviderFailure(Status.PERIOD_MISMATCH)
                return None
            values=[]
            for row in rows:
                if not isinstance(row,dict):raise ValueError("invalid row")
                if row.get("value1")==LABELS[request.field][0]:
                    if columns[0] not in row:raise ValueError("missing table cell")
                    values.append(monetary_value(row[columns[0]],multiplier))
            if not values:return None
            if len(values)!=1:raise ValueError("ambiguous financial row")
            if values[0] is None:return None
            return Fact(request.issuer_id,request.field,values[0],Source.NASDAQ,None,request.period_end,currency,"currency",
                        completed,completed,request.accounting_definition,data.url,raw_sha256=data.sha256,
                        source_field=LABELS[request.field][0],identity_evidence_url=self.directory.source_url,
                        identity_evidence_sha256=self.directory.sha256,identity_observed_at=self.directory.retrieved_at,
                        unit_evidence_url=units.url,unit_evidence_sha256=units.sha256,unit_observed_at=units.retrieved_at,
                        data_observed_at=data.retrieved_at,source_multiplier=multiplier)
        except (KeyError,ValueError,TypeError):raise ProviderFailure(Status.INVALID_DATA) from None
