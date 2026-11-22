"""Deterministic AAPL acceptance gate: one evidence envelope, one LLM verdict.

A GitHub job succeeding is not equivalent to Sharia, predictive-model or trade
approval. This module never accesses market APIs or executes broker actions.
"""
import argparse
import json
from pathlib import Path

from equity_research.mvp import save_json


def assess(report, llm=None):
    if (not isinstance(report, dict) or report.get("schema_version") != 1
            or report.get("symbol") != "AAPL"
            or report.get("eligible_for_trade") is not False
            or report.get("investment_advice") is not False):
        raise ValueError("AAPL research-only envelope required")
    gates = report.get("gates")
    if not isinstance(gates, dict):
        raise ValueError("research gates absent")
    finance = report.get("financial_research")
    valuation = report.get("valuation_research")
    scoring = report.get("scoring_research")
    backtest = report.get("historical_prediction_check")
    news = report.get("research", {}).get("news")
    participation = report.get("participation_research")
    for key, value in (("finance", finance), ("valuation", valuation),
                       ("scoring", scoring), ("backtest", backtest),
                       ("news", news), ("participation", participation)):
        if not isinstance(value, dict):
            raise ValueError(key + " proof missing")
    evidence = {
        "live_price": report.get("source") not in (None, "fixture")
                      and gates.get("market_price") == "source_observed",
        "sec_financials": finance.get("status") == "facts_observed_review_required"
                          and finance.get("all_financial_references_archived") is True
                          and type(finance.get("accepted_fact_count")) is int
                          and finance["accepted_fact_count"] > 0,
        "four_market_sources": valuation.get("status") == "source_gates_observed_not_valued"
                               and valuation.get("blockers") == [],
        "comparative_scoring": scoring.get("status") == "scored_research_hypothesis"
                               and scoring.get("score") is not None,
        "rss_headlines": news.get("status") == "ok"
                         and gates.get("news_event_model") == "rss_headlines_only_no_causal_model",
        "llm_five_real_calls": isinstance(llm, dict)
                               and llm.get("status") == "completed"
                               and llm.get("real_api_tested") is True
                               and llm.get("provider") == "openrouter/free"
                               and llm.get("paid_fallback") is False
                               and llm.get("llm_calls") == 5
                               and all(isinstance(llm.get("agents", {}).get(role), str)
                                       and llm["agents"][role].strip()
                                       for role in ("manager", "researcher", "developer",
                                                    "auditor", "manager_report")),
        "independent_participation": participation.get("status") == "uygun"
                                     and participation.get("no_live_source_verification") is False,
        "predictive_edge_validated": backtest.get("predictive_approved") is True
                                    and backtest.get("adaptive_optimization_verified") is True,
        "news_effect_validated": gates.get("news_event_model") == "validated_causal_outcome_model",
    }
    # Even if a future screen says eligible, independent compliance cannot
    # authorize an order in this research-only application.
    missing = [name for name, passed in evidence.items() if not passed]
    operational = all(evidence[x] for x in
                      ("live_price", "sec_financials", "four_market_sources",
                       "comparative_scoring", "rss_headlines", "llm_five_real_calls"))
    return {
        "schema_version": 1,
        "symbol": "AAPL",
        "as_of": report.get("as_of"),
        "status": "research_chain_operational" if operational else "research_chain_incomplete",
        "all_user_requested_stages_accepted": not missing,
        "evidence_gates": evidence,
        "missing_acceptance": missing,
        "score": scoring.get("score") if evidence["comparative_scoring"] else None,
        "score_model_version": scoring.get("model_version"),
        "score_components": scoring.get("score_components", {}) if evidence["comparative_scoring"] else {},
        "prediction_baseline_hit_rate": backtest.get("benchmark_up_hit_rate"),
        "prediction_observed_hit_rate": backtest.get("direction_hit_rate"),
        "advisor_verdict": (
            llm["agents"]["manager_report"][:1800]
            if evidence["llm_five_real_calls"] else None),
        "participation_review_reasons": sorted([
            reason for reason in participation.get("review_reasons", [])
            if isinstance(reason, str) and len(reason) <= 80
        ]) if isinstance(participation.get("review_reasons"), list) else [
            "reviewed_standard_and_original_filing_evidence_missing"],
        "decision": "YENI_ALIM_IZNI_YOK",
        "investment_approved": False,
        "eligible_for_trade": False,
        "paid_model_used": False,
    }


def markdown(result):
    lines = [
        "# AAPL — Adaptif Yatırım Uzmanı kabul raporu",
        "",
        "Araştırma zinciri: " + result["status"],
        "Araştırma puanı: " + str(result["score"]),
        "Yeni alım yetkisi: YOK",
        "",
        "## Aşama kontrolleri",
    ]
    for name, passed in result["evidence_gates"].items():
        lines.append("- " + ("GEÇTİ" if passed else "EKSİK") + ": " + name)
    components = result.get("score_components", {})
    if components:
        lines.extend(["", "## Finansal skor bileşenleri"])
        for key in ("financial_strength", "valuation", "growth", "profitability", "cash_flow", "risk"):
            item = components.get(key)
            if isinstance(item, dict):
                lines.append("- " + key + ": " + str(item.get("score")) + " / " + str(item.get("max")))
    lines += ["", "## Son uzman değerlendirmesi",
              result.get("advisor_verdict") or "Gerçek beş ajanlı rapor henüz doğrulanmadı.",
              "", "## Kabul eksikleri",
              ", ".join(result["missing_acceptance"]) or "Yok",
              "", "Katılım veri eksikleri:",
              ", ".join(result.get("participation_review_reasons", [])) or "Yok",
              "", "Bu sonuç yatırım talimatı değildir."]
    return "\n".join(lines) + "\n"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--research", required=True)
    parser.add_argument("--llm")
    parser.add_argument("--out", required=True)
    parser.add_argument("--markdown", required=True)
    args = parser.parse_args()
    report = json.loads(Path(args.research).read_text(encoding="utf-8"))
    llm = json.loads(Path(args.llm).read_text(encoding="utf-8")) if args.llm and Path(args.llm).is_file() else None
    result = assess(report, llm)
    save_json(args.out, result)
    Path(args.markdown).write_text(markdown(result), encoding="utf-8")
    print(json.dumps({"status": result["status"], "missing_acceptance": result["missing_acceptance"],
                      "investment_approved": False}, ensure_ascii=False))


if __name__ == "__main__":
    main()
