"""Diagnose real score valuation blockers using the exact valuation source run.

No missing value is filled. A score is never inferred from a previous cutoff.
"""
import argparse
import gzip
import json
from collections import Counter
from datetime import datetime
from pathlib import Path


LEGS=("share_check","price_check","history_check")
VALID={"share_check":"verified_dated_share_class",
       "price_check":"valid","history_check":"valid"}
MARKET_BLOCKER="valuation_source_evidence_required"


def diagnose(score, valuation):
    if (not isinstance(score.get("companies"),list)
            or not isinstance(valuation.get("companies"),list)
            or valuation.get("report_kind") != "valuation_source_collection_scope_pending"):
        raise ValueError("kaynaklı skor ve değerleme raporları gerekli")
    if (score.get("summary",{}).get("candidates")!=100
            or valuation.get("summary",{}).get("candidates")!=100
            or len(score["companies"])!=100 or len(valuation["companies"])!=100):
        raise ValueError("her iki kaynak da 100 tam aday içermeli")
    score_date=datetime.fromisoformat(score["as_of"])
    market_date=datetime.fromisoformat(valuation["as_of"])
    if (score_date.utcoffset() is None or market_date.utcoffset() is None
            or market_date>score_date):
        raise ValueError("değerleme kesimi skor kesiminden ileri olamaz")
    def keyed(rows):
        out={}
        for row in rows:
            key=(row.get("symbol"),row.get("issuer_id"))
            if (not all(type(v) is str and v for v in key)
                    or key in out):
                raise ValueError("tekrarlı veya hatalı sembol/CIK")
            out[key]=row
        return out
    by_score=keyed(score["companies"])
    by_market=keyed(valuation["companies"])
    if by_score.keys()!=by_market.keys():
        raise ValueError("skor ve değerleme şirket kimlikleri uyuşmuyor")
    blockers=[]
    observed=Counter()
    for key,row in by_score.items():
        reasons=row.get("blockers",[])
        if not isinstance(reasons,list):
            raise ValueError("skor engelleri bozuk")
        if MARKET_BLOCKER not in reasons:
            continue
        market=by_market[key]
        details={}
        stages=[]
        for leg in LEGS:
            value=market.get(leg)
            if not isinstance(value,dict) or not isinstance(value.get("status"),str):
                raise ValueError("eksik değerleme kaynak bacağı")
            details[leg]=dict(status=value["status"],
                              deferred_reason=value.get("deferred_reason"))
        attempts=market.get("attempts",[])
        if not isinstance(attempts,list):
            raise ValueError("kaynak denemeleri listesi geçersiz")
        for attempt in attempts:
            if not isinstance(attempt,dict) or not isinstance(attempt.get("stage"),str):
                raise ValueError("kaynak denemesi bozuk")
            stages.append(dict(stage=attempt["stage"],
                               status=attempt.get("status"),
                               requested=attempt.get("http_requested") is True,
                               deferred_reason=attempt.get("deferred_reason")))
        for leg,expect in VALID.items():
            if details[leg]["status"] != expect:
                observed[leg+":"+details[leg]["status"]]+=1
        blockers.append(dict(symbol=key[0],issuer_id=key[1],
                             identity_status=market.get("identity_status"),
                             market_source_states=details,
                             attempted_stages=stages,
                             new_gets=sum(a["requested"] for a in stages),
                             score_blockers=reasons,
                             score=None,investment_approved=False))
    return dict(schema_version=1,report_kind="score_valuation_source_gap_trace",
                score_as_of=score["as_of"],valuation_as_of=valuation["as_of"],
                candidates=100,scored_companies=score["summary"].get("scored_companies"),
                valuation_source_blockers=len(blockers),
                source_stage_counts=dict(sorted(observed.items())),
                companies=blockers,mvp_accepted=False,
                limitations=["not_a_new_valuation_or_investment_score",
                             "source_states_only","all_missing_values_remain_missing"])


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--score-report",type=Path,required=True)
    parser.add_argument("--valuation-report",type=Path,required=True)
    parser.add_argument("--output",type=Path,required=True)
    args=parser.parse_args()
    report=json.loads(gzip.decompress(args.score_report.read_bytes()))
    valuation=json.loads(args.valuation_report.read_text())
    result=diagnose(report,valuation)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(result,ensure_ascii=False,sort_keys=True,
                                       indent=2)+"\n")
    print(json.dumps({k:result[k] for k in ("scored_companies",
        "valuation_source_blockers","source_stage_counts")},ensure_ascii=False))


if __name__=="__main__":
    main()
