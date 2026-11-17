#!/usr/bin/env python3
"""Independent Crible snapshot availability test; never changes radar data."""
import json
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path

SYMBOLS = ["NVDA","AAPL","MSFT","GOOGL","AMZN","AVGO","META","TSLA","LLY","MU","WMT","AMD","JPM","JNJ","MA","ABBV","INTC","PLTR","CVX","COST","CSCO","ORCL","KO","PG","UNH","MRK","BAC","AMAT","HD","PM","GE","LRCX","PANW","DELL","MS","CAT","TXN","RY","GS","RTX","CRWD","TMO","NFLX","AMGN","GEV","ANET","LIN","KLAC","AXP","ADI","GILD","APH","QCOM","SNDK","MRVL","CRM","PEP","BLK","MCD","ABT","COP","UNP","DE","NEE","WELL","PFE","DHR","ACN","SCCO","STX","TMUS","ISRG","TJX","SCHW","ETN","LMT","WDC","CB","VRTX","BA","UBER","PGR","SPGI","ADBE","INTU","NOW","SNPS","CDNS","FTNT","WDAY","ADSK","ROP","MCHP","MPWR","ON","SWKS","NTAP","AKAM","FFIV","TYL"]
FIELDS = {
    "financial": ["revenue", "net_income", "total_assets", "total_liabilities", "operating_cashflow", "capital_expenditure", "total_debt"],
    "market": ["price", "market_cap", "shares_outstanding", "price_to_earnings_ratio", "price_to_book_ratio"],
    "scoring": ["sector", "piotroski_f", "altman_z", "composite_rank"],
}
OUT = Path("crible_coverage")
OUT.mkdir(exist_ok=True)

def run(*args, timeout=900):
    return subprocess.run(args, capture_output=True, text=True, timeout=timeout, check=True)

result = {
    "checked_at_utc": datetime.now(timezone.utc).isoformat(),
    "symbols": SYMBOLS,
    "status": "not_run",
    "source": "crible published snapshot, not a direct live quote",
    "fields_requested": FIELDS,
    "field_mapping_correction": {"total_revenue": "revenue", "operating_cash_flow": "operating_cashflow"},
    "price_note": "Snapshot lacks direct price field under tested name; derived price is diagnostic only.",
    "records": [],
}
try:
    command = os.environ.get("CRIBLE_COMMAND", "crible")
    data_dir = str(OUT / "data")
    bootstrap = run(command, "--data-dir", data_dir, "bootstrap", timeout=1200)
    (OUT / "bootstrap_stdout.txt").write_text(bootstrap.stdout[-30000:], encoding="utf-8")
    fields = json.loads(run(command, "--data-dir", data_dir, "fields", "--format", "json").stdout)
    fieldnames = {v["name"] for v in fields}
    query = "symbol IN (" + ",".join("'" + s + "'" for s in SYMBOLS) + ")"
    raw = json.loads(run(command, "--data-dir", data_dir, "screen", query, "--format", "json", "--limit", "100").stdout)
    found = {r.get("symbol"): r for r in raw["rows"]}
    for symbol in SYMBOLS:
        row = found.get(symbol)
        fielddata = {}
        for section, names in FIELDS.items():
            fielddata[section] = {
                name: ("not_in_schema" if name not in fieldnames else
                       "not_in_snapshot" if row is None else
                       "missing" if row.get(name) is None else "available")
                for name in names
            }
        derived_price = None
        if row is not None and isinstance(row.get("market_cap"), (int, float)) and isinstance(row.get("shares_outstanding"), (int, float)) and row["shares_outstanding"] > 0:
            derived_price = row["market_cap"] / row["shares_outstanding"]
        result["records"].append({
            "symbol": symbol,
            "in_snapshot": row is not None,
            "period": row.get("period") if row else None,
            "price_asof": row.get("price_asof") if row else None,
            "provider": row.get("provider") if row else None,
            "price_derived_from_cap_and_shares_unverified": derived_price,
            "field_status": fielddata,
        })
    result["status"] = "complete"
    result["by_field"] = {section: {name: {"available": sum(r["field_status"][section][name] == "available" for r in result["records"]), "count": len(SYMBOLS)} for name in names} for section, names in FIELDS.items()}
    result["count_in_snapshot"] = sum(r["in_snapshot"] for r in result["records"])
    result["field_count_available"] = sum(
        status == "available"
        for record in result["records"]
        for section in record["field_status"].values()
        for status in section.values()
    )
except Exception as exc:
    result["status"] = "failed"
    result["error"] = str(exc)[:1500]
finally:
    (OUT / "coverage.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({k: result[k] for k in ("status", "symbols", "count_in_snapshot", "field_count_available") if k in result}, ensure_ascii=False))
    if result["status"] != "complete":
        raise SystemExit(1)
