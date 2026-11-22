"""Five-issuer comparison and scoring: invoke ONLY existing SEC evidence engines.

Each stage can be incomplete. No invented financial fields, ETF treatment,
Sharia certification, paid services, LLM calls or broker actions.
"""
import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from equity_research.mvp import save_json
from equity_research.valuation_collection import run_collection
from scripts.prepare_first_score_plans import plans
from scripts.build_current_scores import build as build_scores
from scripts.unified_us_five import COHORT, validate_cohort

EXPECTED = dict(COHORT)


def summarize(original, valuation, plan, scoring=None):
    if not isinstance(original, dict) or not isinstance(original.get("companies"), list):
        raise ValueError("five-company original research missing")
    validate_cohort([{"symbol": x["symbol"], "issuer_id": x["issuer_id"]}
                     for x in original["companies"]])
    prices = valuation.get("companies")
    if not isinstance(prices, list) or len(prices) != 5:
        raise ValueError("five-issuer valuation report incomplete")
    mapping = {}
    for x in prices:
        if (not isinstance(x, dict) or x.get("issuer_id") != EXPECTED.get(x.get("symbol"))
                or x["symbol"] in mapping):
            raise ValueError("valuation issuer mismatch/duplicate")
        mapping[x["symbol"]] = x
    exclusions = plan.get("excluded", [])
    if not isinstance(exclusions, list):
        raise ValueError("score plan exclusions invalid")
    by_exclusion = {}
    for row in exclusions:
        if (not isinstance(row, dict)
                or row.get("issuer_id") != EXPECTED.get(row.get("symbol"))
                or row["symbol"] in by_exclusion):
            raise ValueError("score plan issuer mismatch/duplicate")
        by_exclusion[row["symbol"]] = row.get("reason")
    scored = {}
    if scoring is not None:
        rows = scoring.get("companies", [])
        if not isinstance(rows, list):
            raise ValueError("scoring company result invalid")
        for row in rows:
            if (not isinstance(row, dict)
                    or row.get("issuer_id") != EXPECTED.get(row.get("symbol"))
                    or row["symbol"] in scored):
                raise ValueError("scoring issuer mismatch/duplicate")
            scored[row["symbol"]] = row
    result = dict(original)
    result["companies"] = []
    for entry in original["companies"]:
        symbol = entry["symbol"]
        row = dict(entry)
        market = mapping[symbol]
        status = {
            "identity": market.get("identity_status", "not_started"),
            "share": market.get("share_check", {}).get("status", "not_started"),
            "price": market.get("price_check", {}).get("status", "not_started"),
            "history": market.get("history_check", {}).get("status", "not_started"),
        }
        required = {"identity": "exact_match", "share": "verified_dated_share_class",
                    "price": "valid", "history": "valid"}
        row["valuation_source_states"] = status
        row["valuation_sources_verified"] = all(
            status[key] == needed for key, needed in required.items())
        if not row["valuation_sources_verified"]:
            row["blockers"].append("valuation_source_confirmation_incomplete")
        row["score_plan_exclusion"] = by_exclusion.get(symbol)
        candidate = scored.get(symbol, {})
        value = candidate.get("total_score")
        if candidate.get("status") == "scored_research_hypothesis" and value is not None:
            if isinstance(value, bool) or not isinstance(value, (str, int, float)):
                raise ValueError("score value malformed")
            row["score"] = value
            row["score_status"] = "scored_research_hypothesis"
            row["blockers"] = [x for x in row["blockers"]
                               if x not in ("five_company_valuation_comparison_not_run",)]
        else:
            row["score"] = None
            row["score_status"] = (candidate.get("status")
                                   or "blocked_source_or_comparison_evidence")
            if row["score_plan_exclusion"]:
                row["blockers"].append("scoring_plan_" + row["score_plan_exclusion"])
        # A research score must never override participation or trading rules.
        row["participation"] = "bilinmiyor"
        row["participation_independently_verified"] = False
        row["eligible_for_trade"] = False
        row["investment_approved"] = False
        result["companies"].append(row)
    result["valuation_sources_verified"] = sum(x["valuation_sources_verified"]
                                              for x in result["companies"])
    result["fully_scored"] = sum(x["score"] is not None for x in result["companies"])
    result["status"] = "five_company_comparative_score_research"
    result["investment_approved"] = False
    result["llm_calls"] = 0
    return result


def collect_and_score(*, input_report, sec_state, working_dir, user_agent,
                      collector=None, planner=None, scorer=None, command=None,
                      request_budget=26):
    if type(request_budget) is not int or not 0 <= request_budget <= 26:
        raise ValueError("maximum 26 new valuation requests for five companies")
    if not user_agent or not isinstance(user_agent, str):
        raise ValueError("SEC user agent required")
    original = json.loads(Path(input_report).read_text(encoding="utf-8"))
    validate_cohort(original["companies"])
    root = Path(working_dir)
    root.mkdir(parents=True, exist_ok=True)
    sec = Path(sec_state)
    if not (sec / "batch.json").is_file() or not (sec / "metadata.json").is_file() or not (sec / "report.json").is_file():
        raise ValueError("completed SEC five-company batch evidence required")
    command = command or subprocess.run
    collector = collector or run_collection
    planner = planner or plans
    scorer = scorer or build_scores
    source_dir = root / "sec-seed"
    command([sys.executable, "scripts/export_mvp_evidence.py",
             "--state-dir", str(sec), "--output", str(root / "sec-export"),
             "--sources", str(source_dir)], check=True)
    valuation = collector(
        {"companies": [{"symbol": s, "issuer_id": cik} for s, cik in COHORT]},
        state_dir=root / "valuation", user_agent=user_agent,
        max_new_requests=request_budget, seed_bundles=(str(source_dir),))
    save_json(root / "valuation-report.json", valuation)
    batch = json.loads((sec / "batch.json").read_text(encoding="utf-8"))
    metadata = json.loads((sec / "metadata.json").read_text(encoding="utf-8"))
    current, previous, plan = planner(batch, metadata, valuation,
                                      sec / "companyfacts", maximum=5)
    save_json(root / "score-plan.json", plan)
    save_json(root / "current-plan.json", current)
    save_json(root / "previous-plan.json", previous)
    scoring = None
    if plan.get("selected", 0) > 0:
        for tag, selected in (("current", current), ("previous", previous)):
            plan_file = root / (tag + "-plan.json")
            command([sys.executable, "-m", "equity_research", "research-batch",
                     "--plan", str(plan_file),
                     "--cache-dir", str(sec / "companyfacts"),
                     "--checkpoint", str(root / (tag + ".sqlite")),
                     "--output", str(root / (tag + "-batch.json")),
                     "--user-agent", user_agent,
                     "--max-new-fields", str(plan["selected"])], check=True)
        scoring = scorer(
            financial=sec / "batch.json",
            current=root / "current-batch.json",
            prior=root / "previous-batch.json",
            sources=root / "valuation" / "source-bundle",
            financial_sources=[source_dir], output=root / "scoring",
            as_of=datetime.now(timezone.utc))
    result = summarize(original, valuation, plan, scoring=scoring)
    save_json(root / "final-research.json", result)
    return result


def main():
    ap = argparse.ArgumentParser()
    for key in ("input-report", "sec-state", "working-dir", "user-agent", "out", "markdown"):
        ap.add_argument("--" + key, required=True)
    ap.add_argument("--max-new-requests", type=int, default=26)
    args = ap.parse_args()
    result = collect_and_score(input_report=args.input_report, sec_state=args.sec_state,
                               working_dir=args.working_dir, user_agent=args.user_agent,
                               request_budget=args.max_new_requests)
    save_json(args.out, result)
    from scripts.unified_us_five import render_markdown
    text = render_markdown(result).replace(
        "Tam finansal puan: 0/5 (karşılaştırmalı değerleme henüz bağlanmadı)",
        "Tam finansal puan: " + str(result["fully_scored"]) + "/5")
    for item in result["companies"]:
        text += "\n" + item["symbol"] + " skor=" + str(item["score"]) + " (" + item["score_status"] + ")"
    Path(args.markdown).write_text(text + "\n", encoding="utf-8")
    print(json.dumps({"status": result["status"],
                      "valuations_verified": result["valuation_sources_verified"],
                      "scored": result["fully_scored"], "investment_approved": False},
                     ensure_ascii=False))


if __name__ == "__main__":
    main()
