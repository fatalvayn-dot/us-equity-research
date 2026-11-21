"""Bounded GET transport with explicit source hosts and no redirect following."""
import hashlib
import json
import math
import socket
import ssl
import threading
import time
from http.client import HTTPException
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from email.utils import parsedate_to_datetime
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.parse import parse_qsl
from types import MappingProxyType
from urllib.request import HTTPRedirectHandler, Request, build_opener

from .providers import FailureReason, ProviderFailure, Status


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def strict_json(body: bytes):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("duplicate JSON key")
            result[key] = value
        return result

    def invalid_constant(value):
        raise ValueError("non-finite JSON number")

    try:
        return json.loads(body, object_pairs_hook=unique, parse_constant=invalid_constant, parse_float=Decimal)
    except (ValueError, UnicodeError, RecursionError):
        raise ProviderFailure(Status.INVALID_DATA) from None


@dataclass(frozen=True)
class Response:
    url: str
    body: bytes
    retrieved_at: datetime

    @property
    def sha256(self):
        return hashlib.sha256(self.body).hexdigest()


class RateLimiter:
    """Share one limiter across clients using the same provider in a process."""
    def __init__(self, interval=0.5, *, monotonic=time.monotonic, sleep=time.sleep):
        if not math.isfinite(interval) or interval < 0.1:
            raise ValueError("minimum request interval is 0.1 seconds")
        self.interval, self.monotonic, self.sleep = interval, monotonic, sleep
        self.next_allowed = 0.0
        self.lock = threading.Lock()

    def wait(self, deadline):
        with self.lock:
            now = self.monotonic()
            delay = max(0.0, self.next_allowed - now)
            if now + delay >= deadline:
                raise ProviderFailure(Status.TIMEOUT)
            if delay:
                self.sleep(delay)
            self.next_allowed = self.monotonic() + self.interval


class HttpTransport:
    def __init__(self, *, user_agent, allowed_hosts, timeout=10.0, budget=30.0,
                 max_attempts=3, max_bytes=16_000_000, limiter=None,
                 monotonic=time.monotonic, sleep=time.sleep, clock=None, opener=None,
                 auth_headers=None, accept="application/json"):
        if not isinstance(user_agent, str) or not user_agent.strip() or any(ord(c) < 32 or ord(c) > 126 for c in user_agent):
            raise ValueError("explicit printable identifying User-Agent required")
        if not all(math.isfinite(v) and v > 0 for v in (timeout, budget)):
            raise ValueError("positive finite timeout/budget required")
        if type(max_attempts) is not int or not 1 <= max_attempts <= 5 or type(max_bytes) is not int or max_bytes <= 0:
            raise ValueError("bounded attempts and positive byte limit required")
        if accept not in ("application/json","text/plain","text/html"):
            raise ValueError("explicit supported response media type required")
        self.accept=accept
        self.allowed_hosts = frozenset(allowed_hosts)
        if not self.allowed_hosts:
            raise ValueError("explicit source host allowlist required")
        headers=dict(auth_headers or {})
        if headers and (self.allowed_hosts != {"finnhub.io"} or set(headers) != {"X-Finnhub-Token"}):
            raise ValueError("Finnhub token headers require one exact Finnhub origin")
        if any(not isinstance(v,str) or not v or any(ord(c)<33 or ord(c)>126 for c in v) for v in headers.values()):
            raise ValueError("invalid authentication header")
        self._auth_headers=MappingProxyType(headers)
        self.user_agent, self.timeout, self.budget = user_agent, timeout, budget
        self.max_attempts, self.max_bytes = max_attempts, max_bytes
        self.monotonic, self.sleep = monotonic, sleep
        self.clock = clock or (lambda: datetime.now(timezone.utc))
        self.limiter = limiter or RateLimiter(monotonic=monotonic, sleep=sleep)
        self.opener = opener or build_opener(NoRedirect())

    def _validate_url(self, url):
        try:
            parts = urlsplit(url)
            valid = (parts.scheme == "https" and parts.hostname in self.allowed_hosts
                     and parts.port in (None, 443) and not parts.username
                     and not parts.password and not parts.fragment)
        except ValueError:
            valid = False
        if not valid or any(ord(c) < 32 for c in url):
            raise ValueError("URL must use HTTPS and an exact allowed source host")
        if self._auth_headers and any(k.lower() in ("token","api_key","apikey","key") for k,v in parse_qsl(parts.query)):
            raise ValueError("credentials must not appear in source URLs")

    def _retry_delay(self, headers, attempt):
        header = headers.get("Retry-After") if headers else None
        if header:
            try:
                if header.isascii() and header.isdigit():
                    delay = float(header)
                else:
                    when = parsedate_to_datetime(header)
                    delay = (when - self.clock()).total_seconds()
                return max(0.0, delay) if math.isfinite(delay) else self.budget
            except (ValueError, TypeError, OverflowError):
                pass
        return float(2 ** attempt)

    def get(self, url) -> Response:
        self._validate_url(url)
        deadline = self.monotonic() + self.budget
        for attempt in range(self.max_attempts):
            self.limiter.wait(deadline)
            remaining = deadline - self.monotonic()
            if remaining <= 0:
                raise ProviderFailure(Status.TIMEOUT)
            try:
                request = Request(url, headers={"User-Agent": self.user_agent,
                                  "Accept": self.accept, "Accept-Encoding": "identity",**self._auth_headers})
                with self.opener.open(request, timeout=min(self.timeout, remaining)) as response:
                    if response.geturl() != url or response.status != 200:
                        raise ProviderFailure(Status.API_ERROR)
                    if response.headers.get("Content-Encoding", "identity").lower() != "identity":
                        raise ProviderFailure(Status.INVALID_DATA)
                    length = response.headers.get("Content-Length")
                    if length is not None and (not length.isascii() or not length.isdigit() or int(length) > self.max_bytes):
                        raise ProviderFailure(Status.INVALID_DATA)
                    chunks, size = [], 0
                    # read1 returns after at most one underlying buffered read.
                    # Check the overall deadline between reads in addition to socket timeout.
                    while True:
                        if self.monotonic() >= deadline:
                            raise ProviderFailure(Status.TIMEOUT)
                        chunk = response.read1(min(65536, self.max_bytes - size + 1))
                        if not chunk:
                            break
                        size += len(chunk)
                        if size > self.max_bytes:
                            raise ProviderFailure(Status.INVALID_DATA)
                        chunks.append(chunk)
                    if length is not None and size != int(length):
                        raise ProviderFailure(Status.INVALID_DATA)
                    body=b"".join(chunks)
                    if any(secret.encode("ascii") in body for secret in self._auth_headers.values()):
                        raise ProviderFailure(Status.INVALID_DATA)
                    return Response(url, body, self.clock())
            except HTTPError as exc:
                code, headers = exc.code, exc.headers
                exc.close()
                if code in (401, 403):
                    raise ProviderFailure(Status.ACCESS_DENIED,reason=FailureReason.HTTP,http_status=code) from None
                status = Status.RATE_LIMIT if code == 429 else Status.API_ERROR
                reason, http_code = FailureReason.HTTP, code
                if code not in (429, 500, 502, 503, 504):
                    raise ProviderFailure(status,reason=reason,http_status=code) from None
                delay = self._retry_delay(headers, attempt)
            except (TimeoutError, socket.timeout):
                status, delay = Status.TIMEOUT, float(2 ** attempt)
                reason, http_code = FailureReason.TIMEOUT, None
            except URLError as exc:
                status = Status.TIMEOUT if isinstance(exc.reason, TimeoutError) else Status.API_ERROR
                reason = (FailureReason.TIMEOUT if status is Status.TIMEOUT else
                          FailureReason.DNS if isinstance(exc.reason,socket.gaierror) else
                          FailureReason.TLS if isinstance(exc.reason,ssl.SSLError) else FailureReason.NETWORK)
                http_code = None
                delay = float(2 ** attempt)
            except (ConnectionError, OSError, HTTPException):
                status, delay = Status.API_ERROR, float(2 ** attempt)
                reason, http_code = FailureReason.NETWORK, None
            if attempt == self.max_attempts - 1 or self.monotonic() + delay >= deadline:
                raise ProviderFailure(status,reason=reason,http_status=http_code) from None
            self.sleep(delay)
        raise AssertionError("unreachable")
