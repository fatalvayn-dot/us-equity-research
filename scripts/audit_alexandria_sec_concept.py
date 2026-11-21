"""Read-only audit bridge for Firecrawl Alexandria -> SEC companyconcept evidence.

This does not call paid APIs, mutate the production financial archive,
approve an instrument, or supply any input to the scoring resolver.
Only exact SEC identity, taxonomy, concept and original filing references
are accepted as diagnostic *candidates*, not verified financial facts.
"""
import argparse
from datetime import date
import json
from pathlib import Path
import re

CIK_RE = re.compile(r"[0-9]{10}\Z")
CONCEPT_RE = re.compile(r"[A-Za-z0-9_]{1,200}\Z")
ACCESSION_RE = re.compile(r"[0-9]{10}-[0-9]{2}-[0-9]{6}\Z")
TAXONOMIES = {"us-gaap", "dei", "ifrs-full", "srt"}


def _iso_date(value):
    if not isinstance(value, str):
        raise ValueError("SEC date must be a string")
    stamp = date.fromisoformat(value)
    if value != stamp.isoformat():
        raise ValueError("noncanonical SEC date")
    return stamp


def _extract_items(payload):
    if not isinstance(payload, dict):
        raise ValueError("Alexandria response must be a JSON object")
    root = payload.get("data", payload)
    if not isinstance(root, dict):
        raise ValueError("invalid Alexandria data object")
    items = root.get("alexandria")
    if not isinstance(items, list) or not items:
        raise ValueError("nonempty Alexandria results required")
    return items


def audit_alexandria(payload):
    """Produce an audit-only report with no approval or fabricated scores."""
    results = []
    for item in _extract_items(payload):
        if not isinstance(item, dict) or (
            item.get("provider"), item.get("capability")
        ) != ("sec-gov", "filings/concept"):
            raise ValueError("only SEC companyconcept results are supported")
        data = item.get("data")
        if not isinstance(data, dict):
            raise ValueError("SEC result body missing")
        cik, concept, taxonomy = (
            data.get("cik"), data.get("concept"), data.get("taxonomy")
        )
        if not isinstance(cik, str) or not CIK_RE.fullmatch(cik) or int(cik) == 0:
            raise ValueError("canonical nonzero CIK required")
        if not isinstance(concept, str) or not CONCEPT_RE.fullmatch(concept):
            raise ValueError("exact XBRL concept required")
        if taxonomy not in TAXONOMIES:
            raise ValueError("unsupported taxonomy")
        source_url = (
            f"https://data.sec.gov/api/xbrl/companyconcept/"
            f"CIK{cik}/{taxonomy}/{concept}.json"
        )
        if data.get("source_url") != source_url:
            raise ValueError("noncanonical or mismatched SEC source URL")
        observed = data.get("observed_at_ms")
        if type(observed) is not int or observed <= 0:
            raise ValueError("SEC observation timestamp required")
        facts = data.get("facts")
        if not isinstance(facts, list) or data.get("count") != len(facts):
            raise ValueError("SEC row count mismatch")
        rows = []
        for fact in facts:
            if not isinstance(fact, dict):
                raise ValueError("SEC fact must be an object")
            accession = fact.get("accession_number")
            if not isinstance(accession, str) or not ACCESSION_RE.fullmatch(accession):
                raise ValueError("source filing accession required")
            if accession[:10] != cik:
                raise ValueError("SEC accession does not match issuer")
            if fact.get("form") not in ("10-K", "10-K/A", "10-Q", "10-Q/A"):
                raise ValueError("unsupported SEC filing form")
            end, filed = _iso_date(fact.get("end")), _iso_date(fact.get("filed"))
            if end > filed:
                raise ValueError("filing predates its reporting period")
            start = fact.get("start")
            if start is not None and _iso_date(start) > end:
                raise ValueError("duration starts after it ends")
            unit = fact.get("unit")
            value = fact.get("value")
            if not isinstance(unit, str) or not unit or type(value) not in (int, float):
                raise ValueError("unit and numeric value required")
            if type(value) is float and (value != value or abs(value) == float("inf")):
                raise ValueError("nonfinite SEC value")
            rows.append({
                "accession": accession, "form": fact["form"],
                "period_start": start, "period_end": fact["end"],
                "filed_on": fact["filed"], "unit": unit, "value": value,
                "review_state": "exact_concept_candidate_unverified",
            })
        results.append({
            "issuer_id": cik, "concept": concept, "taxonomy": taxonomy,
            "source_url": source_url, "observed_at_ms": observed,
            "facts": rows, "decision": "manual_review_only",
            "source_raw_sha256": None,
        })
    return {
        "schema_version": 1, "report_kind": "alexandria_sec_concept_audit",
        "source": "Firecrawl Alexandria / SEC EDGAR",
        "results": results, "scored_companies": 0,
        "investment_approved": False,
        "limitations": [
            "Third-party extracted values; original SEC response hash is not supplied",
            "Exact concept/period/unit requires independent source-archive match",
            "No integration into Yahoo > SEC > Nasdaq > Finnhub first-valid resolver",
            "No source archive, portfolio holdings or credentials written",
        ],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.input.resolve() == args.output.resolve():
        parser.error("source and output must be different files")
    report = audit_alexandria(json.loads(args.input.read_text(encoding="utf-8")))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
