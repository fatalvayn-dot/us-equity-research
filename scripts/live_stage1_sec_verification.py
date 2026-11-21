"""Fetch two authorized public SEC CompanyConcept documents and audit exact bytes.

This one-shot tool reads *only* two fixed issuer/concept URLs; no arbitrary
downloads, paid APIs, MotherDuck changes, portfolio information or scoring.
It writes the original JSON files to the ephemeral Actions artifact, with
content SHA-256, a matched-facts report and a deterministic replay check.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import time
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

from scripts.verify_alexandria_sec_raw import verify_raw_sources

PUBLIC_CLAIMS = (
    dict(cik="0001045810", concept="Liabilities", taxonomy="us-gaap",
         accession="0001045810-26-000021", end="2026-01-25",
         filed="2026-02-25", value=49510000000, observed_at_ms=1795086089700),
    dict(cik="0000004127", concept="Liabilities", taxonomy="us-gaap",
         accession="0000004127-26-000055", end="2026-10-02",
         filed="2026-11-10", value=3721100000, observed_at_ms=1795086089677),
)
MAX_SEC_RESPONSE_BYTES = 16_000_000


def expected_payload():
    return {"data": {"alexandria": [
        {"provider": "sec-gov", "capability": "filings/concept",
         "data": {
             "cik": c["cik"], "taxonomy": c["taxonomy"], "concept": c["concept"],
             "source_url": companyconcept_url(c),
             "count": 1, "observed_at_ms": c["observed_at_ms"],
             "facts": [{
                 "accession_number": c["accession"], "form": "10-K",
                 "start": None, "end": c["end"], "filed": c["filed"],
                 "unit": "USD", "value": c["value"],
             }],
         }} for c in PUBLIC_CLAIMS
    ]}}


def companyconcept_url(claim):
    return (f"https://data.sec.gov/api/xbrl/companyconcept/"
            f"CIK{claim['cik']}/{claim['taxonomy']}/{claim['concept']}.json")


def fetch_official(url, user_agent):
    """A bounded official HTTPS GET with a unique, approved URL."""
    if url not in {companyconcept_url(c) for c in PUBLIC_CLAIMS}:
        raise ValueError("nonapproved SEC endpoint")
    if not isinstance(user_agent, str) or not user_agent.strip():
        raise ValueError("SEC_USER_AGENT required")
    request = Request(url, headers={
        "User-Agent": user_agent,
        "Accept": "application/json",
        "Accept-Encoding": "identity",
    })
    try:
        with urlopen(request, timeout=45) as response:
            if response.status != 200 or response.geturl() != url:
                raise ValueError("SEC original endpoint/HTTP status changed")
            data = response.read(MAX_SEC_RESPONSE_BYTES + 1)
            if not data or len(data) > MAX_SEC_RESPONSE_BYTES:
                raise ValueError("empty or oversized SEC original JSON")
            if "json" not in response.headers.get("Content-Type", "").lower():
                raise ValueError("SEC response content type is not JSON")
            json.loads(data)  # exact original bytes kept untouched
            return data
    except (HTTPError, URLError) as exc:
        raise ValueError("SEC download failed") from exc


def verify_snapshot(raw_by_url):
    """Replay one immutable raw snapshot and refuse any missing issuer."""
    if not isinstance(raw_by_url, dict) or set(raw_by_url) != {
        companyconcept_url(c) for c in PUBLIC_CLAIMS
    }:
        raise ValueError("exact two SEC source URLs required")
    from tempfile import TemporaryDirectory
    with TemporaryDirectory() as root:
        for c in PUBLIC_CLAIMS:
            body = raw_by_url[companyconcept_url(c)]
            if type(body) is not bytes or not body or len(body) > MAX_SEC_RESPONSE_BYTES:
                raise ValueError("bounded original bytes required")
            (Path(root) / f"{c['cik']}_{c['taxonomy']}_{c['concept']}.json").write_bytes(body)
        report = verify_raw_sources(expected_payload(), root)
    if report["verified_source_count"] != 2 or any(
        entry["matched_rows"] != 1 for entry in report["sources"]
    ):
        raise ValueError("SEC source agreement incomplete")
    return report


def run_once(raw_by_url, *, fetched_at=None):
    first = verify_snapshot(raw_by_url)
    second = verify_snapshot(raw_by_url)
    if first != second:
        raise ValueError("replay from identical raw SEC bytes is not deterministic")
    if fetched_at is None:
        fetched_at = datetime.now(timezone.utc).isoformat()
    records = []
    for claim, source in zip(PUBLIC_CLAIMS, first["sources"]):
        if (source["source_url"] != companyconcept_url(claim) or
                source["source_raw_sha256"] != hashlib.sha256(
                    raw_by_url[source["source_url"]]).hexdigest()):
            raise ValueError("SEC source digest mismatch")
        records.append({
            "issuer_id": claim["cik"], "concept": claim["concept"],
            "taxonomy": claim["taxonomy"], "accession": claim["accession"],
            "period_start": None, "period_end": claim["end"], "filed_on": claim["filed"],
            "form": "10-K", "unit": "USD", "reported_value": str(claim["value"]),
            "source_url": source["source_url"],
            "source_raw_sha256": source["source_raw_sha256"],
            "source_original_bytes": len(raw_by_url[source["source_url"]]),
            "observed_at_ms": claim["observed_at_ms"],
            "review_state": "source_verified",
            "investment_approved": False,
        })
    return {
        "schema_version": 1, "report_kind": "stage1_live_sec_original_replay",
        "verified_source_count": 2, "verified_record_count": 2,
        "replay_runs": 2, "replay_identical": True, "fetched_at": fetched_at,
        "records": records,
        "original_sec_http_response_bytes_preserved": True,
        "source_priority_unchanged": True,
        "score_inputs_changed": False,
        "scored_companies": 0, "investment_approved": False,
        "limits": ["One SEC snapshot replayed twice, not two independent historical vintages",
                   "No Shariah approval or 100-company acceptance",
                   "No MotherDuck writes or real trading"],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists() and any(args.output.iterdir()):
        raise ValueError("stage-one output directory must be empty")
    ua = os.environ.get("SEC_USER_AGENT")
    bodies = {}
    for idx, claim in enumerate(PUBLIC_CLAIMS):
        if idx:
            time.sleep(1)
        url = companyconcept_url(claim)
        bodies[url] = fetch_official(url, ua)
    report = run_once(bodies)
    args.output.mkdir(parents=True, exist_ok=True)
    for claim in PUBLIC_CLAIMS:
        source = claim["cik"] + "_" + claim["taxonomy"] + "_" + claim["concept"] + ".json"
        (args.output / source).write_bytes(bodies[companyconcept_url(claim)])
    (args.output / "verified-sec-stage1.json").write_text(
        json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8")
    print(json.dumps({key: report[key] for key in
                      ("verified_source_count", "replay_runs", "replay_identical",
                       "scored_companies", "investment_approved")}))
    for row in report["records"]:
        print(json.dumps({"issuer": row["issuer_id"], "accession": row["accession"],
                          "original_sec_sha256": row["source_raw_sha256"],
                          "bytes": row["source_original_bytes"]}))


if __name__ == "__main__":
    main()
