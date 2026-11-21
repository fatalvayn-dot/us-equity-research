"""Optional SEC CompanyConcept original-byte gate for the *existing* score batch.

Never adds a fact, score point, trading permission or provider source.
Original raw source, SHA, issuer, exact filing and reporting period are verified
before a selected existing liability operand can be corroborated.
"""
from datetime import datetime
from decimal import Decimal, InvalidOperation
import hashlib
import json
from pathlib import Path
import re

CIK = re.compile(r"[0-9]{10}\Z")
ACCESSION = re.compile(r"[0-9]{10}-[0-9]{2}-[0-9]{6}\Z")
SHA256 = re.compile(r"[0-9a-f]{64}\Z")


def _number(value):
    if type(value) not in (str, int, float, Decimal):
        raise ValueError("numeric evidence required")
    try:
        n = Decimal(str(value))
    except (InvalidOperation, TypeError):
        raise ValueError("invalid SEC numeric evidence") from None
    if not n.is_finite():
        raise ValueError("nonfinite SEC value")
    return n


def verify_stage1_artifact(artifact, raw_dir, *, as_of):
    """Recompute SHA and exact original SEC SEC-GAAP row for every record."""
    if not isinstance(artifact, dict) or artifact.get("schema_version") != 1 or (
        artifact.get("report_kind") != "stage1_live_sec_original_replay" or
        artifact.get("replay_identical") is not True or
        artifact.get("replay_runs") != 2 or
        artifact.get("score_inputs_changed") is not False or
        artifact.get("investment_approved") is not False
    ):
        raise ValueError("stage-one replay and no-trade contract required")
    stamped = datetime.fromisoformat(artifact["fetched_at"].replace("Z", "+00:00"))
    if (stamped.tzinfo is None or stamped.utcoffset() is None or
            stamped > as_of):
        raise ValueError("future or unqualified SEC fetch time")
    records = artifact.get("records")
    if not isinstance(records, list) or len(records) != 2 or (
        artifact.get("verified_source_count") != 2 or
        artifact.get("verified_record_count") != 2
    ):
        raise ValueError("two complete verified SEC source records required")
    checked = {}
    for record in records:
        if not isinstance(record, dict):
            raise ValueError("invalid SEC record")
        cik = record.get("issuer_id")
        if not isinstance(cik, str) or not CIK.fullmatch(cik) or int(cik) == 0:
            raise ValueError("invalid SEC issuer")
        if record.get("taxonomy") != "us-gaap" or record.get("concept") != "Liabilities":
            raise ValueError("wrong XBRL concept")
        url = f"https://data.sec.gov/api/xbrl/companyconcept/CIK{cik}/us-gaap/Liabilities.json"
        if record.get("source_url") != url or cik in checked:
            raise ValueError("duplicate or mismatched official SEC URL")
        acc = record.get("accession")
        if not isinstance(acc, str) or not ACCESSION.fullmatch(acc) or acc[:10] != cik:
            raise ValueError("invalid filing accession")
        if (record.get("unit") != "USD" or record.get("form") != "10-K"
                or record.get("period_start") is not None or
                record.get("review_state") != "source_verified"
                or record.get("investment_approved") is not False):
            raise ValueError("SEC evidence unit/form/state not approved")
        digest = record.get("source_raw_sha256")
        if not isinstance(digest, str) or not SHA256.fullmatch(digest):
            raise ValueError("missing source SHA-256")
        path = Path(raw_dir) / f"{cik}_us-gaap_Liabilities.json"
        # Explicit filename only; reject path tricks and symlink inputs.
        if path.is_symlink() or not path.is_file():
            raise ValueError("immutable SEC raw evidence absent")
        raw = path.read_bytes()
        if not raw or len(raw) > 16_000_000 or hashlib.sha256(raw).hexdigest() != digest:
            raise ValueError("SEC raw response bytes SHA-256 mismatch")
        if record.get("source_original_bytes") != len(raw):
            raise ValueError("original SEC byte length mismatch")
        payload = json.loads(raw)
        if (str(payload.get("cik")).zfill(10) != cik or
                payload.get("taxonomy") != "us-gaap" or
                payload.get("tag") != "Liabilities"):
            raise ValueError("original SEC concept identity mismatch")
        if record.get("filed_on") > as_of.date().isoformat():
            raise ValueError("SEC filing is future relative to score")
        original = payload.get("units", {}).get("USD")
        if not isinstance(original, list):
            raise ValueError("original SEC USD unit not found")
        matches = [row for row in original if isinstance(row, dict)
                   and row.get("accn") == acc
                   and row.get("form") == "10-K"
                   and row.get("start") is None
                   and row.get("end") == record.get("period_end")
                   and row.get("filed") == record.get("filed_on")]
        if (len(matches) != 1 or
                _number(matches[0].get("val")) != _number(record.get("reported_value"))):
            raise ValueError("original SEC filed fact conflict or ambiguity")
        checked[cik] = record
    return checked


def guard_selected_batch(financial_batch, raw_dir, artifact, *, as_of):
    """Read-only corroboration: never overwrite upstream selected facts."""
    verified = verify_stage1_artifact(artifact, raw_dir, as_of=as_of)
    if not isinstance(financial_batch, dict) or not isinstance(financial_batch.get("companies"), list):
        raise ValueError("original financial batch required")
    checked = 0
    no_overlap = []
    for company in financial_batch["companies"]:
        cik = company.get("issuer_id")
        if cik not in verified:
            continue
        source = verified[cik]
        overlaps = [
            field["fact"]
            for field in company.get("fields", [])
            if isinstance(field, dict) and
               isinstance(field.get("query"), dict) and
               field["query"].get("field") == "liabilities" and
               isinstance(field.get("fact"), dict) and
               field["fact"].get("filing_accession") == source["accession"] and
               field["fact"].get("period_end") == source["period_end"]
        ]
        if len(overlaps) > 1:
            raise ValueError("ambiguous selected liability facts")
        if overlaps:
            fact = overlaps[0]
            if (fact.get("accounting_definition") != "us-gaap:Liabilities" or
                    fact.get("currency") != "USD" or
                    fact.get("period_start") is not None or
                    _number(fact.get("value")) != _number(source["reported_value"])):
                raise ValueError("selected financial batch conflicts with official SEC liabilities")
            checked += 1
        else:
            no_overlap.append(cik)
    return {
        "status": "supplemental_source_corroboration_only",
        "verified_sec_original_sources": len(verified),
        "selected_financial_fact_matches": checked,
        "issuer_period_not_selected": sorted(no_overlap),
        "financial_facts_substituted": 0,
        "provider_order_changed": False,
        "scoring_weights_changed": False,
        "investment_approved": False,
        "original_sec_sha256": {cik: r["source_raw_sha256"] for cik, r in sorted(verified.items())},
    }
