"""Kaynak doğrulaması bekleyen şirketleri değiştirmeden raporla.

This consumes a completed valuation source report, not provider data.
It never converts a pending/rejected source into a valid observation.
"""
import argparse
import json
from collections import Counter
from pathlib import Path


LEGS = ("share_check", "price_check", "history_check")
PASS = {"share_check": "verified_dated_share_class",
        "price_check": "valid", "history_check": "valid"}
REQUIRED = {"symbol", "issuer_id", "identity_status", *LEGS}


def audit(report, plan):
    companies = report.get("companies")
    wanted = plan.get("companies")
    if (report.get("report_kind") != "valuation_source_collection_scope_pending"
            or not isinstance(companies, list) or not companies
            or not isinstance(wanted, list)):
        raise ValueError("geçerli değerleme raporu ve aday listesi gerekli")
    by_key = {}
    for company in companies:
        if not isinstance(company, dict) or not REQUIRED <= company.keys():
            raise ValueError("eksik değerleme şirket alanları")
        key = (company["symbol"], company["issuer_id"])
        if not all(isinstance(v, str) and v for v in key) or key in by_key:
            raise ValueError("tekrarlı veya bozuk şirket kimliği")
        by_key[key] = company
    if (report.get("summary", {}).get("candidates") != len(companies)
            or len(companies) != 100):
        raise ValueError("100 adaylı kaynak raporu bekleniyor")
    selected = []
    seen = set()
    for candidate in wanted:
        key = (candidate.get("symbol"), candidate.get("issuer_id"))
        if key in seen or key not in by_key:
            raise ValueError("aday kimliği ana raporla uyuşmuyor")
        seen.add(key)
        selected.append(key)
    if len(selected) == 0:
        raise ValueError("boş öncelik listesi")
    def row_for(key, *, prioritized):
        c = by_key[key]
        statuses = {}
        for leg in LEGS:
            detail = c[leg]
            if not isinstance(detail, dict) or not isinstance(detail.get("status"), str):
                raise ValueError("kaynak bacağı durumu eksik")
            statuses[leg] = detail["status"]
        attempts = c.get("attempts", [])
        if not isinstance(attempts, list):
            raise ValueError("kaynak istek geçmişi bozuk")
        pending = []
        for leg in LEGS:
            if statuses[leg] != PASS[leg]:
                pending.append(dict(leg=leg, status=statuses[leg],
                                    deferred_reason=c[leg].get("deferred_reason")))
        return dict(symbol=key[0], issuer_id=key[1],
                    prioritized=prioritized, identity_status=c["identity_status"],
                    market_evidence_complete=(c["identity_status"] == "exact_match"
                                              and not pending),
                    blockers=pending, source_gets=sum(a.get("http_requested") is True
                                                      for a in attempts if isinstance(a, dict)),
                    attempted_stages=list(dict.fromkeys(a.get("stage") for a in attempts
                                       if isinstance(a, dict) and isinstance(a.get("stage"), str))),
                    validation={leg:statuses[leg] for leg in LEGS})
    priority=[row_for(k,prioritized=True) for k in selected]
    remaining=[row_for(k,prioritized=False) for k in by_key if k not in seen]
    all_rows=priority+remaining
    return dict(schema_version=1, report_kind="valuation_source_blocker_audit",
                valuation_as_of=report.get("as_of"),
                candidates=len(all_rows), priority_candidates=len(priority),
                priority_complete=sum(r["market_evidence_complete"] for r in priority),
                all_complete=sum(r["market_evidence_complete"] for r in all_rows),
                priority_gets=sum(r["source_gets"] for r in priority),
                blocker_counts=dict(Counter((b["leg"], b["status"]) for r in all_rows
                                            for b in r["blockers"])),
                priority=priority, other_companies=remaining,
                mvp_accepted=False,
                limitations=["source_states_only_not_financial_or_score_acceptance",
                             "no_expired_price_reused_as_current",
                             "no_unverified_score"])


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report",type=Path,required=True)
    parser.add_argument("--priority-plan",type=Path,required=True)
    parser.add_argument("--output",type=Path,required=True)
    args=parser.parse_args()
    result=audit(json.loads(args.report.read_text()),
                 json.loads(args.priority_plan.read_text()))
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(result,ensure_ascii=False,indent=2,
                                     sort_keys=True)+"\n")
    print(json.dumps({k:result[k] for k in ("candidates","priority_candidates",
          "priority_complete","all_complete","priority_gets")},ensure_ascii=False))


if __name__=="__main__":
    main()
