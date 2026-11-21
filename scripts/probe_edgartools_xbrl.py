"""Optional, read-only SEC XBRL concept probe. Not a scoring/provider fallback.

Requires: pip install edgartools (MIT). Uses SEC_USER_AGENT as EDGAR identity.
Never substitutes an adjacent accounting concept for an exact required field.
"""
import argparse
import json
import os
from pathlib import Path


def probe(ticker, concepts, company_factory=None):
    if company_factory is None:
        from edgar import Company, set_identity
        identity = os.getenv("SEC_USER_AGENT", "")
        if not identity.strip():
            raise ValueError("SEC_USER_AGENT missing; SEC requests not attempted")
        set_identity(identity)
        company_factory = Company
    filing = company_factory(ticker).get_filings(form="10-K").latest()
    if filing is None:
        raise ValueError("No 10-K filing found")
    xbrl = filing.xbrl()
    if xbrl is None:
        raise ValueError("Selected 10-K contains no readable XBRL")
    evidence = []
    for concept in concepts:
        # Diagnostic only: avoid claiming that an empty query means the
        # financial concept is economically absent from the issuer's filing.
        frame = xbrl.facts.query().by_concept(concept).to_dataframe()
        evidence.append({"concept": concept, "matching_rows": len(frame),
                         "state": "candidates_for_review" if len(frame) else "not_found_in_probe"})
    return {"ticker": ticker.upper(), "form": "10-K",
            "accession": str(filing.accession_no),
            "filing_date": str(filing.filing_date),
            "results": evidence,
            "decision": "manual_review_only",
            "source": "SEC filing via dgunning/edgartools"}


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--ticker", required=True)
    p.add_argument("--concept", action="append", required=True,
                   help="Exact XBRL concept; repeat for each concept")
    p.add_argument("--output", type=Path)
    args = p.parse_args()
    result = probe(args.ticker, args.concept)
    payload = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(payload, encoding="utf-8")
    else:
        print(payload, end="")


if __name__ == "__main__":
    main()
