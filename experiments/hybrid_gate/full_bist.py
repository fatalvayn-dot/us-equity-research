"""BIST universe discovery + Stage 2 Sharia screening; research only.

Candidate sources: yfinance/Yahoo and Google Finance Scraper. No SEC or other
universe providers. A provider's reported total is not an authoritative
exchange census. Undiscovered assets cannot be claimed screened.
"""
import argparse
import concurrent.futures
from collections import Counter
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import sys
import threading
import time

from experiments.hybrid_gate.run import (collect_google, financial_snapshot,
                                          screen_snapshot)

def now():
    return datetime.now(timezone.utc).isoformat()

def write(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp=path.with_suffix(path.suffix+".tmp")
    temp.write_text(json.dumps(obj,indent=2,ensure_ascii=False))
    temp.replace(path)

def normalize_yahoo(entry):
    ticker=str(entry.get("symbol") or "").strip().upper()
    exch=str(entry.get("exchange") or "").upper()
    kind=str(entry.get("quoteType") or "").upper()
    if not re.fullmatch(r"[A-Z0-9-]+\\.IS",ticker) or exch!="IST" or kind!="EQUITY":
        return None
    return {"symbol":ticker,"company_name":entry.get("shortName") or entry.get("longName") or ticker,
            "exchange":exch,"asset_class":kind,"source":["yfinance"],"google_symbol":None,
            "price":entry.get("regularMarketPrice") or entry.get("intradayprice")}

def discover_yahoo(page_size=250,max_pages=30):
    from yfinance import EquityQuery
    import yfinance as yf
    results={}
    pages=[]
    errors=[]
    total=None
    observed=0
    q=EquityQuery("eq",["region","tr"])
    for i in range(max_pages):
        offset=i*page_size
        try:
            payload=yf.screen(q,offset=offset,size=page_size,
                              sortField="intradaymarketcap",sortAsc=False)
        except Exception as exc:
            errors.append({"page":i,"offset":offset,"error":str(exc)[:240]})
            break
        quotes=payload.get("quotes",[]) or []
        if total is None:
            total=payload.get("total")
        filtered=0
        for entry in quotes:
            row=normalize_yahoo(entry)
            if row is not None:
                if row["symbol"] not in results:
                    results[row["symbol"]]=row
                filtered+=1
        pages.append({"offset":offset,"returned":len(quotes),"accepted_as_BIST_equity":filtered})
        print("DISCOVERY_PAGE",json.dumps(pages[-1]),flush=True)
        observed+=len(quotes)
        if not quotes or len(quotes)<page_size:
            break
        if isinstance(total,int) and observed>=total:
            break
        time.sleep(1.3)
    complete=(not errors and bool(pages) and
              (pages[-1]["returned"]<page_size or (isinstance(total,int) and observed>=total)))
    return results,{"provider":"yfinance","provider_reported_total":total,
                    "records_returned":observed,"strict_IST_equities":len(results),
                    "pages":pages,"errors":errors,"pagination_exhausted":complete}

def discover_google(base,limit):
    # Google Finance discovery surfaces market movers, trending and search,
    # not a full listings API. Document coverage accordingly.
    rows,warnings=collect_google(base,"BIST",limit)
    accepted={}
    for row in rows:
        ticker=str(row.get("yahoo_symbol") or "").upper()
        if re.fullmatch(r"[A-Z0-9-]+\\.IS",ticker):
            accepted[ticker]={"symbol":ticker,"company_name":row.get("name") or ticker,
                              "exchange":"IST","asset_class":"EQUITY_UNVERIFIED",
                              "google_symbol":row.get("google_symbol"),
                              "source":["google_finance"],"price":None}
    return accepted,{"provider":"google_finance","discovered":len(accepted),
                     "not_exhaustive":True,"warnings":warnings}

def discover(base,max_pages):
    yy,yreport=discover_yahoo(max_pages=max_pages)
    gg,greport=discover_google(base,1000)
    for ticker,row in gg.items():
        if ticker in yy:
            yy[ticker]["source"].append("google_finance")
            yy[ticker]["google_symbol"]=row["google_symbol"]
        else:
            yy[ticker]=row
    rows=sorted(yy.values(),key=lambda x:x["symbol"])
    return rows,{"created_utc":now(),"yfinance":yreport,"google_finance":greport,
                 "unique_symbols":len(rows),
                 "all_bist_claim_verified":False,
                 "reason":"Google Finance provides no exhaustive BIST listings, Yahoo total may include excluded instruments or omit listings"}

def screen_one(row):
    import yfinance as yf
    result={"symbol":row["symbol"],"company_name":row["company_name"],
            "source":row["source"],"status":"belirsiz","reason":"not_evaluated",
            "missing":[],"snapshot_date":None,"eligibility_certificate":False}
    try:
        if row["asset_class"]!="EQUITY":
            result["reason"]="stock_type_not_confirmed"
            return result
        ticker=yf.Ticker(row["symbol"])
        facts,sector,industry,date,_info=financial_snapshot(ticker)
        result["snapshot_date"]=date
        result["sector"]=sector
        result["industry"]=industry
        sys.path.insert(0,"/tmp/halal-stock-analyst")
        from src.screening import screen_company
        decision=screen_snapshot(facts,sector,industry,screen_company)
        result.update(decision)
        result["facts_presence"]={k:v is not None for k,v in facts.items()}
        result["methodology"]="halal-stock-analyst MIT self-described variant, NOT certified BIST Participation Index/AAOIFI"
    except Exception as exc:
        result["reason"]="provider_or_adapter_error"
        result["error"]=f"{type(exc).__name__}: {str(exc)[:260]}"
    return result

def run():
    ap=argparse.ArgumentParser()
    ap.add_argument("--google-base",default="http://127.0.0.1:8000")
    ap.add_argument("--output",default="bist_full_output")
    ap.add_argument("--workers",type=int,default=4)
    ap.add_argument("--max-pages",type=int,default=30)
    args=ap.parse_args()
    if not (1<=args.workers<=8 and 1<=args.max_pages<=30):
        ap.error("invalid workers or pages")
    out=Path(args.output)
    universe,discovery=discover(args.google_base,args.max_pages)
    write(out/"discovery.json",discovery)
    write(out/"universe.json",universe)
    print("DISCOVERY_SUMMARY",json.dumps(discovery),flush=True)
    if not universe:
        raise SystemExit("No verified BIST candidates: do not report success")
    results=[]
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures={pool.submit(screen_one,row):row["symbol"] for row in universe}
        for future in concurrent.futures.as_completed(futures):
            try:result=future.result()
            except Exception as exc:
                result={"symbol":futures[future],"status":"belirsiz",
                        "reason":"unexpected_thread_failure","error":str(exc)[:200]}
            results.append(result)
            if len(results)%25==0 or len(results)==len(universe):
                write(out/"eligibility.json",sorted(results,key=lambda x:x["symbol"]))
                print("SCREEN_PROGRESS",len(results),"/",len(universe),
                      json.dumps(Counter(x["status"] for x in results)),flush=True)
    counts=Counter(x["status"] for x in results)
    missing=Counter(k for r in results for k in r.get("missing",[]))
    reasons=Counter(r.get("reason") for r in results)
    report={"created_utc":now(),"scope":"BIST","phase1":discovery,
            "phase2":{"attempted":len(results),"discovered":len(universe),
                      "statuses":dict(counts),"reasons":dict(reasons),
                      "missing_facts":dict(missing),
                      "all_discovered_screened":len(results)==len(universe),
                      "all_BIST_screened":False,
                      "certified_compliant":0,
                      "conditional_pass_is_not_approval":True},
            "phase3_scoring_started":False}
    write(out/"summary.json",report)
    print("FINAL_REPORT",json.dumps(report,ensure_ascii=False),flush=True)

if __name__=="__main__":
    run()
