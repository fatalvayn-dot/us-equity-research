"""Read-only evidence-gap report for the first US five-company cohort.

Consumes existing SEC/valuation/score-plan artifacts, performs NO requests, never
substitutes one GAAP concept for another, and never approves securities.
"""
import argparse
import json
from collections import Counter
from pathlib import Path

from equity_research.fields import SPECS
from equity_research.mvp import save_json
from equity_research.scoring import ALTERNATE_DEFINITIONS, REQUIRED, V3_ALTERNATE_POLICY
from scripts.unified_us_five import COHORT

ISSUERS = dict(COHORT)
SOURCE_STATES = ("missing", "unsupported_field", "timeout", "not_configured",
                 "invalid_data", "rate_limited", "provider_failure",
                 "collected", "available", "not_found")
FOLLOWUPS = {
    "revenue": "Inspect the exact contract-revenue GAAP concept for the annual period; do not replace it with Revenues.",
    "liabilities": "Inspect original balance-sheet liabilities and independently verified equity bridge; do not infer from debt.",
    "capital_expenditure": "Inspect exact PP&E payments for annual cash-flow period; productive-assets aggregate is not a substitute.",
}


def analyze(sec_report, valuation_report, score_plan):
    sec_rows = sec_report.get("companies") if isinstance(sec_report, dict) else None
    val_rows = valuation_report.get("companies") if isinstance(valuation_report, dict) else None
    exclusions = score_plan.get("excluded") if isinstance(score_plan, dict) else None
    if not all(isinstance(x, list) for x in (sec_rows, val_rows, exclusions)):
        raise ValueError("three existing source artifacts required")

    def index(rows, label):
        found = {}
        for row in rows:
            if not isinstance(row, dict):
                raise ValueError(label + " row malformed")
            sym, cik = row.get("symbol"), row.get("issuer_id")
            if sym not in ISSUERS or cik != ISSUERS[sym] or sym in found:
                raise ValueError(label + " cross-issuer/duplicate evidence")
            found[sym] = row
        return found

    secs = index(sec_rows, "SEC")
    vals = index(val_rows, "valuation")
    if set(secs) != set(ISSUERS) or set(vals) != set(ISSUERS):
        raise ValueError("all five issuer evidence reports required")
    excluded = index(exclusions, "score plan")
    out = {"schema_version": 1, "cohort": "US_FIVE_V1",
           "source_network_requests": 0, "scores_recomputed": False,
           "original_evidence_only": True, "investment_approved": False,
           "eligible_for_trade": False, "companies": []}
    for symbol, cik in COHORT:
        sec, value = secs[symbol], vals[symbol]
        fields = sec.get("fields")
        if not isinstance(fields, list):
            raise ValueError("missing SEC field-level observations")
        lookup = {}
        for field in fields:
            if not isinstance(field, dict):
                raise ValueError("malformed SEC field observation")
            name = field.get("query", {}).get("field") if isinstance(field.get("query"), dict) else None
            if name not in SPECS or name in lookup:
                raise ValueError("duplicate/unregistered SEC accounting field")
            lookup[name] = field
        missing = []
        alternates = []
        for name in REQUIRED:
            row = lookup.get(name)
            if row is not None and row.get("fact") is not None:
                continue
            # Model v3: a declared alternate concept with a collected fact covers the
            # requirement, but only as an explicitly labeled non-equivalent definition.
            alt = ALTERNATE_DEFINITIONS.get(name)
            alt_row = lookup.get(alt) if alt else None
            if alt_row is not None and alt_row.get("fact") is not None:
                alternates.append({"required_field": name, "used_field": alt,
                                   "required_concept": SPECS[name].accounting_definition,
                                   "used_concept": SPECS[alt].accounting_definition,
                                   "policy": V3_ALTERNATE_POLICY})
                continue
            attempts = row.get("attempts", []) if row else []
            statuses = []
            if not isinstance(attempts, list):
                raise ValueError("malformed SEC source attempts")
            for attempt in attempts:
                if not isinstance(attempt, dict):
                    raise ValueError("malformed SEC provider attempt")
                status = attempt.get("status")
                source = attempt.get("source")
                # Provider failures are aggregate observations only; never
                # include dynamic messages or user-provided URLs.
                if isinstance(status, str) and status in SOURCE_STATES and source in (
                        "SEC", "Yahoo", "Nasdaq", "Finnhub"):
                    statuses.append({"source": source, "status": status})
            missing.append({
                "field": name,
                "period_start": row.get("query", {}).get("period_start") if row else None,
                "period_end": row.get("query", {}).get("period_end") if row else None,
                "required_concept": SPECS[name].accounting_definition,
                "source_attempts": statuses,
                "action": FOLLOWUPS.get(name, "Obtain the exact dated annual GAAP concept from original SEC facts."),
                "approved_substitute": None,
            })
        share_status = value.get("share_check", {}).get("status")
        if not isinstance(share_status, str):
            share_status = "unknown"
        gate = sec.get("financial_assessment", {})
        if not isinstance(gate, dict):
            raise ValueError("missing risk assessment")
        risk_status = gate.get("quantitative_gate")
        unresolved = gate.get("unresolved_checks", [])
        if not isinstance(unresolved, list) or any(not isinstance(x, str) for x in unresolved):
            raise ValueError("risk review reasons malformed")
        reason = excluded.get(symbol, {}).get("reason")
        gaps = [x["field"] for x in missing]
        if share_status != "verified_dated_share_class":
            gaps.append("dated_exact_share_class")
        if risk_status != "no_screen_trigger":
            gaps.append("financial_risk_assessment")
        out["companies"].append({
            "symbol": symbol, "issuer_id": cik,
            "missing_required_facts": missing,
            "missing_required_count": len(missing),
            "alternate_definitions_used": alternates,
            "share_class_status": share_status,
            "risk_screen": risk_status,
            "unresolved_risk_checks": sorted(set(unresolved)),
            "score_plan_exclusion": reason,
            "gaps": gaps,
            "technical_research_inputs_complete": not gaps and reason is None,
            "participation": "bilinmiyor",
            "investment_approved": False, "eligible_for_trade": False,
        })
    out["with_missing_required_gaap"] = sum(
        bool(x["missing_required_facts"]) for x in out["companies"])
    out["requires_manual_share_class_review"] = sum(
        x["share_class_status"] != "verified_dated_share_class" for x in out["companies"])
    return out


def markdown(report):
    lines = ["# ABD 5 şirket: doğrulanmış eksik veri ve kaynak denetimi", "",
             "Bu rapor mevcut SEC ve değerleme arşivlerinden hesaplandı. Yeni veri çekilmedi.",
             "Yanlış GAAP eşdeğeri, varsayılan sıfır puan veya katılım onayı kullanılmadı.",
             "", "| Sembol | Eksik temel veri | Hisse sınıfı | Risk kapısı |",
             "|---|---|---|---|"]
    for c in report["companies"]:
        fields = ", ".join(e["field"] for e in c["missing_required_facts"]) or "Yok"
        lines.append("| " + c["symbol"] + " | " + fields + " | "
                     + c["share_class_status"] + " | " + str(c["risk_screen"]) + " |")
    lines.extend(["", "## Gerekli kaynak araştırmaları"])
    for c in report["companies"]:
        for field in c["missing_required_facts"]:
            lines.append("- " + c["symbol"] + " / " + field["required_concept"]
                         + ": " + field["action"])
        if c["share_class_status"] != "verified_dated_share_class":
            lines.append("- " + c["symbol"] + ": Orijinal SEC hisse sınıfı ve tarihli hisse adedi ayrıca doğrulanmalı.")
        if c["unresolved_risk_checks"]:
            lines.append("- " + c["symbol"] + ": Tamamlanmamış risk: "
                         + ", ".join(c["unresolved_risk_checks"]))
    lines.append("\nKatılım ve yeni alım onayı: YOK.")
    return "\n".join(lines) + "\n"


def main():
    p = argparse.ArgumentParser()
    for name in ("sec-report", "valuation-report", "score-plan", "out", "markdown"):
        p.add_argument("--" + name, required=True)
    args = p.parse_args()
    doc = analyze(
        json.loads(Path(args.sec_report).read_text(encoding="utf-8")),
        json.loads(Path(args.valuation_report).read_text(encoding="utf-8")),
        json.loads(Path(args.score_plan).read_text(encoding="utf-8")))
    save_json(args.out, doc)
    Path(args.markdown).write_text(markdown(doc), encoding="utf-8")
    print(json.dumps({"status": "source_gaps_audited",
                      "with_missing_required_gaap": doc["with_missing_required_gaap"],
                      "requires_manual_share_class_review": doc["requires_manual_share_class_review"],
                      "investment_approved": False}, ensure_ascii=False))


if __name__ == "__main__":
    main()
