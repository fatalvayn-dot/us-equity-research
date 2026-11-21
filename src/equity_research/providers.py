"""Provider boundary. No exception message is persisted (may contain API keys)."""
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Callable, Protocol

from .models import Fact, FactQuery, FactRequest, SOURCE_ORDER, Source


class Status(str, Enum):
    VALID = "valid"
    MISSING = "missing"
    RATE_LIMIT = "rate_limit"
    API_ERROR = "api_error"
    EVIDENCE_ERROR = "evidence_error"
    SYMBOL_MISMATCH = "symbol_mismatch"
    INVALID_DATA = "invalid_data"
    NOT_CONFIGURED = "not_configured"
    TIMEOUT = "timeout"
    ACCESS_DENIED = "access_denied"
    UNSUPPORTED_FIELD = "unsupported_field"
    PERIOD_MISMATCH = "period_mismatch"
    INVALID_CONFIGURATION = "invalid_configuration"


class FailureReason(str, Enum):
    HTTP = "http"
    DNS = "dns"
    TLS = "tls"
    NETWORK = "network"
    TIMEOUT = "timeout"


class ProviderFailure(Exception):
    def __init__(self, status: Status, *, reason: FailureReason | None = None, http_status: int | None = None):
        if status in (Status.VALID, Status.MISSING):
            raise ValueError("missing must be an explicit provider response")
        self.status = status
        if reason is not None and not isinstance(reason, FailureReason):
            raise ValueError("only enumerated safe failure reasons allowed")
        if http_status is not None and (type(http_status) is not int or not 100 <= http_status <= 599):
            raise ValueError("invalid HTTP status")
        self.reason, self.http_status = reason, http_status
        super().__init__(status.value)


class Provider(Protocol):
    source: Source

    def fetch(self, request: FactRequest) -> Fact | None:
        """Return None only after a successful response confirms field absence."""
        ...


@dataclass(frozen=True)
class Attempt:
    source: Source
    status: Status
    attempted_at: datetime
    detail: str = ""
    cached: bool = False


@dataclass(frozen=True)
class Resolution:
    fact: Fact | None
    attempts: tuple[Attempt, ...]
    as_of: datetime | None = None

    @property
    def confirmed_absent(self) -> bool:
        return self.fact is None and len(self.attempts) == len(SOURCE_ORDER) and all(
            a.status is Status.MISSING for a in self.attempts
        )


class Resolver:
    def __init__(self, providers: list[Provider], clock: Callable[[], datetime] | None = None):
        by_source = {p.source: p for p in providers}
        if len(by_source) != len(providers) or any(not isinstance(p.source, Source) for p in providers):
            raise ValueError("providers must have distinct explicit sources")
        self.providers = by_source
        self.clock = clock or (lambda: datetime.now(timezone.utc))

    def resolve(self, request: FactRequest) -> Resolution:
        return self._resolve(request)

    def resolve_current(self, query: FactQuery) -> Resolution:
        """Prepare only the next needed source, then fix its evidence cutoff.

        Separate from fixed historical requests; never advances their cutoff.
        """
        if not isinstance(query, FactQuery):
            raise TypeError("resolve_current requires a cutoff-free FactQuery")
        query.at(self.clock())  # Validate query before any network operation.
        return self._resolve(query)

    def _resolve(self, specification) -> Resolution:
        attempts = []
        for source in SOURCE_ORDER:
            provider = self.providers.get(source)
            now = self.clock()
            if provider is None:
                attempts.append(Attempt(source, Status.NOT_CONFIGURED, now))
                continue
            try:
                if isinstance(specification, FactQuery):
                    prepare = getattr(provider, "prepare", None)
                    if prepare is not None:
                        prepare(specification)
                    request = specification.at(self.clock())
                else:
                    request = specification
                fact = provider.fetch(request)
            except ProviderFailure as exc:
                detail = exc.reason.value if exc.reason is not None else ""
                if exc.http_status is not None:
                    detail += ":" + str(exc.http_status)
                attempts.append(Attempt(source, exc.status, now, detail))
                continue
            except Exception as exc:
                attempts.append(Attempt(source, Status.API_ERROR, now, type(exc).__name__))
                continue
            if fact is None:
                attempts.append(Attempt(source, Status.MISSING, now))
                continue
            if not isinstance(fact, Fact):
                attempts.append(Attempt(source, Status.INVALID_DATA, now, "unexpected_response_type"))
                continue
            reason = request.rejection(fact)
            if fact.source != source:
                reason = "mismatch:source"
            if reason:
                status = Status.SYMBOL_MISMATCH if reason == "mismatch:issuer_id" else Status.INVALID_DATA
                attempts.append(Attempt(source, status, now, reason))
                continue
            attempts.append(Attempt(source, Status.VALID, now))
            return Resolution(fact, tuple(attempts), request.as_of)
        return Resolution(None, tuple(attempts))
