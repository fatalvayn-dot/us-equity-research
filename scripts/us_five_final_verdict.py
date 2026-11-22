"""Cohort-level acceptance from SAME RUN: SEC, score, raw iXBRL and Sharia gates.

This is a deterministic evidence report, not an LLM trading recommendation.
Missing or issuer-mismatched source material fails closed.
"""
import argparse
import json
from pathlib import Path
from equity_research.mvp import save_json
from scripts.unified_us_five import COHORT

EXPECTED = dict(COHORT)
BLOCKED = ("NVDA", "AMZN", "GOOGL")


def verdict(scored, gaps, original):
    reports = []
    for value, name in ((scored, "scored"), (gaps, "gaps"), (original, "original")):
        if not isinstance(value, dict):
            raise ValueError(name + " must be a report")
        if value.get("investment_approved") is not False:
            raise ValueError(name + " may not approve orders")
    if scored.get("cohort") != "US_FIVE_V1" or gaps.get("cohort") != "US_FIVE_V1":
        raise ValueError("cohort version mismatch")
    for rows, label, required in (
        (scored.get("companies"), "scored", set(EXPECTED)),
        (gaps.get("companies"), "gaps", set(EXPECTED)),
        (original.get("issuer_reviews"), "original", set(BLOCKED)),
    ):
        if not isinstance(rows, list) or len(rows) != len(required):
            raise ValueError(label + " issuer records incomplete")
        mapped = {}
        for r in rows:
            if (not isinstance(r, dict) or r.get("symbol") not in required
                    or r.get("issuer_id") != EXPECTED.get(r.get("symbol"))
                    or r["symbol"] in mapped):
                raise ValueError(label + " issuer identity mismatch")
            mapped[r["symbol"]] = r
        reports.append(mapped)
    by_score, by_gap, by_original = reports
    if (original.get("network_requests") != 0
            or original.get("accounting_substitutions_approved") is not False
            or original.get("multi_class_valuation_approved") is not False):
        raise ValueError("original SEC evidence re-use or scope policy violated")

    result = {
        "schema_version": 1, "cohort": "US_FIVE_V1",
        "as_of": scored.get("as_of"),
        "market_verified": scored.get("market_verified"),
        "sec_archived": scored.get("sec_archived"),
        "valuation_sources_verified": scored.get("valuation_sources_verified"),
        "companies": [], "investment_approved": False, "real_orders": 0,
        "llm_calls": 0, "participation_confirmed": 0,
        "full_cohort_research_accepted": False,
        "expansion_to_25_approved": False,
    }
    for symbol, cik in COHORT:
        s, g = by_score[symbol], by_gap[symbol]
        if (s.get("investment_approved") is not False
                or s.get("eligible_for_trade") is not False
                or g.get("investment_approved") is not False
                or s.get("participation") != "bilinmiyor"):
            raise ValueError("source score/trade gate not fail-closed")
        score = s.get("score")
        issues = list(g.get("gaps", []))
        if not isinstance(issues, list) or any(not isinstance(x, str) for x in issues):
            raise ValueError("source gap list invalid")
        reviewer = by_original.get(symbol)
        if reviewer is not None:
            if (reviewer.get("source_hash_reverified") is not True
                    or reviewer.get("automatic_substitution") is not False
                    or reviewer.get("score_eligible") is not False):
                raise ValueError("original issuer proof missing or unsafe")
            if not isinstance(reviewer.get("disclosed_concepts"), list):
                raise ValueError("original concept proof absent")
        if score is not None and (s.get("score_status") != "scored_research_hypothesis"
                                  or issues):
            raise ValueError("scored issuer contradicts source gaps")
        if score is None and s.get("score_status") == "scored_research_hypothesis":
            raise ValueError("scored issuer missing score")
        result["companies"].append({
            "symbol": symbol, "issuer_id": cik,
            "research_score": score,
            "score_state": "fully_scored_research_only" if score is not None
                           else "not_scored_original_scope_unresolved",
            "missing_required_facts": [
                r["field"] for r in g.get("missing_required_facts", [])
            ],
            "share_class_status": g.get("share_class_status"),
            "financial_risk_screen": g.get("risk_screen"),
            "original_filing_sha256": reviewer.get("original_source_sha256")
                                      if reviewer else None,
            "original_scope_checked": bool(reviewer),
            "original_scope_candidate_count": sum(
                c.get("status") == "exact_original_value"
                for c in reviewer["disclosed_concepts"]
            ) if reviewer else 0,
            "all_original_candidate_aliases_blocked": True,
            "remaining_gaps": issues,
            "participation": "bilinmiyor",
            "investment_approved": False,
        })
    result["scores_generated"] = sum(r["research_score"] is not None for r in result["companies"])
    result["root_cause_checked"] = sum(r["original_scope_checked"] for r in result["companies"])
    result["research_data_collection_operational"] = (
        result["market_verified"] == result["sec_archived"] == 5)
    result["full_cohort_research_accepted"] = (
        result["research_data_collection_operational"]
        and result["valuation_sources_verified"] == 5
        and result["scores_generated"] == 5
        and all(not r["remaining_gaps"] for r in result["companies"]))
    result["expansion_to_25_approved"] = (
        result["full_cohort_research_accepted"]
        and result["participation_confirmed"] == 5)
    result["decision"] = (
        "BES_SIRKET_TAM_KABUL_YOK"
        if not result["full_cohort_research_accepted"] else
        "FINANSAL_ARASTIRMA_TAM_KATILIM_ONAYI_YOK")
    return result


def markdown(doc):
    lines = [
        "# ABD 5 şirket — tek kanıt setinden son kabul kararı", "",
        "Karar: " + doc["decision"],
        "Fiyat/SEC: " + str(doc["market_verified"]) + "/5, "
            + str(doc["sec_archived"]) + "/5",
        "Kaynaklı değerleme: " + str(doc["valuation_sources_verified"]) + "/5",
        "Finansal skor: " + str(doc["scores_generated"]) + "/5",
        "Katılım uygunluğu: 0/5 doğrulandı",
        "25 şirkete genişleme onayı: HAYIR", "",
        "| Şirket | Araştırma puanı | Özgün belge incelendi | Kanıt engelleri |",
        "|---|---:|---|---|",
    ]
    for row in doc["companies"]:
        lines.append("| " + row["symbol"] + " | "
                     + (str(row["research_score"]) if row["research_score"] is not None else "—")
                     + " | " + ("Evet" if row["original_scope_checked"] else "AAPL/MSFT hazır")
                     + " | " + (", ".join(row["remaining_gaps"]) or "Skor mevcut")
                     + " |")
    lines += ["", "Hiçbir şirket için katılım veya alım izni yok. ",
              "Farklı GAAP kapsamları asıl kanıt ve sürümlü model incelemesi olmadan eşdeğer sayılmaz.",
              "Genişleme kapısının kapalı olması toplu SEC fiyat araştırmasını durdurmaz; "
              "25 şirketin tam onaylandığı iddia edilmez."]
    return "\n".join(lines) + "\n"


def main():
    p = argparse.ArgumentParser()
    for name in ("scored", "gaps", "original", "out", "markdown"):
        p.add_argument("--" + name, required=True)
    a = p.parse_args()
    parse = lambda f: json.loads(Path(f).read_text(encoding="utf-8"))
    d = verdict(parse(a.scored), parse(a.gaps), parse(a.original))
    save_json(a.out, d)
    Path(a.markdown).write_text(markdown(d), encoding="utf-8")
    print(json.dumps({"decision": d["decision"],
                      "scored": d["scores_generated"],
                      "originals": d["root_cause_checked"],
                      "full_cohort_research_accepted": d["full_cohort_research_accepted"],
                      "investment_approved": False}, ensure_ascii=False))


if __name__ == "__main__":
    main()
