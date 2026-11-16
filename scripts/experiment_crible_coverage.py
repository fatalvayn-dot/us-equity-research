#!/usr/bin/env python3
"""Independent Crible snapshot availability test; never changes radar data."""
import json
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path

SYMBOLS = ["BAC", "AMAT", "PGR", "APH", "AMGN", "WELL", "SPGI", "TMO", "SCHW", "AAPL"]
FIELDS = {
    "financial": ["total_revenue", "net_income", "total_assets", "total_liabilities", "operating_cash_flow", "capital_expenditure", "total_debt"],
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
        result["records"].append({
            "symbol": symbol,
            "in_snapshot": row is not None,
            "period": row.get("period") if row else None,
            "field_status": fielddata,
        })
    result["status"] = "complete"
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
    print(json.dumps({k: result[k] for k in ("status", "symbols")}, ensure_ascii=False))
    if result["status"] != "complete":
        raise SystemExit(1)
