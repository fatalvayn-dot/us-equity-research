"""Nasdaq Trader membership evidence; candidates are not a final active universe."""
import re
from collections import Counter
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from enum import Enum

from .models import Exchange, aware
from .providers import ProviderFailure, Status
from .sec import DIRECTORY_URL, DirectorySnapshot
from .transport import Response

DIRECTORY_URLS = {
    name: f"https://ftp.nasdaqtrader.com/SymbolDirectory/{name}.txt"
    for name in ("nasdaqlisted", "otherlisted")
}
DIRECTORY_ENDPOINTS = {
    name: (url, f"https://www.nasdaqtrader.com/dynamic/SymDir/{name}.txt")
    for name,url in DIRECTORY_URLS.items()
}


@dataclass(frozen=True)
class ListingRow:
    symbol: str
    aliases: tuple[str, ...]
    name: str
    exchange: Exchange | None
    exchange_code: str
    etf: str
    test_issue: str
    nextshares: str
    financial_status: str | None


@dataclass(frozen=True)
class ListingSnapshot:
    name: str
    rows: tuple[ListingRow, ...]
    source_url: str
    raw_sha256: str
    retrieved_at: datetime
    created_on: date
    creation_label: str


class UniverseStatus(str, Enum):
    CANDIDATE = "common_stock_candidate"
    EXCLUDED_INSTRUMENT = "excluded_instrument"
    OUT_OF_SCOPE_EXCHANGE = "out_of_scope_exchange"
    TEST_ISSUE = "test_issue"
    PENDING_CLASSIFICATION = "pending_classification"
    PENDING_IDENTITY = "pending_identity"
    PENDING_LISTING = "pending_listing_evidence"


@dataclass(frozen=True)
class ClassifiedListing:
    listing: ListingRow
    source_url: str
    raw_sha256: str
    status: UniverseStatus
    reason: str
    issuer_id: str | None = None


def parse_directory(response: Response, name: str) -> ListingSnapshot:
    if name not in DIRECTORY_URLS or response.url not in DIRECTORY_ENDPOINTS[name] or not aware(response.retrieved_at):
        raise ProviderFailure(Status.INVALID_DATA)
    try:
        lines = response.body.decode("utf-8-sig").splitlines()
        if len(lines) < 3:
            raise ValueError("empty or truncated directory")
        headers = [h.strip().lower() for h in lines[0].split("|")]
        required = {"security name", "test issue", "etf"}
        required |= ({"symbol", "market category", "financial status", "nextshares"}
                     if name == "nasdaqlisted" else {"act symbol", "exchange", "cqs symbol", "nasdaq symbol"})
        if len(set(headers)) != len(headers) or not required.issubset(headers):
            raise ValueError("invalid schema")
        footer = lines[-1].split("|")
        match = re.fullmatch(r"File Creation Time: ([0-9]{8})([0-9]{2}):?([0-9]{2})", footer[0])
        # Actual official otherlisted distribution retains the seven-field
        # legacy footer although data/header rows have eight fields. Accept
        # only this observed empty-tail variant; never relax data row widths.
        footer_widths={len(headers)}
        if name=="otherlisted" and len(headers)==8:footer_widths.add(7)
        if not match or len(footer) not in footer_widths or any(footer[1:]):
            raise ValueError("missing or malformed creation footer")
        # No timezone is declared in this text field. Preserve it verbatim and
        # use only the calendar date for freshness, never invent a UTC instant.
        created = datetime.strptime("".join(match.groups()), "%m%d%Y%H%M")
        rows, seen = [], set()
        for line in lines[1:-1]:
            values = line.split("|")
            if len(values) != len(headers):
                raise ValueError("invalid row width")
            data = dict(zip(headers, values))
            if name == "nasdaqlisted":
                symbol = data["symbol"]
                exchange = Exchange.NASDAQ
                code = data["market category"]
                aliases = (symbol,)
            else:
                symbol = data["act symbol"]
                code = data["exchange"]
                exchange = {"N": Exchange.NYSE, "A": Exchange.NYSE_AMERICAN}.get(code)
                aliases = tuple(dict.fromkeys(filter(None, (symbol, data["cqs symbol"], data["nasdaq symbol"])) ))
            if not symbol or symbol in seen or not data["security name"].strip():
                raise ValueError("empty or duplicate identity")
            seen.add(symbol)
            rows.append(ListingRow(symbol, aliases, data["security name"], exchange, code,
                                   data["etf"], data["test issue"], data.get("nextshares", "N"),
                                   data.get("financial status")))
        if not rows:
            raise ValueError("directory has no rows")
        return ListingSnapshot(name, tuple(rows), response.url, response.sha256, response.retrieved_at,
                               created.date(), footer[0])
    except (UnicodeError, ValueError, KeyError):
        raise ProviderFailure(Status.INVALID_DATA) from None


def instrument_status(row: ListingRow) -> tuple[UniverseStatus, str]:
    if row.test_issue not in ("Y", "N") or row.etf not in ("Y", "N") or row.nextshares not in ("Y", "N"):
        return UniverseStatus.PENDING_LISTING, "unknown_boolean_flag"
    if row.test_issue == "Y":
        return UniverseStatus.TEST_ISSUE, "test_issue_flag"
    if row.exchange is None:
        return UniverseStatus.OUT_OF_SCOPE_EXCHANGE, "listing_exchange_outside_scope"
    if row.etf == "Y" or row.nextshares == "Y":
        return UniverseStatus.EXCLUDED_INSTRUMENT, "etf_or_nextshares_flag"
    if row.exchange is Exchange.NASDAQ and row.exchange_code not in ("Q", "G", "S"):
        return UniverseStatus.PENDING_LISTING, "unknown_market_category"
    if row.financial_status is not None and row.financial_status not in ("N", "D", "E", "Q", "G", "H", "J", "K"):
        return UniverseStatus.PENDING_LISTING, "unknown_financial_status"
    description = row.name.rsplit(" - ", 1)[-1].lower()
    patterns = (
        (r"\b(preferred|preference)\s+(stock|shares?)\b", "preferred"),
        (r"\b(depositary|depository)\b|\b(adrs?|adss?)\b", "depositary_receipt"),
        (r"\bwarrants?\b", "warrant"),
        (r"\brights?\b", "right"),
        (r"\bunits?\b", "unit"),
        (r"\b(notes?|bonds?|debentures?)\b", "debt"),
        (r"\bclosed[- ]end\s+fund\b|\b(exchange[- ]traded fund|etf)\b", "fund"),
    )
    for pattern, reason in patterns:
        if re.search(pattern, description):
            return UniverseStatus.EXCLUDED_INSTRUMENT, reason
    if re.search(r"\bfund\b", row.name, re.IGNORECASE):
        return UniverseStatus.PENDING_CLASSIFICATION, "fund_word_requires_legal_type_check"
    if re.search(r"\b(common\s+(stock|shares?)|ordinary\s+shares?)\b", description):
        return UniverseStatus.CANDIDATE, "explicit_common_or_ordinary_share_description"
    return UniverseStatus.PENDING_CLASSIFICATION, "no_explicit_common_share_description"


def build_universe(snapshots: tuple[ListingSnapshot, ...], identity: DirectorySnapshot, *,
                   as_of: datetime, max_age=timedelta(days=4)) -> tuple[ClassifiedListing, ...]:
    """Exhaustively partition raw rows; never convert uncertainty to approval."""
    if not aware(as_of) or {s.name for s in snapshots} != set(DIRECTORY_URLS) or len(snapshots) != 2:
        raise ValueError("both distinct directories and aware cutoff required")
    if max_age < timedelta(0) or identity.source_url != DIRECTORY_URL or not aware(identity.retrieved_at):
        raise ValueError("invalid freshness or identity source")
    if identity.retrieved_at > as_of or as_of - identity.retrieved_at > max_age:
        raise ValueError("stale or future identity snapshot")
    identity_index = {entry.ticker: entry for entry in identity.entries}
    if len(identity_index) != len(identity.entries):
        raise ValueError("ambiguous SEC symbols")
    aliases = Counter(alias for s in snapshots for row in s.rows for alias in set(row.aliases))
    result = []
    labels = {Exchange.NASDAQ: {"Nasdaq"}, Exchange.NYSE: {"NYSE"},
              Exchange.NYSE_AMERICAN: {"NYSE American", "NYSE MKT"}}
    for snapshot in snapshots:
        age = as_of.date() - snapshot.created_on
        fresh = (snapshot.retrieved_at <= as_of and as_of - snapshot.retrieved_at <= max_age
                 and timedelta(0) <= age <= max_age)
        for row in snapshot.rows:
            status, reason = instrument_status(row)
            cik = None
            if status is UniverseStatus.CANDIDATE:
                if not fresh:
                    status, reason = UniverseStatus.PENDING_LISTING, "stale_or_future_source"
                elif any(aliases[a] > 1 for a in row.aliases):
                    status, reason = UniverseStatus.PENDING_IDENTITY, "ambiguous_cross_directory_alias"
                else:
                    matches = [identity_index[a] for a in row.aliases if a in identity_index]
                    if not matches:
                        status, reason = UniverseStatus.PENDING_IDENTITY, "no_exact_sec_symbol_match"
                    elif len({m.issuer.cik for m in matches}) != 1:
                        status, reason = UniverseStatus.PENDING_IDENTITY, "conflicting_sec_issuers"
                    elif any(m.exchange_label not in labels[row.exchange] for m in matches):
                        status, reason = UniverseStatus.PENDING_IDENTITY, "exchange_disagreement"
                    else:
                        cik = matches[0].issuer.cik
            result.append(ClassifiedListing(row, snapshot.source_url, snapshot.raw_sha256, status, reason, cik))
    return tuple(result)


class NasdaqDirectories:
    def __init__(self, transport):
        self.transport = transport
        self.attempts = []

    def fetch(self) -> tuple[ListingSnapshot, ...]:
        snapshots=[]
        self.attempts=[]
        for name,urls in DIRECTORY_ENDPOINTS.items():
            failure=None
            for url in urls:
                try:
                    snapshot=parse_directory(self.transport.get(url),name)
                except ProviderFailure as exc:
                    failure=exc
                    self.attempts.append(dict(name=name,url=url,status=exc.status.value,
                        reason=exc.reason.value if exc.reason else None,http_status=exc.http_status))
                else:
                    self.attempts.append(dict(name=name,url=url,status="valid",sha256=snapshot.raw_sha256,
                        retrieved_at=snapshot.retrieved_at.isoformat()))
                    snapshots.append(snapshot)
                    break
            else:
                raise failure
        return tuple(snapshots)
