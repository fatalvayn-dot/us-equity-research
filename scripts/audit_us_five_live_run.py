"""Prove actual five-company live artifacts exist; research blockers stay visible."""
import argparse
import json
from pathlib import Path

SYMS={"AAPL","MSFT","NVDA","AMZN","GOOGL"}

def audit(files):
    blockers=[]
    stages={}
    for name in ("sec","scored","gaps","verdict"):
        doc=files.get(name)
        rows=doc.get("companies") if isinstance(doc,dict) else None
        valid=isinstance(rows,list) and len(rows)==5 and {
            x.get("symbol") for x in rows if isinstance(x,dict)}==SYMS
        stages[name]={"artifact_present":doc is not None,"five_distinct_issuers":valid}
        if not valid:
            blockers.append({"sec":"sec_evidence_missing","scored":"scoring_artifact_missing",
                             "gaps":"gap_diagnostics_missing","verdict":"final_verdict_missing"}[name])
    scored=files.get("scored") or {}
    verdict=files.get("verdict") or {}
    scored_n=0
    if stages["scored"]["five_distinct_issuers"]:
        scored_n=sum(x.get("score") is not None for x in scored["companies"])
        if scored.get("fully_scored")!=scored_n:
            blockers.append("score_count_inconsistent")
        if scored_n!=5:
            blockers.append("only_"+str(scored_n)+"_of_5_scored")
    if stages["verdict"]["five_distinct_issuers"]:
        if verdict.get("scores_generated")!=scored_n:
            blockers.append("verdict_score_count_inconsistent")
        if not verdict.get("full_cohort_research_accepted"):
            blockers.append("full_research_not_accepted")
    gap=files.get("gaps") or {}
    if stages["gaps"]["five_distinct_issuers"]:
        remaining={x["symbol"]:x.get("gaps",[]) for x in gap["companies"]}
        if any(not isinstance(g,list) or g for g in remaining.values()):
            blockers.append("required_source_or_valuation_gaps")
    recovery=files.get("recovery")
    observations=recovery.get("observations",[]) if isinstance(recovery,dict) else []
    candidates=sum(1 for x in observations if isinstance(x,dict) and x.get("status")=="exact_candidate")
    success=(not blockers and verdict.get("full_cohort_research_accepted") is True)
    return {"schema_version":1,"cohort":"US_FIVE_V1","stages":stages,
            "scored":scored_n,"recovery_candidates":candidates,
            "critical_blockers":blockers,"technical_research_accepted":success,
            "participation_verified":False,"investment_approved":False,
            "expansion_approved":False,"network_requests_this_audit":0}

def main():
    p=argparse.ArgumentParser()
    for name in ("sec","scored","gaps","verdict","recovery"):
        p.add_argument("--"+name)
    p.add_argument("--out",required=True)
    args=p.parse_args()
    def load(path):
        if not path or not Path(path).is_file():
            return None
        try:return json.loads(Path(path).read_text(encoding="utf-8"))
        except (ValueError,UnicodeError):return None
    data=audit({k:load(getattr(args,k)) for k in ("sec","scored","gaps","verdict","recovery")})
    Path(args.out).write_text(json.dumps(data,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({"technical_research_accepted":data["technical_research_accepted"],
                     "scored":data["scored"],"critical_blockers":data["critical_blockers"]}))
    if not data["technical_research_accepted"]:
        raise SystemExit(1)
if __name__=="__main__":main()
