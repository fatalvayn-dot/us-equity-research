"""Read-only, evidence-labelled market radar pilot. No broker or order access."""
from __future__ import annotations
import argparse
import csv
import io
import hashlib
import json
import math
import os
import pathlib
import statistics
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from email.utils import parsedate_to_datetime
from datetime import datetime, timezone

DEFAULT_WATCH = {
    "ABD_HISSE": {"AAPL": "aapl.us", "MSFT": "msft.us"},
    "ABD_ETF": {"SPY": "spy.us", "QQQ": "qqq.us"},
    "EMTIA_VEKIL": {"GLD": "gld.us", "SLV": "slv.us", "USO": "uso.us"},
    "BIST_HISSE_ORNEK": {"ASELS.IS": None},
    "AVRUPA_HISSE_ORNEK": {"SAP.DE": None},
}
# Commodity ETFs are not physical spot quotes. BIST/Europe are representative samples, not full exchange coverage.
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

def fetch_yfinance(symbol: str, timeout=12):
    """Reuse the Apache-2.0 yfinance project's historical price adapter.

    This is a separate optional provider; the existing Yahoo Chart and Stooq
    adapters remain fallbacks. Do not treat an incomplete current-day bar as a close.
    """
    import yfinance as yf
    frame = yf.Ticker(symbol).history(period="2y", interval="1d",
                                      auto_adjust=False, timeout=timeout)
    if frame is None or frame.empty:
        raise ValueError("yfinance returned no daily prices")
    by_day = {}
    for stamp, values in frame.iterrows():
        day = stamp.date().isoformat()
        try:
            close = float(values["Close"])
        except (KeyError, TypeError, ValueError):
            continue
        if close > 0 and math.isfinite(close):
            by_day[day] = {"date": day, "close": close}
    days = sorted(by_day)
    today = datetime.now(timezone.utc).date().isoformat()
    if days and days[-1] >= today:
        days = [d for d in days if d < today]
    if len(days) < 22:
        raise ValueError("yfinance returned insufficient completed daily closes")
    return [by_day[d] for d in days[-260:]]


def fetch_yahoo_chart(symbol: str, timeout=12):
    """Read a bounded set of daily closes from the public Yahoo chart endpoint."""
    path = urllib.parse.quote(symbol, safe="")
    url = "https://query1.finance.yahoo.com/v8/finance/chart/" + path + "?range=2y&interval=1d"
    req = urllib.request.Request(url, headers={
        "User-Agent": "Mozilla/5.0 (compatible; radar-research/0.2)",
        "Accept": "application/json",
    })
    with urllib.request.urlopen(req, timeout=timeout) as response:
        payload = json.loads(response.read(4_000_000))
    chart = (payload.get("chart", {}).get("result") or [None])[0]
    if not chart:
        raise ValueError("yahoo chart returned no result")
    times = chart.get("timestamp", [])
    close = chart.get("indicators", {}).get("quote", [{}])[0].get("close", [])
    parsed = {}
    for stamp, value in zip(times, close):
        if value is None or not math.isfinite(float(value)) or float(value) <= 0:
            continue
        day = datetime.fromtimestamp(stamp, timezone.utc).date().isoformat()
        parsed[day] = {"date": day, "close": float(value)}
    rows = [parsed[day] for day in sorted(parsed)]
    # Today's bar may be incomplete. Avoid recording intraday price as end-of-day.
    if rows and rows[-1]["date"] == datetime.now(timezone.utc).date().isoformat() and datetime.now(timezone.utc).hour < 23:
        rows.pop()
    if len(rows) < 22:
        raise ValueError("yahoo chart has insufficient completed daily closes")
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
    retrieved_at = datetime.now(timezone.utc)
    root = ET.fromstring(xml_bytes)
    items = []
    invalid_dates = 0
    future_dated = 0
    for item in root.findall(".//item")[:30]:
        title = (item.findtext("title") or "").strip()[:300]
        if not title:
            continue
        low = title.casefold()
        categories = [name for name, terms in KEYWORDS.items() if any(x in low for x in terms)]
        reported_time = (item.findtext("pubDate") or "").strip()
        observed_time = None
        if reported_time:
            try:
                published = parsedate_to_datetime(reported_time)
                if published.tzinfo is not None:
                    published = published.astimezone(timezone.utc)
                    if published > retrieved_at:
                        future_dated += 1
                        continue
                    observed_time = published.isoformat()
                else:
                    invalid_dates += 1
            except (ValueError, TypeError, IndexError, OverflowError):
                invalid_dates += 1
        else:
            invalid_dates += 1
        items.append({"title": title, "categories": categories,
                      "url": (item.findtext("link") or "")[:500],
                      "published_at_utc": observed_time})
    return {"status": "ok", "items": items,
            "retrieved_at_utc": retrieved_at.isoformat(),
            "source_sha256": hashlib.sha256(xml_bytes).hexdigest(),
            "dated_items": sum(x["published_at_utc"] is not None for x in items),
            "undated_items": invalid_dates,
            "future_dated_excluded": future_dated,
            "event_price_impact_validated": False,
            "risk_count": sum("risk" in x["categories"] for x in items)}

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
    errors = []
    coverage = {}
    sources = {}
    for category, symbols in DEFAULT_WATCH.items():
        for symbol, provider_symbol in symbols.items():
            if fixture and symbol in history:
                sources[symbol] = "fixture"
            if symbol not in history and not fixture:
                attempts = []
                providers = [
                    ("yfinance_daily", lambda s=symbol: fetch_yfinance(s)),
                    ("yahoo_chart_daily", lambda s=symbol: fetch_yahoo_chart(s)),
                ]
                if provider_symbol:
                    providers.append(("stooq_daily", lambda s=provider_symbol: fetch_prices(s)))
                for provider_name, fetcher in providers:
                    try:
                        history[symbol] = fetcher()
                        sources[symbol] = provider_name
                        break
                    except Exception as exc:
                        attempts.append({"provider": provider_name,
                                         "reason": type(exc).__name__})
                if symbol not in history:
                    errors.append({"symbol": symbol, "attempts": attempts,
                                   "note": "no verified historical prices; no forecast"})
            if symbol in history:
                coverage[symbol] = category
    forecasts = []
    for symbol, category in coverage.items():
        try:
            forecast = signal(history[symbol])
            forecast.update({"symbol": symbol, "asset_group": category,
                             "source": sources.get(symbol, "unknown"),
                             "source_symbol": symbol, "stooq_symbol": DEFAULT_WATCH[category][symbol]})
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
                         "bist": "sample_only" if "ASELS.IS" in coverage else "unavailable",
                         "europe": "sample_only" if "SAP.DE" in coverage else "unavailable",
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
