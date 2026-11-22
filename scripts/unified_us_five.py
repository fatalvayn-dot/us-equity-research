"""Five-US-issuer first rollout, reusing existing SEC MVP and unified market engine.

Live research is strictly read-only. Source/identity failures are recorded per
issuer; zero score never substitutes for missing evidence. No LLM calls here.
"""
import argparse
import json
from pathlib import Path
from datetime import datetime, timezone

from equity_research.mvp import run_mvp, save_json
from scripts import unified_single_issuer

COHORT = (
    ("AAPL", "0000320193"),
    ("MSFT", "0000789019"),
    ("NVDA", "0001045810"),
    ("AMZN", "0001018724"),
    ("GOOGL", "0001652044"),
)
EXPECTED = dict(COHORT)


def validate_cohort(companies):
    if not isinstance(companies, list) or len(companies) != 5:
        raise ValueError("exactly five US common-stock research candidates required")
    try:
        actual = [(entry["symbol"], entry["issuer_id"]) for entry in companies]
    except (KeyError, TypeError):
        raise ValueError("each entry needs exact symbol and SEC CIK") from None
    if len(set(actual)) != 5 or set(actual) != set(COHORT):
        raise ValueError("pilot SEC symbol/CIK mismatch, missing or duplicate")
    return [{"symbol": symbol, "issuer_id": cik} for symbol, cik in COHORT]


def research_five(*, user_agent, state_dir, fixture=None,
                  market_runner=None, sec_collector=None,
                  max_new_fields=70):
    if type(max_new_fields) is not int or not 0 <= max_new_fields <= 70:
        raise ValueError("five-issuer SEC field budget exceeds 70")
    if not isinstance(user_agent, str) or not user_agent.strip():
        raise ValueError("SEC identifying contact required")
    market_runner = market_runner or unified_single_issuer.build
    sec_collector = sec_collector or run_mvp
    candidates = validate_cohort([{"symbol": symbol, "issuer_id": cik}
                                  for symbol, cik in COHORT])
    output = {"schema_version": 1, "cohort": "US_FIVE_V1",
              "as_of": datetime.now(timezone.utc).isoformat(),
              "requested": len(candidates), "companies": [],
              "market_history_orchestrations_per_issuer": 1,
              "sec_batch_runs": 1,
              "llm_calls": 0, "real_orders": 0, "paid_api_enabled": False,
              "investment_approved": False}
    try:
        sec = sec_collector({"companies": candidates},
                            state_dir=state_dir, user_agent=user_agent,
                            max_new_metadata=5, max_new_documents=5,
                            max_new_fields=max_new_fields)
        if not isinstance(sec, dict):
            raise ValueError("SEC collector returned no report")
        sec_rows = sec.get("companies")
        if not isinstance(sec_rows, list):
            raise ValueError("SEC company result list unavailable")
        by_symbol = {}
        for item in sec_rows:
            if not isinstance(item, dict):
                raise ValueError("invalid SEC company result")
            symbol = item.get("symbol")
            cik = item.get("issuer_id")
            if symbol not in EXPECTED or cik != EXPECTED[symbol] or symbol in by_symbol:
                raise ValueError("SEC report contains cross-issuer/duplicate identity")
            by_symbol[symbol] = item
        sec_error = None
    except Exception as exc:
        by_symbol = {}
        sec = {}
        sec_error = type(exc).__name__
    for symbol, cik in COHORT:
        state = {"symbol": symbol, "issuer_id": cik, "as_of": output["as_of"],
                 "market": "not_verified", "sec": "not_verified",
                 "accepted_fact_count": 0, "score": None,
                 "score_status": "blocked_cohort_valuation_not_connected",
                 "participation": "bilinmiyor",
                 "participation_independently_verified": False,
                 "predictive_approved": False,
                 "llm_status": "not_called_cohort_cost_gate",
                 "eligible_for_trade": False, "investment_approved": False,
                 "blockers": []}
        record = by_symbol.get(symbol)
        if record is None:
            state["blockers"].append("sec_identity_not_returned" if not sec_error
                                     else "sec_batch_" + sec_error)
        else:
            count = record.get("accepted_fact_count", 0)
            if type(count) is not int or count < 0:
                count = 0
                state["blockers"].append("invalid_sec_fact_count")
            state["accepted_fact_count"] = count
            # Global archive flag cannot be silently equated to per-company proof.
            archived = sec.get("pipeline", {}).get("all_financial_references_archived") is True
            state["sec"] = "archived_research_facts" if count > 0 and archived else "source_review_required"
            if state["sec"] != "archived_research_facts":
                state["blockers"].append("sec_financial_source_archive_or_fields_incomplete")
        try:
            report = market_runner(symbol, fixture=fixture)
            if (not isinstance(report, dict) or report.get("symbol") != symbol
                    or report.get("eligible_for_trade") is not False
                    or report.get("investment_advice") is not False):
                raise ValueError("market envelope cross-issuer or unsafe")
            state["market"] = report["gates"]["market_price"]
            state["market_source"] = report.get("source")
            state["price_as_of"] = report.get("as_of")
            state["baseline_direction"] = report.get("forecast", {}).get("direction")
            state["baseline_approved"] = False
        except Exception as exc:
            state["blockers"].append("market_" + type(exc).__name__)
        state["blockers"].extend([
            "reviewed_sharia_source_and_ratio_evidence_missing",
            "five_company_valuation_comparison_not_run",
            "historical_prediction_edge_unverified",
        ])
        output["companies"].append(state)
    output["market_verified"] = sum(
        c["market"] in ("fixture", "source_observed") for c in output["companies"])
    output["sec_archived"] = sum(
        c["sec"] == "archived_research_facts" for c in output["companies"])
    output["fully_scored"] = 0
    output["status"] = "research_first_five_cohort_observed"
    return output


def render_markdown(report):
    lines = ["# ABD ilk beş şirket — araştırma kaynak ve kabul özeti", "",
             "Kohort: US_FIVE_V1 · AAPL, MSFT, NVDA, AMZN, GOOGL",
             "Kamu fiyat kaynağı doğrulanan: " + str(report["market_verified"]) + "/5",
             "SEC arşivli araştırma şirketi: " + str(report["sec_archived"]) + "/5",
             "Tam finansal puan: 0/5 (karşılaştırmalı değerleme henüz bağlanmadı)",
             "Katılım ve otomatik alım onayı: YOK",
             "", "## Şirket bazlı durum"]
    for row in report["companies"]:
        lines.append("- " + row["symbol"] + " (CIK " + row["issuer_id"] + "): "
                     + "piyasa=" + row["market"] + ", SEC=" + row["sec"]
                     + ", kabul edilen SEC alanı=" + str(row["accepted_fact_count"])
                     + ", eksikler=" + ", ".join(row["blockers"]))
    lines.extend(["", "Bu bir yatırım veya alım raporu değildir.",
                  "Sonraki iş: kaynak arşivini koruyarak beş şirkete mevcut "
                  "değerleme ve karşılaştırmalı skor motorunu bağlamak."])
    return "\n".join(lines) + "\n"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--user-agent", required=True)
    parser.add_argument("--state-dir", required=True)
    parser.add_argument("--fixture")
    parser.add_argument("--max-new-fields", type=int, default=70)
    parser.add_argument("--out", required=True)
    parser.add_argument("--markdown", required=True)
    args = parser.parse_args()
    result = research_five(user_agent=args.user_agent, state_dir=args.state_dir,
                           fixture=args.fixture, max_new_fields=args.max_new_fields)
    save_json(args.out, result)
    Path(args.markdown).write_text(render_markdown(result), encoding="utf-8")
    print(json.dumps({"status": result["status"], "market_verified": result["market_verified"],
                      "sec_archived": result["sec_archived"],
                      "fully_scored": result["fully_scored"],
                      "investment_approved": False}, ensure_ascii=False))


if __name__ == "__main__":
    main()
