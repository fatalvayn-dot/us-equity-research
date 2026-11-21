"""Strict SEC companyfacts adapter; no tag substitution or period inference."""
import json
import os
import re
import tempfile
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal
from pathlib import Path

from .models import Fact, FactRequest, Source, aware
from .providers import ProviderFailure, Status
from .transport import HttpTransport, Response, strict_json

from .fields import TAGS
FORMS = frozenset({"10-K", "10-K/A", "10-Q", "10-Q/A"})


def companyfacts_url(cik: str) -> str:
    if not isinstance(cik, str) or re.fullmatch(r"[0-9]{10}", cik) is None or int(cik) == 0:
        raise ValueError("canonical nonzero CIK required")
    return f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json"


class SecCompanyFacts:
    source = Source.SEC

    def __init__(self, transport: HttpTransport, *, cache_dir=None, ttl=timedelta(hours=6), clock=None):
        if ttl <= timedelta(0):
            raise ValueError("positive TTL required")
        self.transport = transport
        self.cache_dir = Path(cache_dir) if cache_dir is not None else None
        self.ttl = ttl
        self.clock = clock or (lambda: datetime.now(timezone.utc))
        self.memory = {}
        self.cache_events = []

    @staticmethod
    def _parse(response, cik):
        if response.url != companyfacts_url(cik) or not aware(response.retrieved_at):
            raise ProviderFailure(Status.INVALID_DATA)
        payload = strict_json(response.body)
        if not isinstance(payload, dict) or type(payload.get("cik")) is not int:
            raise ProviderFailure(Status.INVALID_DATA)
        if payload["cik"] != int(cik):
            raise ProviderFailure(Status.SYMBOL_MISMATCH)
        if not isinstance(payload.get("facts"), dict) or not isinstance(payload.get("entityName"), str):
            raise ProviderFailure(Status.INVALID_DATA)
        return response, payload

    def _fresh(self, response):
        now = self.clock()
        return aware(now) and timedelta(0) <= now - response.retrieved_at < self.ttl

    def snapshot(self, cik: str, *, refresh=False):
        """Fetch before constructing an as_of cutoff; retain original retrieval time."""
        url = companyfacts_url(cik)
        if not refresh and cik in self.memory and self._fresh(self.memory[cik][0]):
            return self.memory[cik]
        path = self.cache_dir / (cik + ".json") if self.cache_dir is not None else None
        if not refresh and path is not None and path.exists():
            try:
                if path.stat().st_size > self.transport.max_bytes * 2 + 4096:
                    raise ValueError("oversized cache")
                envelope = json.loads(path.read_text())
                response = Response(envelope["url"], envelope["body"].encode("utf-8"),
                                    datetime.fromisoformat(envelope["retrieved_at"]))
                if response.sha256 != envelope["sha256"] or len(response.body) > self.transport.max_bytes:
                    raise ValueError("cache integrity failure")
                parsed = self._parse(response, cik)
                if self._fresh(response):
                    self.memory[cik] = parsed
                    self.cache_events.append("disk_hit:" + cik)
                    return parsed
            except (ValueError, KeyError, TypeError, ProviderFailure):
                self.cache_events.append("invalid_cache:" + cik)
        response = self.transport.get(url)
        parsed = self._parse(response, cik)
        if not self._fresh(response):
            raise ProviderFailure(Status.INVALID_DATA)
        if path is not None:
            path.parent.mkdir(parents=True, exist_ok=True)
            envelope = {"url": response.url, "body": response.body.decode("utf-8"),
                        "retrieved_at": response.retrieved_at.isoformat(), "sha256": response.sha256}
            temp = None
            try:
                with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent, delete=False) as handle:
                    temp = handle.name
                    json.dump(envelope, handle)
                    handle.flush()
                    os.fsync(handle.fileno())
                os.replace(temp, path)
            finally:
                if temp is not None and os.path.exists(temp):
                    os.unlink(temp)
        self.memory[cik] = parsed
        self.cache_events.append("fetched:" + cik)
        return parsed

    def fetch(self, request: FactRequest) -> Fact | None:
        self._validate_specification(request)
        tag, instant = TAGS[request.field]
        response, payload = self.snapshot(request.issuer_id)
        return self._extract(request, tag, response, payload)

    def prepare(self, query):
        self._validate_specification(query)
        self.snapshot(query.issuer_id)

    @staticmethod
    def _validate_specification(request):
        specification = TAGS.get(request.field)
        if specification is None:
            raise ProviderFailure(Status.UNSUPPORTED_FIELD)
        tag, instant = specification
        if (request.accounting_definition != "us-gaap:" + tag or request.unit != "currency"
                or request.currency is None or instant != (request.period_start is None)):
            raise ProviderFailure(Status.INVALID_DATA)
    def _extract(self, request, tag, response, payload):
        # Reject current API snapshots used as unverified historical vintages.
        if response.retrieved_at > request.as_of:
            raise ProviderFailure(Status.INVALID_DATA)
        taxonomy = payload["facts"].get("us-gaap")
        if taxonomy is None:
            if "ifrs-full" in payload["facts"]:
                raise ProviderFailure(Status.UNSUPPORTED_FIELD)
            return None
        if not isinstance(taxonomy, dict):
            raise ProviderFailure(Status.INVALID_DATA)
        concept = taxonomy.get(tag)
        if concept is None:
            return None
        if not isinstance(concept, dict) or not isinstance(concept.get("units"), dict):
            raise ProviderFailure(Status.INVALID_DATA)
        rows = concept["units"].get(request.currency)
        if rows is None:
            return None
        if not isinstance(rows, list):
            raise ProviderFailure(Status.INVALID_DATA)
        candidates = []
        try:
            for row in rows:
                if not isinstance(row, dict):
                    raise ValueError("invalid row")
                end = date.fromisoformat(row["end"])
                start = date.fromisoformat(row["start"]) if "start" in row else None
                if (start, end) != (request.period_start, request.period_end):
                    continue
                if row.get("form") not in FORMS:
                    continue
                filed = date.fromisoformat(row["filed"])
                # SEC supplies only a filing date here: wait through that entire
                # Eastern date, using 05:00 UTC conservatively for EST and EDT.
                available = datetime.combine(filed + timedelta(days=1), time(5), timezone.utc)
                if available > min(request.as_of, response.retrieved_at):
                    continue
                value = row["val"]
                if type(value) not in (int, Decimal):
                    raise ValueError("invalid numeric value")
                accession = row["accn"]
                fact = Fact(request.issuer_id, request.field, Decimal(value), Source.SEC,
                            start, end, request.currency, "currency", response.retrieved_at,
                            available, "us-gaap:" + tag, response.url,
                            filing_accession=accession, filed_on=filed, raw_sha256=response.sha256)
                candidates.append(fact)
        except (KeyError, ValueError, TypeError, OverflowError):
            raise ProviderFailure(Status.INVALID_DATA) from None
        if not candidates:
            return None
        latest_day = max(f.filed_on for f in candidates)
        latest = [f for f in candidates if f.filed_on == latest_day]
        # Do not silently choose between conflicting values filed the same day.
        if len({f.value for f in latest}) != 1:
            raise ProviderFailure(Status.INVALID_DATA)
        return max(latest, key=lambda f: f.filing_accession)
