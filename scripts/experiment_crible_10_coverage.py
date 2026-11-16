#!/usr/bin/env python3
"""Crible published snapshot coverage check; read-only, no trading and no eligibility filters."""
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

SYMBOLS = ["BAC", "AMAT", "PGR", "APH", "AMGN", "WELL", "SPGI", "TMO", "SCHW", "AAPL"]
GROUPS = {
    "income": ["revenue", "net_income", "operating_income", "gross_profit"],
    "balance": ["total_assets", "total_liabilities", "total_debt", "total_equity", "current_assets", "current_liabilities"],
    "cashflow": ["operating_cash_flow", "capital_expenditure", "free_cash_flow"],
    "market": ["price", "market_cap", "shares_outstanding", "price_to_earnings_ratio", "price_to_book_ratio"],
    "analysis": ["return_on_equity", "altman_z", "piotroski_f", "composite_rank"],
}
ALIASES = {
    "revenue": ["total_revenue", "revenue"],
    "net_income": ["net_income"],
    "operating_income": ["operating_income"],
    "gross_profit": ["gross_profit"],
    "total_assets": ["total_assets"],
    "total_liabilities": ["total_liabilities"],
    "total_debt": ["total_debt"],
    "total_equity": ["stockholders_equity", "total_equity"],
    "current_assets": ["current_assets", "total_current_assets"],
    "current_liabilities": ["current_liabilities", "total_current_liabilities"],
    "operating_cash_flow": ["operating_cashflow", "operating_cash_flow"],
    "capital_expenditure": ["capital_expenditure", "capital_expenditures"],
    "free_cash_flow": ["free_cash_flow"],
    "price": ["price", "last_price", "close"],
    "market_cap": ["market_cap", "market_capitalization"],
    "shares_outstanding": ["shares_outstanding", "ordinary_shares_number"],
    "price_to_earnings_ratio": ["price_to_earnings_ratio"],
    "price_to_book_ratio": ["price_to_book_ratio"],
    "return_on_equity": ["return_on_equity", "roe"],
    "altman_z": ["altman_z"],
    "piotroski_f": ["piotroski_f"],
    "composite_rank": ["composite_rank"],
}
def call(*args):
    p = subprocess.run(["crible", *args], capture_output=True, text=True, timeout=120)
    if p.returncode:
        raise RuntimeError(f"crible exit={p.returncode}: {p.stderr[-1000:]}")
    return json.loads(p.stdout)

def main():
    data_dir = sys.argv[1]
    query = "symbol IN (" + ",".join("'" + s + "'" for s in SYMBOLS) + ")"
    result = call("--data-dir", data_dir, "screen", query, "--format", "json", "--limit", "100")
    status = call("--data-dir", data_dir, "status")
    rows = {str(x.get("symbol", "")).upper(): x for x in result.get("rows", [])}
    output = {"test_date_utc": datetime.now(timezone.utc).isoformat(), "source": "Crible published snapshot",
              "data_dir": data_dir, "requested": SYMBOLS, "matched": len(rows), "snapshot_status": status,
              "companies": [], "warning": "Coverage of a published snapshot, not live verified per-field SEC evidence."}
    for symbol in SYMBOLS:
        row = rows.get(symbol)
        item = {"symbol": symbol, "found": row is not None}
        if row is not None:
            item.update({"period": row.get("period"), "provider": row.get("provider"),
                         "sector": row.get("sector"), "region": row.get("region")})
            for group, fields in GROUPS.items():
                vals = {}
                for field in fields:
                    aliases = ALIASES[field]
                    present = [a for a in aliases if a in row]
                    vals[field] = {"state": ("schema_missing" if not present else
                                    "value_missing" if all(row[a] is None for a in present) else "available"),
                                   "source_column": next((a for a in present if row[a] is not None), present[0] if present else None),
                                   "value": next((row[a] for a in present if row[a] is not None), None)}
                item[group] = vals
        output["companies"].append(item)
    Path("crible_10_coverage.json").write_text(json.dumps(output, indent=2, default=str, ensure_ascii=False))
    headings = list(GROUPS)
    lines = ["# Crible - 10 şirket veri kapsamı", "",
             "Kaynak: Crible yayımlanmış veri paketi. Eksik alanlar uydurulmamıştır.", "",
             "| Sembol | Var mı | Dönem | " + " | ".join(headings) + " |",
             "|---|---|---|" + "|".join(["---"] * len(headings)) + "|"]
    for item in output["companies"]:
        counts = []
        for g in headings:
            if not item["found"]:
                counts.append("—")
            else:
                fs = item[g]
                counts.append(f"{sum(v['state']=='available' for v in fs.values())}/{len(fs)}")
        lines.append(f"| {item['symbol']} | {'Evet' if item['found'] else 'Hayır'} | {item.get('period') or '—'} | " + " | ".join(counts) + " |")
    lines += ["", "Alan bazında gerçek değerler ve şema eksiklikleri JSON dosyasındadır.",
              "Dönem ve kaynak etiketi, tekil alanların aynı tarihte doğrulandığını kanıtlamaz."]
    Path("crible_10_coverage.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))
if __name__ == "__main__":
    main()
