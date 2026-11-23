"""Bounded SEC CompanyFacts investigation worker with resumable SQLite evidence.

Research only: even exact SEC candidates are NOT routed into production scoring.
Reuse existing SEC transport/cache. One CompanyFacts snapshot per issuer, not field.
"""
import argparse
import json
import re
import sqlite3
from collections import defaultdict
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path

from equity_research.companyfacts import SecCompanyFacts
from equity_research.fields import SPECS
from equity_research.providers import ProviderFailure
from equity_research.transport import HttpTransport
from equity_research.mvp import save_json

ACC = re.compile(r"[0-9]{10}-[0-9]{2}-[0-9]{6}")
HASH = re.compile(r"[0-9a-f]{64}")
TERMINAL = {"exact_candidate", "scope_review_required", "concept_not_disclosed",
            "period_not_disclosed", "source_identity_mismatch", "unsupported_market"}

def inspect(task, response, payload):
    cik=task["issuer_id"]
    result={"task_id":task["task_id"],"symbol":task["symbol"],"issuer_id":cik,
            "field":task["field"],"period_end":task["period_end"],
            "required_concept":task["required_concept"],"status":"source_invalid",
            "value":None,"evidence_sha256":response.sha256,
            "source_url":response.url,"filed_on":None,"accession":None,
            "approved_for_scoring":False,"investment_approved":False}
    if response.url != "https://data.sec.gov/api/xbrl/companyfacts/CIK"+cik+".json" or type(payload.get("cik")) is not int or payload["cik"]!=int(cik):
        result["status"]="source_identity_mismatch";return result
    definition=task["required_concept"]
    if not isinstance(definition,str) or not definition.startswith("us-gaap:"):
        result["status"]="scope_review_required";return result
    taxonomy=payload.get("facts",{}).get("us-gaap",{})
    if not isinstance(taxonomy,dict):
        return result
    concept=taxonomy.get(definition[8:])
    if concept is None:
        result["status"]="concept_not_disclosed";return result
    if not isinstance(concept,dict) or not isinstance(concept.get("units"),dict):
        return result
    records=concept["units"].get("USD",[])
    if not isinstance(records,list):
        return result
    found=[]
    for row in records:
        if not isinstance(row,dict) or row.get("end")!=task["period_end"] or row.get("form") not in ("10-K","10-K/A"):
            continue
        try:
            end=date.fromisoformat(row["end"]);filed=date.fromisoformat(row["filed"])
            accession=row["accn"]
            if not isinstance(accession,str) or not ACC.fullmatch(accession) or filed<end:
                continue
            val=row["val"]
            if type(val) not in (int,Decimal) or not Decimal(val).is_finite():
                continue
            found.append((filed,accession,str(Decimal(val)),row.get("start")))
        except (ValueError,KeyError,TypeError,InvalidOperation):
            continue
    if not found:
        result["status"]="period_not_disclosed";return result
    recent=max(x[0] for x in found)
    selected=[x for x in found if x[0]==recent]
    if len({(x[2],x[3]) for x in selected})!=1:
        result["status"]="scope_review_required";return result
    chosen=max(selected,key=lambda x:x[1])
    result.update(value=chosen[2],filed_on=chosen[0].isoformat(),accession=chosen[1])
    spec=SPECS.get(task["field"])
    # Duration requires an exact known start; missing start must never be inferred.
    if (spec is None or spec.accounting_definition!=definition or
        spec.requires_semantic_model_review or
        (spec.instant and chosen[3] is not None) or
        (not spec.instant and (not chosen[3] or not task.get("period_start") or chosen[3]!=task.get("period_start")))):
        result["status"]="scope_review_required"
    else:
        result["status"]="exact_candidate"
    return result

def recover(plan, *, db_path, fetcher, max_issuers=10):
    if type(max_issuers) is not int or not 1<=max_issuers<=200:
        raise ValueError("bounded issuer budget required")
    tasks=plan.get("tasks") if isinstance(plan,dict) else None
    if not isinstance(tasks,list):
        raise ValueError("valid recovery task plan required")
    groups=defaultdict(list);seen=set()
    for task in tasks:
        if not isinstance(task,dict):
            raise ValueError("invalid recovery task")
        key=task.get("task_id")
        cik=task.get("issuer_id")
        if not isinstance(key,str) or not HASH.fullmatch(key) or key in seen:
            raise ValueError("invalid task hash/duplicate")
        seen.add(key)
        if task.get("investment_approved",False) is not False or task.get("automatic_substitution",False) is not False:
            raise ValueError("unsafe task flags")
        if task.get("market")=="US":
            if not isinstance(cik,str) or not re.fullmatch(r"[0-9]{10}",cik) or int(cik)==0:
                raise ValueError("canonical US CIK required")
            groups[cik].append(task)
        else:
            groups["other:"+key].append(task)
    db=Path(db_path);db.parent.mkdir(parents=True,exist_ok=True)
    observations=[];fetches=0
    with sqlite3.connect(db) as con:
        con.execute("""CREATE TABLE IF NOT EXISTS recovery_observations (
            task_id TEXT PRIMARY KEY, status TEXT NOT NULL, evidence TEXT NOT NULL)""")
        selected=0
        for group, jobs in groups.items():
            prior={}
            for job in jobs:
                saved=con.execute("SELECT status,evidence FROM recovery_observations WHERE task_id=?",(job["task_id"],)).fetchone()
                if saved is not None and saved[0] in TERMINAL:
                    prior[job["task_id"]]=json.loads(saved[1])
            pending=[j for j in jobs if j["task_id"] not in prior]
            observations.extend(prior.values())
            if not pending:
                continue
            if selected>=max_issuers:
                continue
            selected+=1
            if group.startswith("other:"):
                new=[{"task_id":j["task_id"],"symbol":j["symbol"],"issuer_id":j["issuer_id"],
                      "field":j["field"],"status":"unsupported_market","value":None,
                      "approved_for_scoring":False,"investment_approved":False} for j in pending]
            else:
                try:
                    response,payload=fetcher.snapshot(group)
                    fetches+=1
                    new=[inspect(j,response,payload) for j in pending]
                except ProviderFailure as exc:
                    new=[{"task_id":j["task_id"],"symbol":j["symbol"],"issuer_id":group,
                          "field":j["field"],"status":"provider_"+exc.status.value,
                          "value":None,"approved_for_scoring":False,"investment_approved":False} for j in pending]
                except (ValueError,KeyError,TypeError):
                    new=[{"task_id":j["task_id"],"symbol":j["symbol"],"issuer_id":group,
                          "field":j["field"],"status":"invalid_source_response",
                          "value":None,"approved_for_scoring":False,"investment_approved":False} for j in pending]
            for item in new:
                con.execute("INSERT OR REPLACE INTO recovery_observations VALUES (?,?,?)",
                            (item["task_id"],item["status"],json.dumps(item,ensure_ascii=False,sort_keys=True)))
            con.commit()
            observations.extend(new)
    return {"schema_version":1,"observations":observations,
            "tasks_received":len(tasks),"observed":len(observations),
            "deferred":len(tasks)-len(observations),"network_fetches":fetches,
            "scores_generated":0,"automatic_substitution":False,
            "investment_approved":False,"expansion_to_25_approved":False}

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--plan",required=True)
    p.add_argument("--db",required=True)
    p.add_argument("--out",required=True)
    p.add_argument("--user-agent",required=True)
    p.add_argument("--max-issuers",type=int,default=5)
    a=p.parse_args()
    transport=HttpTransport(user_agent=a.user_agent,allowed_hosts={"data.sec.gov"})
    provider=SecCompanyFacts(transport,cache_dir=Path(a.db).parent/"companyfacts")
    result=recover(json.loads(Path(a.plan).read_text(encoding="utf-8")),
                   db_path=a.db,fetcher=provider,max_issuers=a.max_issuers)
    save_json(a.out,result)
    print(json.dumps({"observed":result["observed"],"deferred":result["deferred"],
                      "network_fetches":result["network_fetches"],"scores_generated":0}))

if __name__=="__main__":
    main()
