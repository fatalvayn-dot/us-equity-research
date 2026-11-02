"""SEC directory identity only; not instrument classification or financial data."""
from dataclasses import dataclass
from datetime import datetime

from .models import Issuer
from .providers import ProviderFailure, Status
from .transport import HttpTransport, Response, strict_json

DIRECTORY_URL = "https://www.sec.gov/files/company_tickers_exchange.json"


@dataclass(frozen=True)
class DirectoryEntry:
    issuer: Issuer
    ticker: str
    exchange_label: str | None


@dataclass(frozen=True)
class DirectorySnapshot:
    entries: tuple[DirectoryEntry, ...]
    source_url: str
    retrieved_at: datetime
    sha256: str

    def lookup(self, symbol: str, expected_cik: str | None = None) -> DirectoryEntry | None:
        if not isinstance(symbol, str) or not symbol.strip():
            raise ValueError("symbol required")
        # Preserve class punctuation: BRK.B must not silently match BRK-B.
        ticker = symbol.strip().upper()
        for entry in self.entries:
            if entry.ticker == ticker:
                if expected_cik is not None and entry.issuer.cik != expected_cik:
                    raise ProviderFailure(Status.SYMBOL_MISMATCH)
                return entry
        return None


def parse_directory(response: Response) -> DirectorySnapshot:
    if response.url != DIRECTORY_URL:
        raise ProviderFailure(Status.INVALID_DATA)
    payload = strict_json(response.body)
    try:
        fields, rows = payload["fields"], payload["data"]
        if (not isinstance(fields, list) or not all(isinstance(f, str) for f in fields)
                or len(set(fields)) != len(fields)
                or not {"cik", "name", "ticker", "exchange"}.issubset(fields)
                or not isinstance(rows, list) or not rows):
            raise ValueError("invalid directory schema")
        entries, seen = [], set()
        for row in rows:
            if not isinstance(row, list) or len(row) != len(fields):
                raise ValueError("invalid row width")
            data = dict(zip(fields, row))
            cik, name, symbol, exchange = (data[k] for k in ("cik", "name", "ticker", "exchange"))
            if type(cik) is not int or not 0 < cik < 10_000_000_000:
                raise ValueError("invalid CIK")
            if not isinstance(name, str) or not name.strip() or not isinstance(symbol, str) or not symbol.strip():
                raise ValueError("missing identity")
            ticker = symbol.strip().upper()
            if ticker in seen or (exchange is not None and not isinstance(exchange, str)):
                raise ValueError("ambiguous identity or exchange")
            seen.add(ticker)
            entries.append(DirectoryEntry(Issuer(str(cik).zfill(10), name.strip()), ticker, exchange))
    except (TypeError, KeyError, ValueError):
        raise ProviderFailure(Status.INVALID_DATA) from None
    return DirectorySnapshot(tuple(entries), response.url, response.retrieved_at, response.sha256)


class SecDirectory:
    def __init__(self, transport: HttpTransport):
        self.transport = transport

    def fetch(self) -> DirectorySnapshot:
        return parse_directory(self.transport.get(DIRECTORY_URL))
