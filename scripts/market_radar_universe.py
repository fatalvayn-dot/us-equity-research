"""Audit the existing public research list for bounded, read-only price observation.

This file is NOT an official active-listing catalogue, a sector/participation
screen, or evidence that any instrument is suitable for a new investment.
"""
from __future__ import annotations

import hashlib
import json
import pathlib
import re

MAX_INPUT_BYTES = 100_000
MAX_PUBLIC_EQUITIES = 40
MAX_TOTAL_SYMBOLS = 50
MARKETS = {
    "ABD": ("ABD_HISSE", "USD", re.compile(r"[A-Z0-9][A-Z0-9.-]{0,19}")),
    "BIST": ("BIST_HISSE_ORNEK", "TRY", re.compile(r"[A-Z0-9][A-Z0-9.-]{0,15}\.IS")),
    "AVRUPA": ("AVRUPA_HISSE_ORNEK", "EUR", re.compile(r"[A-Z0-9][A-Z0-9.-]{0,15}\.DE")),
}


def load_public_watch(path, base):
    """Merge an explicitly public, finite research list with the original pilot.

    The official exchange universe, provider asset class, sector and Islamic
    eligibility must each be independently verified before investment use.
    """
    p = pathlib.Path(path)
    if p.stat().st_size > MAX_INPUT_BYTES:
        raise ValueError("public universe file exceeds size limit")
    original = p.read_bytes()
    data = json.loads(original)
    if not isinstance(data, dict) or data.get("schema_version") != 1:
        raise ValueError("public universe schema_version must be 1")
    markets = data.get("markets")
    if not isinstance(markets, dict) or set(markets) != set(MARKETS):
        raise ValueError("public universe must declare exact supported markets")

    watch = {group: dict(items) for group, items in base.items()}
    owner = {}
    for group, items in watch.items():
        for symbol in items:
            if symbol in owner:
                raise ValueError("duplicate pilot symbol across asset groups")
            owner[symbol] = group

    counts = {}
    for market, (group, currency, pattern) in MARKETS.items():
        entries = markets[market]
        if not isinstance(entries, list):
            raise ValueError("market instruments must be a list")
        counts[market] = len(entries)
        if sum(counts.values()) > MAX_PUBLIC_EQUITIES:
            raise ValueError("public research candidate limit exceeded")
        seen_market = set()
        for item in entries:
            if not isinstance(item, dict) or set(item) != {"symbol", "currency"}:
                raise ValueError("unexpected public research item fields")
            symbol = item["symbol"]
            if (not isinstance(symbol, str) or not pattern.fullmatch(symbol)
                    or item["currency"] != currency or symbol in seen_market):
                raise ValueError("invalid/duplicated symbol or currency")
            seen_market.add(symbol)
            if symbol in owner and owner[symbol] != group:
                raise ValueError("symbol assigned to conflicting asset class")
            if symbol not in owner:
                watch.setdefault(group, {})[symbol] = None
                owner[symbol] = group

    total = sum(len(items) for items in watch.values())
    if total > MAX_TOTAL_SYMBOLS:
        raise ValueError("total daily observation budget exceeded")
    return watch, {
        "status": "public_research_list_only",
        "file": str(p).replace("\\", "/"),
        "source_sha256": hashlib.sha256(original).hexdigest(),
        "source_count_by_market": counts,
        "total_requested_symbols": total,
        "official_listing_verified": False,
        "sector_verified": False,
        "participation_verified": False,
        "investment_candidates": False,
    }
