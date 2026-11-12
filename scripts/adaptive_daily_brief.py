"""Minimal, read-only three-market evidence handoff for a human/AI analyst.

No portfolio positions, personal balances, investment scores, or automated orders.
A provider failure yields an explicit missing observation, never a guessed price.
"""
import argparse
import json
import math
import re
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

MARKETS = ("ABD", "BIST", "AVRUPA")
SYMBOL = re.compile(r"^[A-Z][A-Z0-9.\-]{0,18}$")
PRICE_HOST = "https://query1.finance.yahoo.com/v8/finance/chart/"


def validate_universe(document):
    if document.get("schema_version") != 1:
        raise ValueError("unsupported universe version")
    markets = document.get("markets")
    if not isinstance(markets, dict) or set(markets) != set(MARKETS):
        raise ValueError("exact ABD, BIST, AVRUPA markets required")
    seen = set()
    for market in MARKETS:
        entries = markets[market]
        if not isinstance(entries, list) or len(entries) > 200:
            raise ValueError("market list must contain at most 200 entries")
        for item in entries:
            if not isinstance(item, dict) or set(item) != {"symbol", "currency"}:
                raise ValueError("exact public research symbol and currency required")
            symbol, currency = item["symbol"], item["currency"]
            if (not isinstance(symbol, str) or not SYMBOL.fullmatch(symbol)
                    or currency not in {"USD", "EUR", "TRY"} or symbol in seen):
                raise ValueError("invalid or duplicate research symbol")
            seen.add(symbol)
    return markets


def get_chart(symbol, timeout=8):
    url = PRICE_HOST + quote(symbol, safe="") + "?interval=1d&range=5d"
    request = Request(url, headers={
        "User-Agent": "Mozilla/5.0 (compatible; adaptive-investment-research/1.0)",
        "Accept": "application/json",
    })
    with urlopen(request, timeout=timeout) as response:
        if response.status != 200:
            raise ValueError("provider status not 200")
        body = response.read(1_500_001)
        if len(body) > 1_500_000:
            raise ValueError("oversized source")
        return json.loads(body), url


def valid_number(x):
    return type(x) in (int, float) and math.isfinite(x) and x > 0


def parse_chart(payload, *, symbol, currency, url):
    try:
        chart = payload["chart"]
        if chart["error"] is not None:
            raise ValueError("provider chart error")
        results = chart["result"]
        if not isinstance(results, list) or len(results) != 1:
            raise ValueError("ambiguous chart results")
        meta = results[0]["meta"]
        if meta["symbol"] != symbol or meta["currency"] != currency:
            raise ValueError("quote identity or currency mismatch")
        if meta.get("instrumentType") != "EQUITY":
            raise ValueError("not a verified equity instrument")
        price, stamp = meta["regularMarketPrice"], meta["regularMarketTime"]
        if not valid_number(price) or type(stamp) is not int:
            raise ValueError("missing market quote")
        at = datetime.fromtimestamp(stamp, timezone.utc)
        if at > datetime.now(timezone.utc):
            raise ValueError("future quote")
        # Yahoo chart uses chartPreviousClose in many live quote payloads;
        # previousClose is absent from those responses.
        prior = meta.get("previousClose")
        if not valid_number(prior):
            prior = meta.get("chartPreviousClose")
        change = round((price / prior - 1) * 100, 3) if valid_number(prior) else None
        return {"status": "observed", "price": float(price), "currency": currency,
                "market_at": at.isoformat(), "change_1d_pct": change,
                "source_url": url, "source": "Yahoo Finance chart"}
    except (KeyError, TypeError, IndexError, ValueError, OverflowError) as exc:
        raise ValueError("unusable quoted market evidence") from exc


def build_brief(universe, *, fetch=get_chart, clock=None):
    markets = validate_universe(universe)
    now = clock or datetime.now(timezone.utc)
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("timezone-aware time required")
    output = {"schema_version": 1, "created_at": now.isoformat(),
              "purpose": "daily market data handoff, not financial advice",
              "midas_tradability_confirmed": False,
              "participation_compliance_confirmed": False,
              "portfolio_positions_included": False, "markets": {}}
    for market in MARKETS:
        rows = []
        for item in markets[market]:
            symbol = item["symbol"]
            try:
                payload, url = fetch(symbol)
                observation = parse_chart(payload, symbol=symbol,
                                          currency=item["currency"], url=url)
                # Observations are recorded even if a session is closed.
                age_seconds = (now - datetime.fromisoformat(observation["market_at"])).total_seconds()
                observation["stale_over_4_days"] = age_seconds > 4 * 86400
                if age_seconds < 0:
                    raise ValueError("future observation")
                delta = observation["change_1d_pct"]
                observation["research_trigger"] = (
                    "price_baseline_missing" if delta is None
                    else "price_move_abs_3pct" if abs(delta) >= 3
                    else "no_price_move_trigger")
            except (ValueError, TypeError, KeyError, HTTPError, URLError, TimeoutError, OSError):
                observation = {"status": "source_unavailable", "price": None,
                               "currency": item["currency"], "market_at": None,
                               "change_1d_pct": None, "source_url": None,
                               "research_trigger": "manual_source_review"}
            rows.append({"symbol": symbol, **observation})
        output["markets"][market] = rows
    return output


def render_markdown(brief):
    lines = ["# Günlük yatırım araştırma veri özeti", "",
             f"Üretim: {brief['created_at']}", "",
             "Bu çıktı yalnızca piyasa gözlemidir. Katılım uygunluğu, Midas erişimi,",
             "yatırım önerisi, işlem emri veya kişisel portföy verisi içermez.", ""]
    for market in MARKETS:
        lines.extend([f"## {market}", "",
                      "| Sembol | Fiyat | 1g değişim | Piyasa zamanı (UTC) | Araştırma tetikleyicisi |",
                      "|---|---:|---:|---|---|"])
        for row in brief["markets"][market]:
            price = (f"{row['price']:.4f} {row['currency']}"
                     if row["price"] is not None else "Veri yok")
            delta = (f"{row['change_1d_pct']:+.3f}%"
                     if row["change_1d_pct"] is not None else "—")
            if row.get("stale_over_4_days"):
                price += " (eski)"
            lines.append(f"| {row['symbol']} | {price} | {delta} | "
                         f"{row['market_at'] or '—'} | {row['research_trigger']} |")
        lines.append("")
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--universe", default="data/analyst/public_research_universe.json")
    parser.add_argument("--output-dir", default="data/analyst-output")
    args = parser.parse_args()
    source = json.loads(Path(args.universe).read_text(encoding="utf-8"))
    brief = build_brief(source)
    directory = Path(args.output_dir)
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "daily-brief.json").write_text(
        json.dumps(brief, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    (directory / "daily-brief.md").write_text(render_markdown(brief), encoding="utf-8")
    counts = {market: sum(row["status"] == "observed" for row in rows)
              for market, rows in brief["markets"].items()}
    print(json.dumps({"observed_by_market": counts}, ensure_ascii=False))


if __name__ == "__main__":
    main()
