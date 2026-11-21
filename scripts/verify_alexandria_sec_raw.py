"""Reconcile Firecrawl SEC concept observations with raw original SEC JSON bytes.

No network calls, database writes, scores, or provider-order changes. Original
companyconcept JSON files are supplied locally and remain outside public git.
The report records SHA256 of original bytes and exact row-level matches.
"""
import argparse
from decimal import Decimal
import hashlib
import json
from pathlib import Path

from scripts.audit_alexandria_sec_concept import audit_alexandria


def _value(value):
    if type(value) not in (int, float):
        raise ValueError("SEC value must be numeric")
    out = Decimal(str(value))
    if not out.is_finite():
        raise ValueError("nonfinite SEC value")
    return out


def _raw_path(raw_dir, item):
    """Exact validated CIK/taxonomy/concept; no user supplied file paths."""
    return raw_dir / (
        item["issuer_id"] + "_" + item["taxonomy"] + "_" + item["concept"] + ".json"
    )


def verify_raw_sources(alexandria, raw_dir):
    report = audit_alexandria(alexandria)
    results = []
    for item in report["results"]:
        path = _raw_path(Path(raw_dir), item)
        raw = path.read_bytes()
        document = json.loads(raw)
        cik = document.get("cik")
        if isinstance(cik, bool) or str(cik).zfill(10) != item["issuer_id"]:
            raise ValueError("raw SEC issuer does not match Alexandria CIK")
        if (document.get("taxonomy") != item["taxonomy"]
                or document.get("tag") != item["concept"]
                or not isinstance(document.get("units"), dict)):
            raise ValueError("raw SEC taxonomy or XBRL concept mismatch")
        for fact in item["facts"]:
            original = document["units"].get(fact["unit"])
            if not isinstance(original, list):
                raise ValueError("SEC unit not found in raw document")
            matching = [
                row for row in original
                if isinstance(row, dict)
                and row.get("accn") == fact["accession"]
                and row.get("form") == fact["form"]
                and row.get("start") == fact["period_start"]
                and row.get("end") == fact["period_end"]
                and row.get("filed") == fact["filed_on"]
            ]
            if len(matching) != 1 or _value(matching[0].get("val")) != _value(fact["value"]):
                raise ValueError("SEC original filing fact mismatch or ambiguity")
        results.append({
            "issuer_id": item["issuer_id"],
            "taxonomy": item["taxonomy"],
            "concept": item["concept"],
            "source_url": item["source_url"],
            "source_raw_sha256": hashlib.sha256(raw).hexdigest(),
            "matched_rows": len(item["facts"]),
            "decision": "raw_sec_bytes_matched_not_approved",
        })
    return {
        "schema_version": 1,
        "report_kind": "firecrawl_original_sec_companyconcept_reconciliation",
        "sources": results,
        "verified_source_count": len(results),
        "scored_companies": 0,
        "investment_approved": False,
        "notes": [
            "Original SEC files were supplied locally and are not included in output",
            "No proof of when original raw files were fetched unless separately archived",
            "Matching facts are candidates only; scope, finance and participation gates remain separate",
        ],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--alexandria", required=True, type=Path)
    parser.add_argument("--sec-raw-dir", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    if args.output.resolve() == args.alexandria.resolve():
        parser.error("input and output paths must differ")
    payload = json.loads(args.alexandria.read_text(encoding="utf-8"))
    result = verify_raw_sources(payload, args.sec_raw_dir)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "verified_source_count": result["verified_source_count"],
        "scored_companies": 0,
    }))


if __name__ == "__main__":
    main()
