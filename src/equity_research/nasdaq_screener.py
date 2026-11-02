"""Public Nasdaq discovery fallback. No ETF, active-status or type inference."""
from dataclasses import dataclass
from urllib.parse import urlencode

from .providers import ProviderFailure, Status
from .transport import Response, strict_json

BASE_URL = "https://api.nasdaq.com/api/screener/stocks"


@dataclass(frozen=True)
class DiscoveryRecord:
    symbol: str
    name: str
    raw_symbol: str


@dataclass(frozen=True)
class ScreenerPage:
    response: Response
    records: tuple[DiscoveryRecord, ...]
    total_records: int
    source_asof_label: str | None


@dataclass(frozen=True)
class DiscoverySnapshot:
    records: tuple[DiscoveryRecord, ...]
    pages: tuple[ScreenerPage, ...]
    source_asof_label: str | None
    # Intentionally no active/common security model here. Missing metadata
    # must be corroborated before these records enter the research universe.


def screener_url(limit: int, offset: int) -> str:
    if type(limit) is not int or not 1 <= limit <= 10000 or type(offset) is not int or offset < 0:
        raise ValueError("bounded positive page limit and nonnegative offset required")
    return BASE_URL + "?" + urlencode({"tableonly": "true", "limit": limit, "offset": offset})


def parse_page(response: Response, *, limit: int, offset: int) -> ScreenerPage:
    if response.url != screener_url(limit, offset):
        raise ProviderFailure(Status.INVALID_DATA)
    payload = strict_json(response.body)
    try:
        status = payload["status"]["rCode"]
        if status != 200:
            raise ProviderFailure(Status.RATE_LIMIT if status == 429 else Status.ACCESS_DENIED if status in (401,403) else Status.API_ERROR)
        data = payload["data"]
        total, rows = data["totalrecords"], data["table"]["rows"]
        label = data.get("asof")
        if (type(total) is not int or total <= 0 or not isinstance(rows, list) or not rows
                or len(rows) > min(limit, total) or (label is not None and not isinstance(label, str))):
            raise ValueError("invalid or empty screener page")
        records, symbols = [], set()
        for row in rows:
            raw_symbol, name = row["symbol"], row["name"]
            if not isinstance(raw_symbol,str):
                raise ValueError("invalid symbol type")
            # Nasdaq currently pads two symbols with ASCII spaces. Retain the
            # original bytes in evidence and raw_symbol; trim only surrounding
            # ASCII whitespace, never class punctuation or internal characters.
            symbol=raw_symbol.strip(" \t\r\n")
            if (not symbol or not isinstance(name, str) or not name.strip() or symbol in symbols):
                raise ValueError("invalid or duplicate symbol")
            symbols.add(symbol)
            records.append(DiscoveryRecord(symbol, name, raw_symbol))
        return ScreenerPage(response, tuple(records), total, label)
    except (KeyError, TypeError, ValueError):
        raise ProviderFailure(Status.INVALID_DATA) from None


class NasdaqScreener:
    def __init__(self, transport, *, page_size=1000, max_pages=20, max_records=20000):
        screener_url(page_size, 0)
        if type(max_pages) is not int or max_pages <= 0 or type(max_records) is not int or max_records <= 0:
            raise ValueError("positive collection bounds required")
        self.transport, self.page_size = transport, page_size
        self.max_pages, self.max_records = max_pages, max_records

    def fetch(self) -> DiscoverySnapshot:
        records, pages, seen = [], [], set()
        total, label = None, None
        for _ in range(self.max_pages):
            offset = len(records)
            page = parse_page(self.transport.get(screener_url(self.page_size, offset)),limit=self.page_size,offset=offset)
            if total is None:
                total, label = page.total_records, page.source_asof_label
                if total > self.max_records:
                    raise ProviderFailure(Status.INVALID_DATA)
            elif (total, label) != (page.total_records, page.source_asof_label):
                raise ProviderFailure(Status.INVALID_DATA)
            for record in page.records:
                if record.symbol in seen:
                    raise ProviderFailure(Status.INVALID_DATA)
                seen.add(record.symbol)
            records.extend(page.records)
            pages.append(page)
            if len(records) == total:
                return DiscoverySnapshot(tuple(records), tuple(pages), label)
            if len(records) > total:
                raise ProviderFailure(Status.INVALID_DATA)
        raise ProviderFailure(Status.INVALID_DATA)
