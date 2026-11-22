"""Read-only archive of ORIGINAL official AAPL issuer/methodology bytes.

This proves bytes came from allowlisted HTTPS endpoints on retrieval date.
It does NOT establish PDF issue date, original accounting ratios or Sharia approval.
"""
import argparse
import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
import urllib.request
from urllib.parse import urlsplit

from equity_research.mvp import save_json

OFFICIAL = {
    "sec_submissions": ("https://data.sec.gov/submissions/CIK0000320193.json", "json"),
    "sp_shariah_methodology": (
        "https://www.spglobal.com/spdji/en/documents/methodologies/"
        "methodology-sp-shariah-indices.pdf", "pdf"),
}
MAX_BYTES = 12 * 1024 * 1024


def verify_bytes(source_name, payload):
    if source_name not in OFFICIAL:
        raise ValueError("unapproved source")
    if not isinstance(payload, bytes) or not 32 <= len(payload) <= MAX_BYTES:
        raise ValueError("original source bytes absent or over budget")
    if source_name == "sec_submissions":
        doc = json.loads(payload)
        if not isinstance(doc, dict) or doc.get("cik") != 320193:
            raise ValueError("SEC CIK identity mismatch")
        if "AAPL" not in doc.get("tickers", []):
            raise ValueError("SEC AAPL ticker evidence missing")
        content_kind = "sec_issuer_identity_only"
    else:
        if not payload.lstrip().startswith(b"%PDF-"):
            raise ValueError("official methodology PDF header missing")
        content_kind = "published_methodology_bytes_only"
    return {
        "source_name": source_name,
        "source_url": OFFICIAL[source_name][0],
        "raw_sha256": hashlib.sha256(payload).hexdigest(),
        "size_bytes": len(payload),
        "validation": content_kind,
        "publication_date_verified": False,
        "independent_financial_ratios_verified": False,
        "investment_approved": False,
    }


def archive(destination, user_agent, transport=None):
    if not isinstance(user_agent, str) or not user_agent.strip():
        raise ValueError("official SEC contact user agent missing")
    destination = Path(destination)
    destination.mkdir(parents=True, exist_ok=True)
    results = []
    for source_name, (url, kind) in OFFICIAL.items():
        now = datetime.now(timezone.utc).isoformat()
        try:
            if transport is not None:
                body, final_url = transport(url)
            else:
                req = urllib.request.Request(
                    url, headers={"User-Agent": user_agent,
                                  "Accept": "application/json" if kind == "json"
                                            else "application/pdf"})
                with urllib.request.urlopen(req, timeout=18) as response:
                    final_url = response.url
                    body = response.read(MAX_BYTES + 1)
            if not isinstance(final_url, str) or final_url.rstrip("/") != url.rstrip("/"):
                raise ValueError("unexpected redirect or source host")
            if urlsplit(final_url).scheme != "https":
                raise ValueError("non-HTTPS original source")
            proof = verify_bytes(source_name, body)
            extension = "json" if kind == "json" else "pdf"
            (destination / (source_name + "." + extension)).write_bytes(body)
            proof.update(retrieved_at_utc=now, status="original_bytes_archived",
                         archive_filename=source_name + "." + extension)
        except Exception as exc:
            # Errors are intentionally deterministic names; no full URL,
            # response contents, Authorization or external error details.
            proof = {"source_name": source_name, "source_url": url,
                     "retrieved_at_utc": now, "status": "unavailable",
                     "reason": type(exc).__name__,
                     "publication_date_verified": False,
                     "investment_approved": False}
        results.append(proof)
    report = {
        "schema_version": 1,
        "symbol": "AAPL",
        "issuer_key": "SEC:0000320193",
        "sources": results,
        "all_original_bytes_archived": all(
            p.get("status") == "original_bytes_archived" for p in results),
        "sharia_methodology_independently_reviewed": False,
        "issuer_financial_ratios_independently_verified": False,
        "participation_status": "bilinmiyor",
        "investment_approved": False,
        "eligible_for_trade": False,
    }
    save_json(str(destination / "source-manifest.json"), report)
    return report


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--destination", required=True)
    p.add_argument("--user-agent", required=True)
    args = p.parse_args()
    report = archive(args.destination, args.user_agent)
    print(json.dumps({
        "status": "source_archive_attempt",
        "all_original_bytes_archived": report["all_original_bytes_archived"],
        "source_statuses": {s["source_name"]: s["status"] for s in report["sources"]},
        "participation_status": report["participation_status"],
        "investment_approved": False}, ensure_ascii=False))


if __name__ == "__main__":
    main()
