"""Prepare exact consecutive SEC revenue comparison plans for a live score attempt.

Only discovers periods and eligibility candidates. Numeric facts are still
selected by the ordinary Yahoo -> SEC -> Nasdaq -> Finnhub research resolver.
"""
import argparse
import hashlib
import json
from collections import Counter
from datetime import date, datetime, timedelta
from decimal import Decimal
from pathlib import Path

from equity_research.comparative import comparable_periods
from equity_research.companyfacts import companyfacts_url
from equity_research.mvp import save_json
from equity_research.reporting import build_report
from equity_research.scoring import MODELS, REQUIRED
from equity_research.sector_policy import excluded_banking_or_insurance
from equity_research.transport import strict_json


def revenue_periods(revenue, annual, companyfacts_dir, cik):
    """Return exact SEC periods or a reason the comparison cannot be planned."""
    if (not annual or revenue["period_end"] != annual[0]["report_end"]
            or revenue.get("filing_accession") != annual[0]["accession"]):
        return None, "annual_period_or_accession_mismatch"

    cache = Path(companyfacts_dir) / (cik + ".json")
    if not cache.is_file():
        return None, "original_sec_companyfacts_cache_missing"
    envelope = json.loads(cache.read_text())
    body = envelope.get("body", "").encode("utf-8")
    if (envelope.get("url") != companyfacts_url(cik)
            or hashlib.sha256(body).hexdigest() != envelope.get("sha256")
            or envelope.get("sha256") != revenue.get("raw_sha256")):
        return None, "companyfacts_source_hash_or_url_mismatch"
    payload = strict_json(body)
    if payload.get("cik") != int(cik):
        return None, "sec_issuer_identity_mismatch"
    rows = (payload.get("facts", {}).get("us-gaap", {})
        .get("RevenueFromContractWithCustomerExcludingAssessedTax", {})
        .get("units", {}).get("USD", []))
    current_start = date.fromisoformat(revenue["period_start"])
    current_end = date.fromisoformat(revenue["period_end"])
    previous_end = current_start - timedelta(days=1)
    filing_rows = [r for r in rows if r.get("accn") == revenue["filing_accession"]
                   and r.get("filed") == revenue.get("filed_on")
                   and r.get("form") in ("10-K", "10-K/A")]
    current_rows = [r for r in filing_rows if r.get("start") == revenue["period_start"]
                    and r.get("end") == revenue["period_end"]]
    previous_rows = [r for r in filing_rows
                     if r.get("end") == previous_end.isoformat() and r.get("start")
                     and comparable_periods(current_start, current_end,
                         date.fromisoformat(r["start"]), previous_end)]
    ambiguous = "explicit_comparable_revenue_missing_or_ambiguous"
    if len(current_rows) != 1 or len(previous_rows) != 1:
        return None, ambiguous
    current_value, prior_value = (current_rows[0]["val"], previous_rows[0]["val"])
    if (type(current_value) not in (int, Decimal) or type(prior_value) not in (int, Decimal)
            or not Decimal(prior_value).is_finite() or prior_value <= 0
            or Decimal(current_value) != Decimal(revenue["value"])):
        return None, ambiguous
    return (current_rows[0], previous_rows[0]), None


def plans(financial_batch, metadata, valuation, companyfacts_dir, *, maximum=10):
    if not isinstance(maximum, int) or not 1 <= maximum <= 100:
        raise ValueError("bounded candidate selection required")
    financial_report = build_report(financial_batch)
    reviewed = {c["issuer_id"]: c for c in financial_report["companies"]}
    metas = {c["issuer_id"]: c for c in metadata["companies"]}
    prices = {c["issuer_id"]: c for c in valuation["companies"]}
    if len(metas) != len(metadata["companies"]) or len(prices) != len(valuation["companies"]):
        raise ValueError("duplicate metadata or valuation identity")
    current, prior, excluded, market_pending = [], [], [], []
    priority_symbols = set(valuation.get("priority_symbols", []))
    candidates = sorted(financial_batch["companies"],
                        key=lambda company: company["symbol"] not in priority_symbols)
    for company in candidates:
        cik, symbol = company["issuer_id"], company["symbol"]
        reason = None
        rowmeta, market = metas.get(cik), prices.get(cik)
        if rowmeta is None or market is None or rowmeta["symbol"] != symbol or market["symbol"] != symbol:
            reason = "issuer_or_symbol_source_mismatch"
        elif excluded_banking_or_insurance(rowmeta.get("snapshot", {}).get("sic_label")):
            reason = "banking_or_insurance_permanently_excluded"
        elif reviewed[cik]["financial_assessment"]["quantitative_gate"] != "no_screen_trigger":
            reason = "financial_review_required"
        elif not (rowmeta.get("status") == "metadata_available_legal_type_pending"
                  and rowmeta.get("snapshot", {}).get("entity_type_label") == "operating"
                  and rowmeta["snapshot"].get("sic_label") in MODELS):
            reason = "unsupported_sector_or_entity_type"
        else:
            facts = {f["query"]["field"]: f["fact"] for f in company["fields"] if f.get("fact")}
            if any(f not in facts for f in REQUIRED):
                reason = "nine_model_financial_facts_incomplete"
            elif facts["revenue"]["source"] != "SEC":
                reason = "current_revenue_sec_confirmation_pending"
            else:
                annual = rowmeta["snapshot"].get("annual_filings", [])
                try:
                    periods, reason = revenue_periods(facts["revenue"], annual, companyfacts_dir, cik)
                except (OSError, ValueError, TypeError, KeyError, AttributeError, ArithmeticError):
                    periods, reason = None, "invalid_comparable_revenue_evidence"
                if periods is not None:
                    latest, previous = periods
                    if (market.get("identity_status") != "exact_match"
                            or market.get("share_check", {}).get("status") != "verified_dated_share_class"
                            or market.get("price_check", {}).get("status") != "valid"
                            or market.get("history_check", {}).get("status") != "valid"):
                        reason = "market_or_original_share_evidence_incomplete"
                        market_pending.append(dict(symbol=symbol, issuer_id=cik,
                            current_period=[latest["start"], latest["end"]],
                            prior_period=[previous["start"], previous["end"]],
                            accession=latest["accn"], raw_sha256=facts["revenue"]["raw_sha256"]))
                    elif len(current) >= maximum:
                        reason = "candidate_budget_exceeded"
                    else:
                        basis = dict(symbol=symbol, issuer_id=cik, currency="USD",
                            fields=["revenue"], scope_status="pending_scope",
                            scope_reason="separate_security_sector_and_investment_review_pending")
                        current.append(dict(**basis, period_start=latest["start"], period_end=latest["end"]))
                        prior.append(dict(**basis, period_start=previous["start"], period_end=previous["end"]))
        if reason:
            excluded.append(dict(symbol=symbol, issuer_id=cik, reason=reason))
    return (
        dict(schema_version=1, companies=current),
        dict(schema_version=1, companies=prior),
        dict(schema_version=1, selected=len(current), evaluated=len(financial_batch["companies"]),
            selected_symbols=[x["symbol"] for x in current],
            excluded_reasons=dict(Counter(x["reason"] for x in excluded)),
            excluded=excluded, comparison_evidence_market_pending=market_pending, securities_approved=False, full_scores_generated=False,
            mvp_accepted=False,
            notes="Only exact consecutive periods, not financial winner selection or scoring")
    )


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for name in ("financial", "metadata", "valuation", "companyfacts-dir",
                 "current-plan", "prior-plan", "report"):
        p.add_argument("--" + name, required=True)
    p.add_argument("--maximum", type=int, default=10)
    args = p.parse_args()
    read = lambda path: json.loads(Path(path).read_text())
    current, prior, report = plans(read(args.financial), read(args.metadata),
        read(args.valuation), args.companyfacts_dir, maximum=args.maximum)
    for path, value in ((args.current_plan, current), (args.prior_plan, prior),
                        (args.report, report)):
        save_json(path, value)
    print(json.dumps(dict(selected=report["selected"], symbols=report["selected_symbols"],
        reasons=report["excluded_reasons"]), ensure_ascii=False))
    if "GITHUB_OUTPUT" in __import__("os").environ:
        with Path(__import__("os").environ["GITHUB_OUTPUT"]).open("a") as out:
            out.write("ready=true\n")
            out.write(f"has_candidates={str(bool(report['selected'])).lower()}\n")


if __name__ == "__main__":
    main()
