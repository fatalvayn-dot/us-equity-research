"""Prepare a provenance-aware SEC evidence CSV for *manual* MotherDuck staging.

Accepts a Firecrawl Alexandria JSON envelope and uses the independent strict
auditor. Does not contact Firecrawl, the SEC or MotherDuck, and never scores,
approves or imports investments. No secrets or portfolio positions.
"""
import argparse
import csv
from decimal import Decimal, InvalidOperation
import hashlib
import json
import os
from pathlib import Path
import tempfile

from scripts.audit_alexandria_sec_concept import audit_alexandria

FIELDS = (
    "issuer_id", "concept", "taxonomy", "source_url", "accession",
    "period_start", "period_end", "filed_on", "unit", "reported_value",
    "observed_at_ms", "review_state", "source_raw_sha256", "source_system",
)
SOURCE_NAME = "Firecrawl Alexandria / SEC EDGAR"


def _decimal_for_staging(value):
    """Reject values the MotherDuck DECIMAL(38,6) cannot represent exactly."""
    if type(value) not in (int, float):
        raise ValueError("strictly numeric SEC reported value required")
    try:
        amount = Decimal(str(value))
    except InvalidOperation:
        raise ValueError("invalid SEC reported value") from None
    if not amount.is_finite():
        raise ValueError("nonfinite SEC reported value")
    places = max(0, -amount.as_tuple().exponent)
    whole_digits = max(1, amount.adjusted() + 1)
    if places > 6 or whole_digits > 32:
        raise ValueError("value not exactly representable as DECIMAL(38,6)")
    return format(amount, "f")


def staging_rows(payload):
    """Validate original upstream envelope, return deduplicated unapproved rows."""
    audit = audit_alexandria(payload)
    seen = {}
    rows = []
    for result in audit["results"]:
        if result["decision"] != "manual_review_only" or result["source_raw_sha256"] is not None:
            raise ValueError("unexpected SEC audit state")
        for fact in result["facts"]:
            row = {
                "issuer_id": result["issuer_id"],
                "concept": result["concept"],
                "taxonomy": result["taxonomy"],
                "source_url": result["source_url"],
                "accession": fact["accession"],
                "period_start": fact["period_start"] or "",
                "period_end": fact["period_end"],
                "filed_on": fact["filed_on"],
                "unit": fact["unit"],
                "reported_value": _decimal_for_staging(fact["value"]),
                "observed_at_ms": result["observed_at_ms"],
                "review_state": "exact_concept_candidate_unverified",
                "source_raw_sha256": "",
                "source_system": SOURCE_NAME,
            }
            key = tuple(row[k] for k in (
                "issuer_id", "concept", "taxonomy", "accession",
                "period_start", "period_end", "unit", "observed_at_ms"
            ))
            if key in seen:
                if seen[key] != row:
                    raise ValueError("conflicting SEC evidence for the same observation")
                continue
            seen[key] = row
            rows.append(row)
    return rows


def prepare_export(payload, *, csv_path, manifest_path):
    csv_path, manifest_path = Path(csv_path), Path(manifest_path)
    if csv_path.resolve() == manifest_path.resolve():
        raise ValueError("CSV and manifest must use different paths")
    rows = staging_rows(payload)
    if not rows:
        raise ValueError("no audited SEC facts to export")
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", newline="",
                                     dir=csv_path.parent, delete=False) as tmp:
        tmp_name = tmp.name
        writer = csv.DictWriter(tmp, fieldnames=FIELDS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
        tmp.flush()
        os.fsync(tmp.fileno())
    try:
        csv_bytes = Path(tmp_name).read_bytes()
        manifest = {
            "schema_version": 1,
            "report_kind": "manual_motherduck_sec_staging_export",
            "row_count": len(rows),
            "issuers": len({r["issuer_id"] for r in rows}),
            "csv_sha256": hashlib.sha256(csv_bytes).hexdigest(),
            "columns": list(FIELDS),
            "review_state": "exact_concept_candidate_unverified",
            "source_original_sha256_available": False,
            "database_write_performed": False,
            "scoring_performed": False,
            "limitations": [
                "No original SEC response hash, source archive or issuer approval",
                "Not automatically uploaded to MotherDuck or GitHub Actions",
                "Database import requires separately authorized write step",
            ],
        }
        with tempfile.NamedTemporaryFile("w", encoding="utf-8",
                                         dir=manifest_path.parent, delete=False) as meta:
            meta_name = meta.name
            json.dump(manifest, meta, ensure_ascii=False, indent=2)
            meta.write("\n")
            meta.flush()
            os.fsync(meta.fileno())
        os.replace(tmp_name, csv_path)
        os.replace(meta_name, manifest_path)
        return manifest
    finally:
        if os.path.exists(tmp_name):
            os.unlink(tmp_name)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--csv", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    args = parser.parse_args()
    paths = [p.resolve() for p in (args.input, args.csv, args.manifest)]
    if len(set(paths)) != 3:
        parser.error("input, CSV and manifest paths must be distinct")
    payload = json.loads(args.input.read_text(encoding="utf-8"))
    result = prepare_export(payload, csv_path=args.csv, manifest_path=args.manifest)
    print(json.dumps({
        "row_count": result["row_count"],
        "csv_sha256": result["csv_sha256"],
        "database_write_performed": False,
    }))


if __name__ == "__main__":
    main()
