"""Generic bounded, evidence-first missing-field planner for any market universe.

No provider requests or score changes. Plans only; source recovery adapters
must verify original filing/period/unit/definition before writing evidence.
"""
import argparse
import hashlib
import json
import re
from pathlib import Path

MARKETS={"US","BIST","EU"}
PROVIDERS={"Yahoo","SEC","Nasdaq","Finnhub","KAP","ESEF","CompanyIR"}
RETRYABLE={"timeout","provider_failure","invalid_data","not_configured","rate_limited"}
ACCOUNTING_FIELDS={"revenue","liabilities","capital_expenditure","net_income",
                   "assets","operating_cash_flow","current_assets","current_liabilities"}
SCOPE_REVIEW={"revenue","liabilities","capital_expenditure",
              "dated_exact_share_class"}
REGISTRY={
    "US":{"primary":"SEC","alternatives":["CompanyIR","Nasdaq","Finnhub"]},
    "BIST":{"primary":"KAP","alternatives":["CompanyIR"]},
    "EU":{"primary":"ESEF","alternatives":["CompanyIR"]},
}

def _key(market,issuer,field,period):
    value=json.dumps([market,issuer,field,period],separators=(",",":"),ensure_ascii=True)
    return hashlib.sha256(value.encode("utf-8")).hexdigest()

def plan(report, *, previous=None, max_tasks=500):
    if type(max_tasks) is not int or not 1<=max_tasks<=10000:
        raise ValueError("bounded task limit required")
    companies=report.get("companies") if isinstance(report,dict) else None
    if not isinstance(companies,list):
        raise ValueError("company rows required")
    prior=previous.get("tasks",[]) if isinstance(previous,dict) else []
    if not isinstance(prior,list):
        raise ValueError("invalid prior tasks")
    cached={}
    for row in prior:
        if not isinstance(row,dict) or not isinstance(row.get("task_id"),str) or row["task_id"] in cached:
            raise ValueError("invalid or duplicate cache")
        cached[row["task_id"]]=row
    seen_companies={}
    unique={}
    for company in companies:
        if not isinstance(company,dict):
            raise ValueError("invalid company row")
        market=company.get("market","US")
        sym=company.get("symbol")
        issuer=company.get("issuer_id")
        period=company.get("period_end") or "unspecified"
        if market not in MARKETS or not isinstance(sym,str) or not re.fullmatch(r"[A-Za-z0-9.\-]{1,24}",sym) or not isinstance(issuer,str) or not re.fullmatch(r"[A-Za-z0-9.\-]{1,32}",issuer):
            raise ValueError("invalid market or issuer identity")
        identity=(market,issuer)
        if identity in seen_companies and seen_companies[identity]!=sym:
            raise ValueError("issuer identity collision")
        seen_companies[identity]=sym
        findings=company.get("missing_required_facts")
        if not isinstance(findings,list):
            raise ValueError("missing required fact list")
        for fact in findings:
            if not isinstance(fact,dict):
                raise ValueError("invalid fact record")
            field=fact.get("field")
            definition=fact.get("required_concept")
            if not isinstance(field,str) or not re.fullmatch(r"[a-z][a-z0-9_]{0,79}",field) or not isinstance(definition,str) or not definition.strip():
                raise ValueError("invalid field accounting definition")
            attempts=fact.get("source_attempts",[])
            if not isinstance(attempts,list) or any(not isinstance(x,dict) for x in attempts):
                raise ValueError("invalid provider observations")
            key=_key(market,issuer,field,period)
            if key in unique:
                old=unique[key]
                if old["required_concept"]!=definition or old["symbol"]!=sym:
                    raise ValueError("conflicting field evidence")
                continue
            statuses=[{"source":x.get("source"),"status":x.get("status")}
                      for x in attempts if x.get("source") in PROVIDERS and isinstance(x.get("status"),str)]
            if any(a["status"]=="rate_limited" for a in statuses):
                route="provider_cooldown"
            elif field in SCOPE_REVIEW:
                route="accounting_scope_review"
            elif any(a["status"] in RETRYABLE for a in statuses):
                route="retry_with_budget"
            else:
                route="source_discovery"
            unique[key]={
                "task_id":key,"market":market,"symbol":sym,"issuer_id":issuer,
                "field":field,"period_end":period,"required_concept":definition,
                "source_attempts":statuses,"route":route,
                "primary_source":REGISTRY[market]["primary"],
                "backup_sources":REGISTRY[market]["alternatives"],
                "approved_value":None,"approved_substitute":None,
                "automatic_substitution":False,"investment_approved":False,
            }
    cached_verified=0
    open_tasks=[]
    for task in unique.values():
        prev=cached.get(task["task_id"])
        if prev and prev.get("status")=="verified_exact" and isinstance(prev.get("evidence_sha256"),str) and re.fullmatch("[a-fA-F0-9]{64}",prev["evidence_sha256"]):
            cached_verified+=1
            continue
        if prev and prev.get("status")=="verified_exact":
            raise ValueError("cached verified evidence lacks SHA")
        open_tasks.append(task)
    priority={"accounting_scope_review":0,"source_discovery":1,"retry_with_budget":2,"provider_cooldown":3}
    open_tasks.sort(key=lambda t:(priority[t["route"]],t["market"],t["issuer_id"],t["field"]))
    selection=open_tasks[:max_tasks]
    return {
        "schema_version":1,"purpose":"missing_data_recovery_plan",
        "total_companies":len(companies),"total_unique_gaps":len(unique),
        "cached_verified":cached_verified,"deferred_count":len(open_tasks)-len(selection),
        "tasks":selection,"network_requests":0,"scores_generated":0,
        "investment_approved":False,"automatic_substitution":False,
        "score_pipeline_modified":False
    }

def markdown(data):
    out=["# Eksik veri kurtarma planı","",
         f"Şirket: {data['total_companies']} · Tekil eksik: {data['total_unique_gaps']} · Kuyruk: {len(data['tasks'])} · Ertelenen: {data['deferred_count']}",
         "", "Bu yalnızca araştırma planıdır; doğrulanmış yeni veri, puan veya alım izni üretmez.","",
         "| Piyasa | Şirket | Alan | İşlem yönü |","|---|---|---|---|"]
    for r in data["tasks"]:
        out.append(f"| {r['market']} | {r['symbol']} | {r['field']} | {r['route']} |")
    return "\n".join(out)+"\n"

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--gaps",required=True)
    p.add_argument("--previous")
    p.add_argument("--limit",type=int,default=500)
    p.add_argument("--out",required=True)
    p.add_argument("--markdown",required=True)
    a=p.parse_args()
    read=lambda x:json.loads(Path(x).read_text(encoding="utf-8"))
    result=plan(read(a.gaps),previous=read(a.previous) if a.previous else None,max_tasks=a.limit)
    Path(a.out).write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    Path(a.markdown).write_text(markdown(result),encoding="utf-8")
    print(json.dumps({"unique_gaps":result["total_unique_gaps"],
                      "queued":len(result["tasks"]),"deferred":result["deferred_count"]}))
if __name__=="__main__":
    main()
