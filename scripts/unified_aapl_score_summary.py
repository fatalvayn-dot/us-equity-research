"""AAPL-only summary of existing 0-100 research scorer; zero is NEVER a missing score."""
import argparse
import gzip
import json
from pathlib import Path
from decimal import Decimal, InvalidOperation

WEIGHTS = {"financial_strength": 20, "valuation": 20, "growth": 20,
           "profitability": 15, "cash_flow": 15, "risk": 10}
from equity_research.mvp import save_json

CIK = "0000320193"

def summarize_score(report):
    if not isinstance(report, dict) or len(report.get("companies", [])) != 1:
        raise ValueError("exactly one scoring company required")
    c = report["companies"][0]
    if c.get("symbol") != "AAPL" or c.get("issuer_id") != CIK:
        raise ValueError("score issuer mismatch")
    status = c.get("status")
    score = c.get("total_score")
    if (score is not None and
        (status != "scored_research_hypothesis" or
         isinstance(score, bool) or not isinstance(score, (int, float, str)))):
        raise ValueError("unsupported score output")
    raw_components = c.get("components", {})
    components = {}
    if score is not None:
        if not isinstance(raw_components, dict) or set(raw_components) != set(WEIGHTS):
            raise ValueError("complete existing scoring component evidence required")
        try:
            for name, cap in WEIGHTS.items():
                part = raw_components[name]
                if not isinstance(part, dict) or Decimal(str(part.get("weight"))) != cap:
                    raise ValueError("component weight mismatch")
                value = Decimal(str(part.get("score")))
                if not value.is_finite() or not 0 <= value <= cap:
                    raise ValueError("component out of range")
                components[name] = {"score": str(value), "max": cap}
            total = Decimal(str(score))
            if not total.is_finite() or sum(Decimal(v["score"]) for v in components.values()) != total:
                raise ValueError("component sum differs from total")
        except (InvalidOperation, TypeError):
            raise ValueError("scoring component value invalid") from None
    blockers = c.get("blockers", [])
    if not isinstance(blockers, list) or not all(isinstance(x, str) for x in blockers):
        raise ValueError("invalid scoring blockers")
    return {
        "symbol": "AAPL", "issuer_id": CIK,
        "score": score if status == "scored_research_hypothesis" else None,
        "score_status": status,
        "score_components": components,
        "blockers": blockers,
        "model_version": c.get("model_version"),
        "rank": None, "investment_approved": False,
        "eligible_for_trade": False,
        "source_report_kind": report.get("report_kind", "research_scoring"),
        "as_of": report.get("as_of"),
    }

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--input", required=True)
    p.add_argument("--out", required=True)
    args = p.parse_args()
    raw = Path(args.input).read_bytes()
    report = json.loads(gzip.decompress(raw) if args.input.endswith(".gz") else raw)
    result = summarize_score(report)
    save_json(args.out, result)
    print(json.dumps(result, ensure_ascii=False))
if __name__ == "__main__":
    main()
