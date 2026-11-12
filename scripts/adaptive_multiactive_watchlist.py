"""Supplementary public ETF/crypto observation feed, separated from equity valuation.

This is a generic research universe; it contains NO account positions, personal
balances or trade history. Unknown provider instrument classes fail closed.
"""
import argparse
import json
import math
from datetime import datetime, timezone
from pathlib import Path
from scripts.adaptive_daily_brief import get_chart

ASSET_CLASSES = {"etf": {"ETF"}, "crypto": {"CRYPTOCURRENCY"}}
MAX_SYMBOLS = 40


def validate_watchlist(data):
    if not isinstance(data, dict) or data.get("schema_version") != 1:
        raise ValueError("watchlist version")
    items = data.get("instruments")
    if not isinstance(items, list) or len(items) > MAX_SYMBOLS:
        raise ValueError("watchlist must be bounded")
    seen = set()
    for item in items:
        if not isinstance(item, dict) or set(item) != {"symbol", "asset_class", "currency"}:
            raise ValueError("unexpected watchlist fields")
        symbol = item["symbol"]
        if not isinstance(symbol, str) or not symbol or len(symbol) > 30 or not all(
            c.isupper() or c.isdigit() or c in ".-=" for c in symbol
        ):
            raise ValueError("invalid symbol")
        if item["asset_class"] not in ASSET_CLASSES or item["currency"] not in ("USD", "TRY", "EUR"):
            raise ValueError("invalid class/currency")
        if symbol in seen:
            raise ValueError("duplicate ticker")
        seen.add(symbol)
    return items


def parse_observation(payload, item, url, clock):
    results = payload["chart"]["result"]
    if payload["chart"]["error"] is not None or len(results) != 1:
        raise ValueError("bad chart response")
    meta = results[0]["meta"]
    if meta.get("symbol") != item["symbol"] or meta.get("currency") != item["currency"]:
        raise ValueError("quote identity mismatch")
    if meta.get("instrumentType") not in ASSET_CLASSES[item["asset_class"]]:
        raise ValueError("quote instrument type mismatch")
    price, stamp = meta.get("regularMarketPrice"), meta.get("regularMarketTime")
    if (type(price) not in (int, float) or not math.isfinite(price) or price <= 0
            or type(stamp) is not int):
        raise ValueError("invalid quote")
    dt = datetime.fromtimestamp(stamp, timezone.utc)
    age = (clock - dt).total_seconds()
    if age < 0:
        raise ValueError("future quote")
    # Previous-close change may use different trading sessions for crypto and ETFs.
    # Do not derive a 24h / daily return from potentially mismatched baselines.
    return {"status": "observed", "price": float(price),
            "observed_at": dt.isoformat(), "stale_over_4_days": age > 4 * 86400,
            "source_url": url}


def collect(data, fetch=get_chart, clock=None):
    clock = clock or datetime.now(timezone.utc)
    if clock.tzinfo is None or clock.utcoffset() is None:
        raise ValueError("aware timestamp required")
    items = validate_watchlist(data)
    rows = []
    for item in items:
        try:
            body, url = fetch(item["symbol"])
            quote = parse_observation(body, item, url, clock)
        except (ValueError, KeyError, IndexError, TypeError, TimeoutError, OSError):
            quote = {"status": "unavailable", "price": None, "observed_at": None,
                     "source_url": None}
        rows.append({**item, **quote, "midas_tradability": "unverified",
                     "participation_status": "unknown", "investment_action": None})
    return {"schema_version": 1, "created_at": clock.isoformat(),
            "personal_portfolio_included": False, "research_only": True,
            "instruments": rows}


def main():
    cli = argparse.ArgumentParser()
    cli.add_argument("--input", default="data/analyst/public_multiactive_watchlist.json")
    cli.add_argument("--out", default="data/analyst-output/multiactive-research.json")
    args = cli.parse_args()
    data = json.loads(Path(args.input).read_text(encoding="utf-8"))
    report = collect(data)
    dest = Path(args.out)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"observed": sum(x["status"] == "observed" for x in report["instruments"]),
                      "total": len(report["instruments"])}, ensure_ascii=False))


if __name__ == "__main__":
    main()
