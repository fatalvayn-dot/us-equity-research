"""Read-only, evidence-labelled market radar pilot. No broker or order access."""
from __future__ import annotations
import argparse
import csv
import io
import json
import math
import os
import pathlib
import statistics
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone

DEFAULT_WATCH = {
    "ABD_HISSE": {"AAPL": "aapl.us", "MSFT": "msft.us"},
    "ABD_ETF": {"SPY": "spy.us", "QQQ": "qqq.us"},
    "EMTIA_VEKIL": {"GLD": "gld.us", "SLV": "slv.us", "USO": "uso.us"},
}
# Commodity ETF proxies are NOT physical spot quotes. BIST and Europe not claimed as covered.
KEYWORDS = {
    "risk": ("war", "conflict", "sanction", "pandemic", "earthquake", "attack", "tariff",
             "savaş", "çatışma", "yaptırım", "salgın", "deprem"),
    "macro": ("inflation", "interest rate", "central bank", "fed", "ecb",
              "enflasyon", "faiz", "merkez bankası"),
}
UA = "us-equity-research radar research/0.1 (read-only)"

def fetch_prices(stooq_symbol: str, timeout=12):
    query = urllib.parse.urlencode({"s": stooq_symbol, "i": "d"})
    req = urllib.request.Request("https://stooq.com/q/d/l/?" + query, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        raw = resp.read(2_000_000).decode("utf-8-sig")
    rows = []
    for row in csv.DictReader(io.StringIO(raw)):
        try:
            day, close = row["Date"], float(row["Close"])
            if close > 0 and math.isfinite(close):
                rows.append({"date": day, "close": close})
        except (KeyError, ValueError, TypeError):
            continue
    rows.sort(key=lambda r: r["date"])
    if len(rows) < 22:
        raise ValueError("insufficient historical closes")
    return rows[-260:]

def load_fixture(path):
    data = json.loads(pathlib.Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("fixture must be a symbol-to-rows mapping")
    return data

def news_digest(url=None, timeout=10):
    if not url:
        return {"status": "not_configured", "items": [], "risk_count": None}
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        xml_bytes = resp.read(800_000)
    root = ET.fromstring(xml_bytes)
    items = []
    for item in root.findall(".//item")[:30]:
        title = (item.findtext("title") or "").strip()[:300]
        if not title:
            continue
        low = title.casefold()
        categories = [name for name, terms in KEYWORDS.items() if any(x in low for x in terms)]
        items.append({"title": title, "categories": categories,
                      "url": (item.findtext("link") or "")[:500]})
    return {"status": "ok", "items": items, "risk_count": sum("risk" in x["categories"] for x in items)}

def signal(rows):
    if len(rows) < 22:
        raise ValueError("need at least 22 daily prices")
    points = [(r["date"], float(r["close"])) for r in rows]
    if any(not math.isfinite(p) or p <= 0 for _, p in points):
        raise ValueError("invalid close")
    if points != sorted(points):
        raise ValueError("prices must be sorted by date")
    if len({d for d, _ in points}) != len(points):
        raise ValueError("duplicate dates")
    values = [v for _, v in points]
    momentum_5 = values[-1] / values[-6] - 1
    momentum_20 = values[-1] / values[-21] - 1
    trend = "yukari" if momentum_5 > 0 and momentum_20 > 0 else (
        "asagi" if momentum_5 < 0 and momentum_20 < 0 else "kararsiz")
    return {"as_of": points[-1][0], "close": values[-1], "momentum_5": round(momentum_5, 6),
            "momentum_20": round(momentum_20, 6), "direction": trend,
            "horizon_sessions": 5, "method": "5d_20d_momentum_baseline",
            "confidence": None, "eligibility": "bilinmiyor", "investment_advice": False}

def evaluate(old_predictions, current_prices):
    results = []
    for pred in old_predictions:
        symbol = pred.get("symbol")
        history = current_prices.get(symbol, [])
        dates = [r["date"] for r in history]
        date = pred.get("as_of")
        if date not in dates or len(dates) <= dates.index(date) + 5:
            results.append({"symbol": symbol, "as_of": date, "status": "pending"})
            continue
        idx = dates.index(date)
        start, finish = float(history[idx]["close"]), float(history[idx+5]["close"])
        movement = finish/start - 1
        actual = "yukari" if movement > 0 else ("asagi" if movement < 0 else "duz")
        forecast = pred.get("direction")
        hit = forecast == actual if forecast in ("yukari", "asagi") else None
        results.append({"symbol": symbol, "as_of": date, "status": "evaluated",
                        "realized_5d": round(movement, 6), "actual": actual, "hit": hit})
    return results

def run(fixture=None, prior=None, feed=None):
    history = load_fixture(fixture) if fixture else {}
    source = "fixture" if fixture else "stooq_daily"
    errors = []
    coverage = {}
    for category, symbols in DEFAULT_WATCH.items():
        for symbol, provider_symbol in symbols.items():
            if symbol not in history and not fixture:
                try:
                    history[symbol] = fetch_prices(provider_symbol)
                except Exception as exc:
                    errors.append({"symbol": symbol, "reason": type(exc).__name__,
                                   "note": "provider unavailable; no forecast"})
            if symbol in history:
                coverage[symbol] = category
    forecasts = []
    for symbol, category in coverage.items():
        try:
            forecast = signal(history[symbol])
            forecast.update({"symbol": symbol, "asset_group": category,
                             "source": source, "source_symbol": DEFAULT_WATCH[category][symbol]})
            forecasts.append(forecast)
        except (ValueError, KeyError, TypeError) as exc:
            errors.append({"symbol": symbol, "reason": type(exc).__name__,
                           "note": "invalid input; no forecast"})
    try:
        headlines = news_digest(feed)
    except Exception as exc:
        headlines = {"status": "unavailable", "items": [], "risk_count": None}
        errors.append({"source": "news", "reason": type(exc).__name__})
    old = json.loads(pathlib.Path(prior).read_text(encoding="utf-8")) if prior else []
    review = evaluate(old, history)
    dated = datetime.now(timezone.utc).isoformat()
    return {"generated_at_utc": dated, "mode": "historical_fixture" if fixture else "live_attempt",
            "forecast_status": "uncalibrated_research_only", "news": headlines,
            "forecasts": forecasts, "evaluation": review, "errors": errors,
            "coverage": {"forecast_count": len(forecasts), "requested": sum(map(len, DEFAULT_WATCH.values())),
                         "bist": "not_implemented", "europe": "not_implemented",
                         "global_equities_and_etfs": "not_implemented",
                         "physical_commodities": "not_implemented"},
            "restrictions": {"orders": False, "portfolio_access": False,
                             "participation_approval": False, "trading_recommendations": False}}

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--fixture", help="Offline test JSON of date/close rows per symbol")
    ap.add_argument("--prior", help="Previous forecasts JSON array; 5-session evaluation")
    ap.add_argument("--rss", help="Optional publicly accessible RSS feed URL")
    ap.add_argument("--out", default="radar-pilot-report.json")
    args = ap.parse_args()
    result = run(args.fixture, args.prior, args.rss)
    pathlib.Path(args.out).write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("Radar pilot:", result["mode"], "forecasts", len(result["forecasts"]),
          "errors", len(result["errors"]), "file", args.out)

if __name__ == "__main__":
    main()
