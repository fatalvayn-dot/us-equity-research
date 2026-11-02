"""Versioned SQLite cache for accepted facts only; failures are never cached."""
import json
import sqlite3
from dataclasses import asdict
from datetime import date, datetime, timedelta
from decimal import Decimal
from pathlib import Path

from .models import Fact, FactRequest, Source, aware


def encode(value):
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return str(value)
    raise TypeError(type(value).__name__)


def decode_fact(payload):
    data=dict(payload)
    data["value"]=Decimal(data["value"]);data["source"]=Source(data["source"])
    data["period_start"]=date.fromisoformat(data["period_start"]) if data["period_start"] else None
    data["period_end"]=date.fromisoformat(data["period_end"])
    if data.get("filed_on") is not None:data["filed_on"]=date.fromisoformat(data["filed_on"])
    for key in ("available_at","retrieved_at","identity_observed_at","unit_observed_at","data_observed_at"):
        if data.get(key) is not None:data[key]=datetime.fromisoformat(data[key])
    if data.get("source_multiplier") is not None:data["source_multiplier"]=Decimal(data["source_multiplier"])
    return Fact(**data)


class FactCache:
    def __init__(self, path: str | Path):
        self.db = sqlite3.connect(path)
        self.db.execute("CREATE TABLE IF NOT EXISTS facts_v1 (key TEXT PRIMARY KEY, payload TEXT NOT NULL, stored_at TEXT NOT NULL)")

    @staticmethod
    def key(request: FactRequest, source: Source) -> str:
        # Include time and full semantics: never reuse current facts for a past query.
        return json.dumps({**asdict(request), "source": source.value}, default=encode, sort_keys=True)

    def put(self, request: FactRequest, fact: Fact, now: datetime):
        if not aware(now) or now < fact.retrieved_at:
            raise ValueError("cache time precedes retrieval or has no timezone")
        if request.rejection(fact):
            raise ValueError("cannot cache a fact that fails the request")
        with self.db:
            self.db.execute("INSERT OR REPLACE INTO facts_v1 VALUES (?, ?, ?)", (
                self.key(request, fact.source), json.dumps(asdict(fact), default=encode), now.isoformat()))

    def get(self, request: FactRequest, source: Source, now: datetime, ttl: timedelta) -> Fact | None:
        if not aware(now) or ttl <= timedelta(0):
            raise ValueError("aware time and positive TTL required")
        row = self.db.execute("SELECT payload, stored_at FROM facts_v1 WHERE key=?", (self.key(request, source),)).fetchone()
        if row is None:
            return None
        stored_at = datetime.fromisoformat(row[1])
        if now < stored_at or now - stored_at >= ttl:
            return None
        fact = decode_fact(json.loads(row[0]))
        return fact if fact.source is source and request.rejection(fact) is None else None

    def close(self):
        self.db.close()
