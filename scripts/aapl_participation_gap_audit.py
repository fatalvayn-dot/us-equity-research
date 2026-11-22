"""AAPL-only missing participation evidence worklist, no made-up ratio facts.

Reuse the existing participation screen. Output exact evidence fields and safe
research actions without presuming Sharia approval or original SEC observations.
"""
import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from equity_research.mvp import save_json
from equity_research.participation_screen import assess_participation

AAPL_KEY = "SEC:0000320193"
REQUIRED = {
    "reviewed_standard_evidence_missing": (
        "official_methodology", "Archive original, dated Sharia index methodology "
        "PDF and its SHA-256; review effective version and each numerator and denominator."),
    "sector_evidence_unverified": (
        "issuer_sector", "Verify SEC submissions CIK, SIC and nonfinancial "
        "activity using original retrieved bytes and source SHA-256."),
    "special_instrument_review_required": (
        "instrument_class", "Verify AAPL common-share security class, CUSIP and "
        "exact SEC/market issuer identity; do not infer from ticker alone."),
    "security_type_evidence_unverified": (
        "instrument_original", "Archive SEC original share-class disclosure with timestamp and SHA-256."),
    "business_activity_evidence_unverified": (
        "business_segments", "Review all reported business segments and revenue "
        "sources using original SEC annual filing; no assumed permitted status."),
    "interest_debt_unverified_or_incompatible": (
        "interest_bearing_debt", "Source interest-bearing debt numerator from "
        "SEC footnotes and independently calculate the standard-defined denominator."),
    "impermissible_income_unverified_or_incompatible": (
        "nonpermitted_revenue", "Review interest revenue and impermissible "
        "activities, then reconcile to total business revenue in original SEC disclosures."),
    "interest_cash_securities_unverified_or_incompatible": (
        "cash_ratio_if_applicable", "Collect interest-bearing cash/securities "
        "only if the reviewed effective standard actually requires this ratio."),
}


def audit(evidence, as_of):
    if not isinstance(evidence, dict):
        raise ValueError("participation package must be object")
    company = evidence.get("company")
    if not isinstance(company, dict) or company.get("symbol") != "AAPL" or company.get("issuer_key") != AAPL_KEY:
        raise ValueError("exact AAPL issuer evidence required")
    screen = assess_participation(company, evidence.get("rulebook"), as_of=as_of)
    reasons = set(screen.get("review_reasons", []))
    rulebook = evidence.get("rulebook")
    rules = rulebook.get("ratios", {}) if isinstance(rulebook, dict) else {}
    if "reviewed_standard_evidence_missing" in reasons:
        # The rulebook is absent or invalid. All optional accounting inputs
        # must stay flagged, even if the existing screen cannot run those rules.
        reasons |= {"interest_debt_unverified_or_incompatible",
                    "impermissible_income_unverified_or_incompatible"}
    elif isinstance(rules, dict):
        for ratio in rules:
            if ratio in ("interest_debt", "impermissible_income", "interest_cash_securities"):
                if ratio not in screen.get("ratios", {}):
                    reasons.add(ratio + "_unverified_or_incompatible")
    tasks = [{"id": REQUIRED[code][0], "screen_reason": code,
              "action": REQUIRED[code][1]}
             for code in sorted(reasons) if code in REQUIRED]
    unknown = sorted(reasons - set(REQUIRED))
    return {
        "schema_version": 1, "symbol": "AAPL", "issuer_key": AAPL_KEY,
        "as_of": screen["as_of"], "screen_status": screen["status"],
        "source_verification": "not_independently_verified",
        "rulebook_id": screen.get("rulebook_id"),
        "rulebook_version": screen.get("rulebook_version"),
        "applied_rules": screen.get("applied_rules", []),
        "tasks": tasks,
        "other_review_reasons": unknown,
        "blocking_exclusions": screen.get("blockers", []),
        "all_evidence_completed": False,
        "investment_approved": False,
        "eligible_for_trade": False,
    }


def markdown(result):
    lines = ["# AAPL katılım kanıtı eksik işler", "",
             "Mevcut tarama: " + result["screen_status"],
             "Bağımsız kaynak doğrulaması: YOK",
             "Alım onayı: YOK", "",
             "## Kanıt toplama işleri"]
    for task in result["tasks"]:
        lines.append("- " + task["id"] + " (" + task["screen_reason"] + "): " + task["action"])
    for reason in result["other_review_reasons"]:
        lines.append("- Ek ekran engeli: " + reason)
    return "\n".join(lines) + "\n"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--markdown", required=True)
    args = ap.parse_args()
    package = json.loads(Path(args.input).read_text(encoding="utf-8"))
    now = datetime.now(timezone.utc).isoformat()
    result = audit(package, now)
    save_json(args.out, result)
    Path(args.markdown).write_text(markdown(result), encoding="utf-8")
    print(json.dumps({"status": result["screen_status"], "task_count": len(result["tasks"]),
                      "investment_approved": False}, ensure_ascii=False))


if __name__ == "__main__":
    main()
