#!/usr/bin/env python3
"""Independent source-capability benchmark. No trades or SEC requests."""
import csv, json, os, pathlib, subprocess, sys, time, urllib.request
from datetime import datetime, timezone
from urllib.parse import urlencode

ROOT=pathlib.Path("benchmark_output"); ROOT.mkdir(exist_ok=True)
SRC=os.environ["SOURCE"]
records=json.loads(pathlib.Path("docs/evidence/common100/candidates.json").read_text())["companies"]
symbols=[x["symbol"] for x in records]
assert len(symbols)==100 and len(set(symbols))==100
rows=[{"symbol":s,"identity":"unavailable","recent_price":"","price_date":"","history_rows":0,"financials":"not_tested","error":""} for s in symbols]
by={r["symbol"]:r for r in rows}
def get(url,timeout=20):
    req=urllib.request.Request(url,headers={"User-Agent":"Mozilla/5.0 (compatible; research-benchmark/1.0)"})
    with urllib.request.urlopen(req,timeout=timeout) as f: return f.read().decode("utf-8")
def save():
    with (ROOT/(SRC+".csv")).open("w",newline="") as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
    manifest={"source":SRC,"asof":datetime.now(timezone.utc).isoformat(),"requested":100,
       "identity_found":sum(x["identity"]=="found" for x in rows),
       "recent_price_found":sum(bool(x["recent_price"]) for x in rows),
       "historical_series_found":sum(x["history_rows"]>1 for x in rows),
       "financials_found":sum(x["financials"]=="found" for x in rows),
       "errors":sum(bool(x["error"]) for x in rows),
       "stage8_full_radar_acceptance":False,
       "note":"This is a source capability comparison, not completion of radar stages 1-8. Missing fields never filled from another provider."}
    (ROOT/(SRC+".json")).write_text(json.dumps(manifest,indent=2))
    print(json.dumps(manifest),flush=True)
try:
    if SRC=="tickeratlas":
        data=get("https://raw.githubusercontent.com/MeridianAlgo/TickerAtlas/main/data/All_Stocks.csv",60)
        entries=list(csv.DictReader(data.splitlines()))
        index={}
        for e in entries: index.setdefault(e.get("ticker","").upper(),e)
        for s in symbols:
            r=by[s];e=index.get(s)
            if e: r["identity"]="found"
            else:r["error"]="not in published symbol list"
            r["financials"]="unsupported"
    elif SRC=="us_screener":
        base=pathlib.Path("/tmp/us-stocks-screener")
        base.mkdir(exist_ok=True)
        with (base/"input.csv").open("w",newline="") as f:
            w=csv.writer(f);w.writerow(["Symbol"]);w.writerows([[x] for x in symbols])
        cmd=[sys.executable,"-m","us_symbols.cli","--symbols-file",str(base/"input.csv"),
          "--no-sec","--batch-size","10","--pause","1.0","--max-retries","1",
          "--output-dir",str(base/"results")]
        p=subprocess.run(cmd,cwd="/tmp/us-stocks-screener",capture_output=True,text=True,timeout=1400)
        (ROOT/"us_screener_run.log").write_text(p.stdout[-15000:]+"\\n"+p.stderr[-15000:])
        out=base/"results"/"us_symbols_merged.csv"
        if not out.exists():out=base/"results"/"us_symbols.csv"
        if out.exists():
            for e in csv.DictReader(out.open()):
                s=e.get("Symbol") or e.get("symbol")
                if s in by: by[s]["identity"]="found";by[s]["financials"]="unsupported"
        if p.returncode: 
            for r in rows:r["error"]="CLI exit "+str(p.returncode)
    elif SRC=="yfinance":
        import yfinance as yf
        for n,s in enumerate(symbols):
            r=by[s]
            try:
                hist=yf.Ticker(s).history(period="1y",auto_adjust=False,timeout=12)
                if len(hist)>0:
                    r["identity"]="found";r["history_rows"]=len(hist)
                    r["recent_price"]=str(float(hist["Close"].iloc[-1]))
                    r["price_date"]=str(hist.index[-1].date())
                else:r["error"]="no price rows"
            except Exception as exc:r["error"]=str(exc)[:200]
            if n%10==9:print("checked",n+1,flush=True);save()
    elif SRC=="openbb":
        try:
            from openbb import obb
            for n,s in enumerate(symbols):
                r=by[s]
                try:
                    result=obb.equity.price.historical(symbol=s,provider="yfinance",start="2025-11-19")
                    d=result.to_df()
                    if len(d):
                        r["identity"]="found";r["history_rows"]=len(d)
                        r["recent_price"]=str(float(d["close"].iloc[-1]))
                        r["price_date"]=str(d.index[-1])
                    else:r["error"]="empty historical"
                except Exception as exc:r["error"]=str(exc)[:200]
                if n%10==9:print("checked",n+1,flush=True);save()
        except Exception as exc:
            for r in rows:r["error"]="OpenBB unavailable: "+str(exc)[:150]
    elif SRC=="google_scraper":
        base="http://127.0.0.1:8000"
        for n,s in enumerate(symbols):
            r=by[s];errs=[]
            for exch in ("NASDAQ","NYSE","NYSEAMERICAN"):
                try:
                    q=json.loads(get(base+"/quote?"+urlencode({"symbol":s+":"+exch}),40))
                    if q.get("error"):errs.append(str(q["error"])[:60]);continue
                    price=q.get("price") or q.get("quote",{}).get("price")
                    if price is not None:
                        r["identity"]="found";r["recent_price"]=str(price)
                        r["price_date"]=datetime.now(timezone.utc).date().isoformat()
                        try:
                            h=json.loads(get(base+"/chart?"+urlencode({"symbol":s+":"+exch,"range":"1Y"}),30))
                            r["history_rows"]=len(h.get("data",[]) if isinstance(h,dict) else [])
                        except Exception as exc:errs.append("chart "+str(exc)[:80])
                        break
                except Exception as exc:errs.append(str(exc)[:70])
            if r["identity"]!="found":r["error"]="; ".join(errs)[:200]
            if n%10==9: print("checked",n+1,flush=True);save()
    else:raise ValueError("Unknown SOURCE")
finally:
    save()
