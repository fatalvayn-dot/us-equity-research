"""Opt-in free-only real AAPL LLM run. No second market fetch and no paid fallback."""
import argparse
import json
import os
from pathlib import Path
from scripts import llm_team
from equity_research.mvp import save_json


def process(report, *, enabled, key_present, transport=None):
    if (not isinstance(report, dict) or report.get("symbol") != "AAPL"
            or report.get("schema_version") != 1
            or report.get("eligible_for_trade") is not False
            or report.get("investment_advice") is not False):
        raise ValueError("unverified research-only AAPL report")
    missing = []
    if enabled != "true":
        missing.append("RADAR_FREE_LLM_ENABLED")
    if not key_present and transport is None:
        missing.append("OPENROUTER_API_KEY")
    if missing:
        return {"status": "blocked_missing_configuration",
                "missing_configuration": missing, "real_api_tested": False,
                "paid_fallback": False, "investment_approved": False}
    # Called once using the already serialized research envelope.
    result = llm_team.orchestrate(report, transport=transport)
    return {"status": "completed", "real_api_tested": transport is None,
            "provider": "openrouter/free" if transport is None else "mock_only",
            "paid_fallback": False, "investment_approved": False,
            "llm_calls": result["llm_calls"], "agents": result["agents"]}


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--input", required=True)
    p.add_argument("--out", required=True)
    args = p.parse_args()
    report = json.loads(Path(args.input).read_text(encoding="utf-8"))
    result = process(
        report, enabled=os.getenv("RADAR_FREE_LLM_ENABLED", "false"),
        key_present=bool(os.getenv("OPENROUTER_API_KEY")))
    save_json(args.out, result)
    print(json.dumps({k: v for k, v in result.items() if k != "agents"},
                     ensure_ascii=False))
if __name__ == "__main__":
    main()
