"""Reuse the existing SEC MVP collector for one exact issuer; no parallel SEC parser."""
import argparse
import json
from pathlib import Path

from equity_research.mvp import run_mvp, save_json

AAPL_CIK = "0000320193"


def collect_one(*, symbol="AAPL", cik=AAPL_CIK, state_dir, user_agent,
                max_new_documents=1, max_new_fields=14):
    if symbol != "AAPL" or cik != AAPL_CIK:
        raise ValueError("pilot permits only exact reviewed AAPL SEC identity")
    if not isinstance(user_agent, str) or not user_agent.strip():
        raise ValueError("SEC identifying user agent required")
    if type(max_new_fields) is not int or not 0 <= max_new_fields <= 14:
        raise ValueError("one-issuer bounded field budget required")
    report = run_mvp({"companies": [{"symbol": symbol, "issuer_id": cik}]},
                     state_dir=state_dir, user_agent=user_agent,
                     max_new_metadata=1, max_new_documents=max_new_documents,
                     max_new_fields=max_new_fields)
    if not isinstance(report, dict):
        raise ValueError("no verified SEC report returned")
    return report


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--state-dir", default="data/unified-aapl-sec")
    ap.add_argument("--user-agent", required=True)
    ap.add_argument("--out", default="unified-aapl-sec-report.json")
    args = ap.parse_args()
    report = collect_one(state_dir=args.state_dir, user_agent=args.user_agent)
    save_json(args.out, report)
    print(json.dumps({"status": "sec_collection_attempt",
                      "companies": len(report.get("companies", [])),
                      "accepted_facts": sum(
                          x.get("accepted_fact_count", 0)
                          for x in report.get("companies", [])
                          if type(x.get("accepted_fact_count")) is int),
                      "investment_approval": False}))
if __name__ == "__main__":
    main()
