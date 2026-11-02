"""Immutable identity, provenance and point-in-time financial contracts."""
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from enum import Enum
import re


class Source(str, Enum):
    YAHOO = "Yahoo"
    SEC = "SEC"
    NASDAQ = "Nasdaq"
    FINNHUB = "Finnhub"


SOURCE_ORDER = tuple(Source)


class Exchange(str, Enum):
    NYSE = "NYSE"
    NASDAQ = "NASDAQ"
    NYSE_AMERICAN = "NYSE_AMERICAN"


class SecurityType(str, Enum):
    COMMON_STOCK = "common_stock"
    ETF = "etf"
    FUND = "fund"
    WARRANT = "warrant"
    BOND = "bond"
    PREFERRED = "preferred"
    ADR = "adr"
    UNKNOWN = "unknown"


def aware(value: datetime) -> bool:
    return value.tzinfo is not None and value.utcoffset() is not None


@dataclass(frozen=True)
class Issuer:
    cik: str
    legal_name: str

    def __post_init__(self):
        if len(self.cik) != 10 or not self.cik.isascii() or not self.cik.isdigit():
            raise ValueError("CIK must contain exactly ten ASCII digits")
        if not self.legal_name.strip():
            raise ValueError("legal_name is required")


@dataclass(frozen=True)
class Security:
    issuer: Issuer
    symbol: str
    exchange: Exchange
    security_type: SecurityType
    active: bool
    observed_at: datetime

    def __post_init__(self):
        if not self.symbol.strip() or not aware(self.observed_at):
            raise ValueError("symbol and timezone-aware observation time are required")
        if not isinstance(self.exchange, Exchange) or not isinstance(self.security_type, SecurityType):
            raise ValueError("use explicit exchange and security-type enums")
        if type(self.active) is not bool:
            raise ValueError("active must be a verified boolean")

    def in_scope(self) -> bool:
        return self.active and self.security_type is SecurityType.COMMON_STOCK


@dataclass(frozen=True)
class Fact:
    issuer_id: str
    field: str
    value: Decimal
    source: Source
    period_start: date | None
    period_end: date
    currency: str | None
    unit: str
    retrieved_at: datetime
    available_at: datetime
    accounting_definition: str
    source_url: str
    filing_accession: str | None = None
    filed_on: date | None = None
    raw_sha256: str | None = None
    source_field: str | None = None
    identity_evidence_url: str | None = None
    identity_evidence_sha256: str | None = None
    identity_observed_at: datetime | None = None
    unit_evidence_url: str | None = None
    unit_evidence_sha256: str | None = None
    unit_observed_at: datetime | None = None
    data_observed_at: datetime | None = None
    source_multiplier: Decimal | None = None

    def __post_init__(self):
        if len(self.issuer_id) != 10 or not self.issuer_id.isascii() or not self.issuer_id.isdigit():
            raise ValueError("canonical CIK is required")
        if not isinstance(self.value, Decimal) or not self.value.is_finite():
            raise ValueError("value must be a finite Decimal; missing is never zero")
        if not isinstance(self.source, Source):
            raise ValueError("explicit source is required")
        if not all(s.strip() for s in (self.field, self.unit, self.accounting_definition)):
            raise ValueError("field, unit and accounting definition are required")
        if not self.source_url.startswith("https://"):
            raise ValueError("HTTPS provenance URL is required")
        if self.currency is not None and (len(self.currency) != 3 or not self.currency.isascii() or not self.currency.isupper() or not self.currency.isalpha()):
            raise ValueError("currency must be an uppercase three-letter code")
        if self.unit in ("currency", "currency_per_share") and self.currency is None:
            raise ValueError("monetary facts require currency")
        if self.period_start is not None and self.period_start > self.period_end:
            raise ValueError("period_start exceeds period_end")
        if not aware(self.retrieved_at) or not aware(self.available_at):
            raise ValueError("timestamps must be timezone-aware")
        if self.available_at.date() < self.period_end or self.available_at > self.retrieved_at:
            raise ValueError("invalid availability/retrieval chronology")
        if self.filing_accession is not None and not re.fullmatch(r"[0-9]{10}-[0-9]{2}-[0-9]{6}", self.filing_accession):
            raise ValueError("invalid accession")
        if self.filed_on is not None and (type(self.filed_on) is not date or self.filed_on < self.period_end or self.filed_on > self.available_at.date()):
            raise ValueError("invalid filing date")
        if self.raw_sha256 is not None and not re.fullmatch(r"[0-9a-f]{64}", self.raw_sha256):
            raise ValueError("invalid raw response checksum")
        if self.identity_observed_at is not None and (not aware(self.identity_observed_at) or self.identity_observed_at > self.retrieved_at):
            raise ValueError("invalid identity evidence time")
        if self.identity_evidence_url is not None and not self.identity_evidence_url.startswith("https://"):
            raise ValueError("identity provenance must use HTTPS")
        if self.identity_evidence_sha256 is not None and not re.fullmatch(r"[0-9a-f]{64}",self.identity_evidence_sha256):
            raise ValueError("invalid identity checksum")
        for stamp in (self.unit_observed_at,self.data_observed_at):
            if stamp is not None and (not aware(stamp) or stamp>self.retrieved_at):
                raise ValueError("invalid auxiliary evidence time")
        if self.unit_evidence_url is not None and not self.unit_evidence_url.startswith("https://"):
            raise ValueError("invalid unit evidence URL")
        if self.unit_evidence_sha256 is not None and not re.fullmatch(r"[0-9a-f]{64}",self.unit_evidence_sha256):
            raise ValueError("invalid unit evidence checksum")
        if self.source_multiplier is not None and (not isinstance(self.source_multiplier,Decimal) or not self.source_multiplier.is_finite() or self.source_multiplier<=0):
            raise ValueError("positive finite Decimal source multiplier required")


@dataclass(frozen=True)
class FactRequest:
    issuer_id: str
    field: str
    period_start: date | None
    period_end: date
    currency: str | None
    unit: str
    accounting_definition: str
    as_of: datetime

    def __post_init__(self):
        if not aware(self.as_of):
            raise ValueError("as_of must be timezone-aware")
        if self.period_start is not None and self.period_start > self.period_end:
            raise ValueError("invalid requested period")
        if self.period_end > self.as_of.date():
            raise ValueError("requested financial period is in the future")
        if not all(s.strip() for s in (self.issuer_id, self.field, self.unit, self.accounting_definition)):
            raise ValueError("request identity and accounting semantics are required")

    def rejection(self, fact: Fact) -> str | None:
        for field in ("issuer_id", "field", "period_start", "period_end", "currency", "unit", "accounting_definition"):
            if getattr(self, field) != getattr(fact, field):
                return "mismatch:" + field
        if fact.available_at > self.as_of:
            return "not_yet_public"
        # A current API response cannot establish historical point-in-time knowledge.
        # Historical adapters will require a separately validated vintage contract.
        if fact.retrieved_at > self.as_of:
            return "unverified_historical_vintage"
        return None


@dataclass(frozen=True)
class FactQuery:
    """Live collection specification with no pretended historical cutoff."""
    issuer_id: str
    field: str
    period_start: date | None
    period_end: date
    currency: str | None
    unit: str
    accounting_definition: str

    def at(self, cutoff: datetime) -> FactRequest:
        return FactRequest(self.issuer_id,self.field,self.period_start,self.period_end,
                           self.currency,self.unit,self.accounting_definition,cutoff)
