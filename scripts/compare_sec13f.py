"""SEC Form 13F XML information table comparison; no live scraping or trade signals.

Accepts separately sourced filing metadata and raw information-table XML.
The public filing date, NOT quarter-end, is the earliest usable observation.
"""
import argparse
import json
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path
from xml.etree import ElementTree

MAX_BYTES = 12_000_000
MAX_ROWS = 30_000


def date_value(value):
    if not isinstance(value, str):
        raise ValueError("filing date required")
    return date.fromisoformat(value)


def local(tag):
    return tag.rsplit("}", 1)[-1]


def field(parent, name):
    for node in parent:
        if local(node.tag) == name:
            return (node.text or "").strip()
    return ""


def decimal_positive(value):
    try:
        number = Decimal(value)
    except (InvalidOperation, TypeError):
        raise ValueError("invalid positive numeric field") from None
    if not number.is_finite() or number <= 0:
        raise ValueError("invalid positive numeric field")
    return number


def parse_info_table(xml_bytes):
    if not isinstance(xml_bytes, bytes) or not 0 < len(xml_bytes) <= MAX_BYTES:
        raise ValueError("invalid 13F document size")
    upper = xml_bytes.upper()
    if b"<!DOCTYPE" in upper or b"<!ENTITY" in upper:
        raise ValueError("external entity declarations forbidden")
    root = ElementTree.fromstring(xml_bytes)
    if local(root.tag) != "informationTable":
        raise ValueError("not a SEC informationTable")
    holdings = {}
    rows = 0
    excluded_derivatives = 0
    for row in root:
        if local(row.tag) != "infoTable":
            continue
        rows += 1
        if rows > MAX_ROWS:
            raise ValueError("too many 13F holdings")
        cusip = field(row, "cusip").upper()
        issuer = field(row, "nameOfIssuer")
        if len(cusip) != 9 or not cusip.isalnum() or not issuer:
            raise ValueError("invalid issuer or CUSIP")
        amount_group = next((n for n in row if local(n.tag) == "shrsOrPrnAmt"), None)
        if amount_group is None:
            raise ValueError("missing share group")
        share_type = field(amount_group, "sshPrnamtType").upper()
        # Only plain long share exposures; excludes options and debt/principal units.
        if field(row, "putCall") or share_type != "SH":
            excluded_derivatives += 1
            continue
        shares = decimal_positive(field(amount_group, "sshPrnamt"))
        value_thousands = decimal_positive(field(row, "value"))
        if cusip in holdings:
            # Multiple voting authority/discretion rows may represent one security.
            if holdings[cusip]["issuer"] != issuer:
                raise ValueError("CUSIP mapped to conflicting issuer names")
            holdings[cusip]["shares"] += shares
            holdings[cusip]["value_usd_thousands"] += value_thousands
        else:
            holdings[cusip] = {"issuer": issuer, "cusip": cusip, "shares": shares,
                               "value_usd_thousands": value_thousands}
    if rows == 0:
        raise ValueError("empty 13F information table")
    return holdings, {"raw_rows": rows, "excluded_non_plain_shares": excluded_derivatives}


def compare(prior_metadata, prior_xml, current_metadata, current_xml, *, as_of):
    cutoff = date_value(as_of)
    required = ("manager_cik", "period_end", "filed_on", "accession", "source_url")
    for meta in (prior_metadata, current_metadata):
        if not isinstance(meta, dict) or any(not meta.get(k) for k in required):
            raise ValueError("missing original filing provenance")
        if not (str(meta["manager_cik"]).isdigit() and len(str(meta["manager_cik"])) <= 10):
            raise ValueError("invalid manager CIK")
        if not str(meta["source_url"]).startswith("https://www.sec.gov/Archives/edgar/data/"):
            raise ValueError("original SEC filing link required")
        if date_value(meta["period_end"]) > date_value(meta["filed_on"]):
            raise ValueError("filing before holdings period")
        if date_value(meta["filed_on"]) > cutoff:
            raise ValueError("future or unpublished SEC filing")
    if str(prior_metadata["manager_cik"]).zfill(10) != str(current_metadata["manager_cik"]).zfill(10):
        raise ValueError("cannot compare different managers")
    if date_value(prior_metadata["period_end"]) >= date_value(current_metadata["period_end"]):
        raise ValueError("filing periods out of order")
    old, old_count = parse_info_table(prior_xml)
    new, new_count = parse_info_table(current_xml)
    changes = []
    for cusip in sorted(old.keys() | new.keys()):
        p, c = old.get(cusip), new.get(cusip)
        before = p["shares"] if p else Decimal(0)
        after = c["shares"] if c else Decimal(0)
        if after == before:
            continue
        change = after - before
        changes.append({
            "cusip": cusip, "issuer": (c or p)["issuer"],
            "prior_shares": str(before), "current_shares": str(after),
            "delta_shares": str(change),
            "change_type": "new" if not p else "exited" if not c else "increased" if change > 0 else "decreased",
            "investment_eligibility": "unverified",
            "investment_action": None,
        })
    return {
        "schema_version": 1, "manager_cik": str(current_metadata["manager_cik"]).zfill(10),
        "prior_period_end": prior_metadata["period_end"],
        "current_period_end": current_metadata["period_end"],
        "first_usable_on": current_metadata["filed_on"],
        "as_of": as_of, "source_urls": [prior_metadata["source_url"], current_metadata["source_url"]],
        "changes": changes, "counts": {"prior": old_count, "current": new_count},
        "limitations": ["13F is delayed; publication date is not trade date",
                        "Share change is not performance, transaction cost or buy/sell recommendation",
                        "13F lacks short positions and full fund exposures",
                        "CUSIP requires verified mapping; participation compliance not checked",
                        "Amended/confidential filings require separate temporal reconciliation"],
    }


def main():
    cli = argparse.ArgumentParser(description="SEC 13F published snapshot comparison (offline)")
    cli.add_argument("--prior-meta", required=True)
    cli.add_argument("--prior-xml", required=True)
    cli.add_argument("--current-meta", required=True)
    cli.add_argument("--current-xml", required=True)
    cli.add_argument("--as-of", required=True)
    cli.add_argument("--output", required=True)
    args = cli.parse_args()
    result = compare(
        json.loads(Path(args.prior_meta).read_text(encoding="utf-8")),
        Path(args.prior_xml).read_bytes(),
        json.loads(Path(args.current_meta).read_text(encoding="utf-8")),
        Path(args.current_xml).read_bytes(), as_of=args.as_of)
    Path(args.output).write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"changes": len(result["changes"]), "first_usable_on": result["first_usable_on"]}))


if __name__ == "__main__":
    main()
