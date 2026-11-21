"""Read-only comparison of Crible snapshot coverage against existing audited radar fields.

Crible coverage does not contain filing-level evidence; emit candidates for
verification rather than accepting them as Fact objects or recalculating ratios.
No third-party code or runtime dependency is imported here.
"""
from collections import Counter
from html import unescape
from pathlib import Path
import json
import re

FIELDS = {
    "revenue": "Vergiler hariç müşteri sözleşmesi hasılatı",
    "net_income": "Net dönem kârı / zararı (NetIncomeLoss)",
    "total_assets": "Toplam varlıklar",
    "total_liabilities": "Toplam yükümlülükler",
    "operating_cashflow": "Faaliyetlerden nakit akışı",
    "capital_expenditure": "Maddi duran varlık alım ödemeleri",
}
ARTICLE = re.compile(r"<article\b[^>]*>\s*<h2>([A-Z0-9.]+)\s*<small.*?</article>", re.S)
ROW = re.compile(r"<tr>\s*<td>(.*?)</td>\s*<td>(.*?)</td>\s*<td>", re.S)
TAGS = re.compile(r"<[^>]*>")


def plain(text):
    return unescape(TAGS.sub("", text)).strip()


def read_radar_coverage(html):
    results = {}
    for article in ARTICLE.finditer(html):
        symbol = article.group(1)
        if symbol in results:
            raise ValueError("duplicate radar symbol")
        rows = {}
        for row in ROW.finditer(article.group(0)):
            label, value = plain(row.group(1)), plain(row.group(2))
            for field, expected in FIELDS.items():
                if label == expected:
                    if field in rows:
                        raise ValueError("duplicate radar field")
                    rows[field] = value != "Mevcut değil" and bool(value)
        if set(rows) != set(FIELDS):
            raise ValueError(f"radar field schema mismatch: {symbol}")
        results[symbol] = rows
    if not results:
        raise ValueError("no radar companies")
    return results


def compare(radar, crible):
    symbols, records = crible.get("symbols"), crible.get("records")
    if crible.get("status") != "complete" or not isinstance(symbols, list) or not isinstance(records, list):
        raise ValueError("incomplete Crible run")
    if len(set(symbols)) != len(symbols) or len(symbols) != len(records) or set(symbols) != set(radar):
        raise ValueError("different candidate universe")
    lookup = {r["symbol"]: r for r in records}
    if set(lookup) != set(symbols):
        raise ValueError("duplicate or missing snapshot symbol")
    totals = {k: Counter() for k in FIELDS}
    candidates = []
    for symbol in symbols:
        record = lookup[symbol]
        statuses = record.get("field_status", {}).get("financial", {})
        for field in FIELDS:
            status = statuses.get(field)
            if status not in ("available", "missing", "not_in_schema", "not_in_snapshot"):
                raise ValueError(f"unexpected field status {symbol}/{field}: {status}")
            have = bool(radar[symbol][field])
            vendor = status == "available" and record.get("in_snapshot") is True
            counts = totals[field]
            counts["radar"] += have
            counts["crible"] += vendor
            counts["union"] += have or vendor
            if vendor and not have:
                counts["candidate"] += 1
                candidates.append({"symbol": symbol, "field": field, "state": "unverified_candidate",
                                   "period_hint": record.get("period"),
                                   "reason": "Original report period, issuer and accounting concept unverified"})
    return {"companies": len(symbols),
            "fields": {k: {metric: v[metric] for metric in ("radar","crible","union","candidate")}
                       for k,v in totals.items()},
            "candidate_count": len(candidates), "verification_queue": candidates,
            "accepted_facts": 0, "status": "diagnostic_only"}


def audit(radar_html, crible_json):
    radar = read_radar_coverage(Path(radar_html).read_text(encoding="utf-8"))
    snapshot = json.loads(Path(crible_json).read_text(encoding="utf-8"))
    return compare(radar, snapshot)
