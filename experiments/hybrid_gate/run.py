"""Isolated hybrid Google Finance + Yahoo Finance discovery and evidence-gated screening.

Research only. Never treat 'unknown' or model pass as an index certificate.
"""
import argparse
import importlib
import json
import math
import os
from pathlib import Path
import sys
from datetime import datetime, timezone

REGIONS = {
    "ABD": {"countries": ["US"], "suffixes": ["NASDAQ", "NYSE", "NYSEAMERICAN", "NYSEARCA"]},
    "BIST": {"countries": ["TR"], "suffixes": ["IST"]},
    "AVRUPA": {"countries": ["DE", "FR", "GB", "NL", "IT", "ES"], "suffixes": ["ETR", "FRA", "EPA", "LON", "AMS", "BIT", "BME", "SWX"]},
}
SUFFIX = {"IST": ".IS", "ETR": ".DE", "FRA": ".DE", "EPA": ".PA", "LON": ".L",
          "AMS": ".AS", "BIT": ".MI", "BME": ".MC", "SWX": ".SW"}
BLOCK = ("bank", "insurance", "capital market", "credit services", "gambling",
         "casino", "tobacco", "alcohol", "brewer", "distiller", "winery",
         "adult entertainment", "pornograph", "pork", "aerospace & defense")
REQUIRED = ("market_cap", "total_debt", "cash", "short_investments",
            "receivables", "revenue", "interest_income")


def valid_number(x):
    if x is None or isinstance(x, bool):
        return None
    try:
        n = float(x)
        return n if math.isfinite(n) and n >= 0 else None
    except (TypeError, ValueError):
        return None


def map_symbol(quote):
    sym = str(quote.get("symbol") or "")
    if ":" not in sym:
        return None
    ticker, exchange = sym.rsplit(":", 1)
    if not ticker or not exchange:
        return None
    return {"google_symbol": sym, "ticker": ticker, "exchange": exchange,
            "yahoo_symbol": ticker + SUFFIX.get(exchange, ""),
            "name": quote.get("name") or ticker,
            "source": "google_finance"}


def collect_google(base, region, limit):
    import requests
    found, warnings = {}, []
    for country in REGIONS[region]["countries"]:
        for endpoint in ("market-movers", "trending", "search"):
            try:
                params = {"country": country}
                if endpoint == "market-movers":
                    params["limit"] = 50
                elif endpoint == "search":
                    params.update({"query": "a", "limit": 50})
                res = requests.get(base.rstrip("/") + "/" + endpoint, params=params, timeout=35)
                res.raise_for_status()
                payload = res.json()
                if "error" in payload:
                    raise ValueError(str(payload["error"]))
                sections = [payload.get(k, []) for k in ("most_active", "gainers", "losers", "results")]
                for group in sections:
                    if not isinstance(group, list):
                        continue
                    for q in group:
                        if isinstance(q, dict):
                            row = map_symbol(q)
                            if row and row["exchange"] in REGIONS[region]["suffixes"]:
                                found[row["yahoo_symbol"]] = row
            except Exception as exc:
                warnings.append(f"{country}/{endpoint}: {type(exc).__name__}: {str(exc)[:120]}")
    return list(found.values())[:limit], warnings


def collect_yahoo(region, limit):
    import yfinance as yf
    from yfinance import EquityQuery
    out, warnings = [], []
    countries = {"ABD": ["us"], "BIST": ["tr"],
                 "AVRUPA": ["de", "fr", "gb", "nl", "it", "es"]}[region]
    for country in countries:
        try:
            q = EquityQuery("eq", ["region", country])
            payload = yf.screen(q, size=min(limit, 100),
                                sortField="intradaymarketcap", sortAsc=False)
            for x in payload.get("quotes", []):
                symbol = x.get("symbol")
                if symbol and x.get("quoteType") in (None, "EQUITY"):
                    out.append({"yahoo_symbol": symbol, "name": x.get("shortName") or symbol,
                                "source": "yfinance", "exchange": x.get("exchange"),
                                "google_symbol": None})
        except Exception as exc:
            warnings.append(f"yfinance screener {country}: {type(exc).__name__}: {str(exc)[:180]}")
    return out[:limit], warnings


def merge_discovery(google, yahoo):
    merged = {}
    for row in google + yahoo:
        key = row["yahoo_symbol"].upper()
        if key in merged:
            merged[key]["source"] = "google_finance+yfinance"
        else:
            merged[key] = dict(row)
    return list(merged.values())


def from_statement(frame, names):
    if frame is None or frame.empty:
        return None
    for name in names:
        if name in frame.index:
            return valid_number(frame.loc[name].iloc[0])
    return None


def financial_snapshot(t):
    info = t.info or {}
    bs = t.quarterly_balance_sheet
    fin = t.quarterly_income_stmt
    if bs is None or bs.empty:
        bs = t.balance_sheet
    if fin is None or fin.empty:
        fin = t.income_stmt
    def pick(*xs):
        return next((n for x in xs if (n := valid_number(x)) is not None), None)
    snapshot = {
        "market_cap": pick(info.get("marketCap")),
        "total_debt": pick(from_statement(bs, ("Total Debt",)), info.get("totalDebt")),
        "cash": from_statement(bs, ("Cash And Cash Equivalents", "Cash Cash Equivalents And Short Term Investments")),
        "short_investments": from_statement(bs, ("Other Short Term Investments", "Short Term Investments")),
        "receivables": from_statement(bs, ("Receivables", "Accounts Receivable")),
        "revenue": pick(from_statement(fin, ("Total Revenue",)), info.get("totalRevenue")),
        "interest_income": from_statement(fin, ("Interest Income", "Interest Income Non Operating")),
    }
    date = str(bs.columns[0].date()) if bs is not None and not bs.empty else None
    return snapshot, str(info.get("sector") or ""), str(info.get("industry") or ""), date, info


def screen_snapshot(snapshot, sector, industry, engine=None):
    text = (sector + " " + industry).lower()
    if any(x in text for x in BLOCK):
        return {"status": "uygunsuz", "reason": "yasakli_faaliyet", "missing": []}
    if not sector or not industry:
        return {"status": "belirsiz", "reason": "faaliyet_sinifi_eksik", "missing": []}
    missing = [k for k in REQUIRED if snapshot.get(k) is None]
    if missing:
        return {"status": "belirsiz", "reason": "finansal_kanit_eksik", "missing": missing}
    if snapshot["market_cap"] <= 0 or snapshot["revenue"] <= 0:
        return {"status": "belirsiz", "reason": "gecersiz_payda", "missing": []}
    values = {"debt": snapshot["total_debt"] / snapshot["market_cap"],
              "liquidity": (snapshot["cash"] + snapshot["short_investments"]) / snapshot["market_cap"],
              "receivables": snapshot["receivables"] / snapshot["market_cap"],
              "impure_income": snapshot["interest_income"] / snapshot["revenue"]}
    # An installed upstream open-source screening engine is required in live operation.
    if engine is None:
        raise RuntimeError("Open-source compliance adapter not loaded")
    from types import SimpleNamespace
    f = SimpleNamespace(ticker="TEST", name="TEST", sector=sector, industry=industry,
        market_cap=snapshot["market_cap"], total_debt=snapshot["total_debt"],
        cash_and_equivalents=snapshot["cash"], short_term_investments=snapshot["short_investments"],
        accounts_receivable=snapshot["receivables"], total_revenue=snapshot["revenue"],
        interest_income=snapshot["interest_income"], reporting_date="verified_snapshot",
        reporting_period="latest_available", data_source="yfinance",
        market_price_asof="execution_time")
    upstream = engine(f)
    return {"status": "kosullu_gecti" if upstream.is_compliant else "uygunsuz",
            "reason": "acik_kaynak_model", "missing": [], "ratios": values,
            "method": upstream.standard, "upstream_pass": upstream.is_compliant}


def provisional_score(info, annual_return):
    """Test-only score; never a full investment radar score."""
    pe = valid_number(info.get("trailingPE"))
    if pe is None or pe == 0 or annual_return is None or not math.isfinite(annual_return):
        return None
    # Transparent test components. Not a replacement for financial research.
    return round(60 * min(1, 15 / pe) + 40 * max(0, min(1, (annual_return + 0.2) / 0.6)), 2)


def run():
    parser = argparse.ArgumentParser()
    parser.add_argument("--google-base", default="http://127.0.0.1:8000")
    parser.add_argument("--limit-per-region", type=int, default=12)
    parser.add_argument("--output", default="hybrid_gate_output")
    parser.add_argument("--europe-index-csv", help="verified COMPLETE MSCI Europe IMI Islamic roster")
    parser.add_argument("--europe-index-date", help="date in official roster YYYY-MM-DD")
    parser.add_argument("--europe-expected-count", type=int)
    args = parser.parse_args()
    if args.limit_per_region < 1 or args.limit_per_region > 100:
        parser.error("limit must be 1..100")
    import yfinance as yf
    # Clone of MIT project, isolated in runner. Its default missing->zero path is forbidden here.
    sys.path.insert(0, "/tmp/halal-stock-analyst")
    from src.screening import screen_company
    out = Path(args.output); out.mkdir(parents=True, exist_ok=True)
    summary = {"created_utc": datetime.now(timezone.utc).isoformat(),
               "method": "halal-stock-analyst market-cap variant, NOT certified AAOIFI",
               "live_discovery_exhaustive": False,
               "europe_membership_gate": "MSCI Europe IMI Islamic Index",
               "europe_full_roster_verified": official_europe is not None,
               "europe_roster_metadata": official_europe_metadata,
               "markets": {}}
    for region in REGIONS:
        gf, gw = collect_google(args.google_base, region, args.limit_per_region)
        yy, yw = collect_yahoo(region, args.limit_per_region)
        universe = merge_discovery(gf, yy)
        rows = []
        for company in universe:
            row = dict(company, market=region, status="belirsiz",
                       missing=[], reason="henuz_incelenmedi", score=None, snapshot_date=None)
            try:
                t = yf.Ticker(company["yahoo_symbol"])
                snap, sector, industry, date, info = financial_snapshot(t)
                decision = screen_snapshot(snap, sector, industry, screen_company)
                row.update(decision)
                row["snapshot_date"] = date
                if row["status"] == "kosullu_gecti":
                    hist = t.history(period="1y", auto_adjust=True)
                    change = (float(hist["Close"].iloc[-1]) / float(hist["Close"].iloc[0]) - 1) if len(hist) > 1 else None
                    row["score"] = provisional_score(info, change)
                    row["score_type"] = "deneysel_gosterge_asla_yatirim_onayi_degil"
            except Exception as exc:
                row["reason"] = "data_request_error"
                row["error"] = f"{type(exc).__name__}: {str(exc)[:180]}"
            rows.append(row)
        report = {"google_discovered": len(gf), "yfinance_discovered": len(yy),
                  "unique": len(universe), "screened": len(rows),
                  "passed": sum(x["status"] == "kosullu_gecti" for x in rows),
                  "rejected": sum(x["status"] == "uygunsuz" for x in rows),
                  "unknown": sum(x["status"] == "belirsiz" for x in rows),
                  "scored": sum(x.get("score") is not None for x in rows),
                  "warnings": gw + yw}
        summary["markets"][region] = report
        (out / f"{region.lower()}.json").write_text(json.dumps(rows, ensure_ascii=False, indent=2))
        print(json.dumps({"market": region, **report}, ensure_ascii=False), flush=True)
    (out / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2))
    print("SUMMARY", json.dumps(summary, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    run()
