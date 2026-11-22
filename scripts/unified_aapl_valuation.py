"""Bounded AAPL valuation evidence acquisition using the EXISTING collector and plan selector.

No new financial ratios, guessed prices, inferred share class, or trade actions.
"""
import argparse
import json
from pathlib import Path
from equity_research.valuation_collection import run_collection
from equity_research.mvp import save_json
from scripts.prepare_first_score_plans import plans

CIK = "0000320193"
SYMBOL = "AAPL"
LEGS = ("identity", "share", "price", "history")


def summarize(report):
    if not isinstance(report, dict) or len(report.get("companies", [])) != 1:
        raise ValueError("exactly one valuation issuer required")
    company = report["companies"][0]
    if (company.get("symbol"), company.get("issuer_id")) != (SYMBOL, CIK):
        raise ValueError("valuation issuer identity mismatch")
    states = {
        "identity": company.get("identity_status", "not_started"),
        "share": company.get("share_check", {}).get("status", "not_started"),
        "price": company.get("price_check", {}).get("status", "not_started"),
        "history": company.get("history_check", {}).get("status", "not_started"),
    }
    expected = {"identity": "exact_match", "share": "verified_dated_share_class",
                "price": "valid", "history": "valid"}
    missing = [
        {"stage": name, "observed": states[name], "expected": expected[name]}
        for name in LEGS if states[name] != expected[name]
    ]
    return {"symbol": SYMBOL, "issuer_id": CIK,
            "source_as_of": report.get("as_of"),
            "states": states, "blockers": missing,
            "market_source_complete": not missing,
            "eligible_for_trade": False,
            "score": None}


def collect(*, state_dir, user_agent, source_bundle, max_new_requests=8):
    if not user_agent or not isinstance(user_agent, str):
        raise ValueError("SEC user agent required")
    if type(max_new_requests) is not int or not 0 <= max_new_requests <= 10:
        raise ValueError("single-issuer budget must be <=10")
    bundle = Path(source_bundle)
    if not (bundle / "manifest.json").is_file():
        raise ValueError("verified financial archive seed bundle required")
    report = run_collection(
        {"companies": [{"symbol": SYMBOL, "issuer_id": CIK}]},
        state_dir=state_dir, user_agent=user_agent,
        max_new_requests=max_new_requests, seed_bundles=(str(bundle),))
    return report, summarize(report)


def plan_review(*, financial_batch, metadata, valuation_report, companyfacts_dir):
    current, previous, diagnostic = plans(
        json.loads(Path(financial_batch).read_text(encoding="utf-8")),
        json.loads(Path(metadata).read_text(encoding="utf-8")),
        valuation_report, companyfacts_dir, maximum=1)
    if diagnostic.get("evaluated") != 1:
        raise ValueError("single issuer score planning required")
    if (current["companies"] and
        any(c.get("issuer_id") != CIK or c.get("symbol") != SYMBOL
            for c in current["companies"])):
        raise ValueError("score plan issuer mismatch")
    # Zero is unavailable, not a zero-valued ranking.
    return current, previous, diagnostic


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--state-dir", required=True)
    p.add_argument("--user-agent", required=True)
    p.add_argument("--source-bundle", required=True)
    p.add_argument("--max-new-requests", type=int, default=8)
    p.add_argument("--financial-batch")
    p.add_argument("--metadata")
    p.add_argument("--companyfacts-dir")
    p.add_argument("--out", required=True)
    args = p.parse_args()
    report, summary = collect(
        state_dir=args.state_dir, user_agent=args.user_agent,
        source_bundle=args.source_bundle,
        max_new_requests=args.max_new_requests)
    if all((args.financial_batch, args.metadata, args.companyfacts_dir)):
        current, previous, review = plan_review(
            financial_batch=args.financial_batch, metadata=args.metadata,
            valuation_report=report, companyfacts_dir=args.companyfacts_dir)
        summary["score_plan"] = {
            "eligible_count": review["selected"],
            "blocked_reasons": review["excluded_reasons"],
            "status": "planning_only",
            "investment_approved": False,
        }
        save_json(str(Path(args.out).with_suffix(".score-plan.json")), review)
        save_json(str(Path(args.out).with_suffix(".current.json")), current)
        save_json(str(Path(args.out).with_suffix(".prior.json")), previous)
    save_json(args.out, summary)
    print(json.dumps(summary, ensure_ascii=False))
if __name__ == "__main__":
    main()
