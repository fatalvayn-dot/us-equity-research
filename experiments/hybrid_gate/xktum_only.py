"""Classify BIST candidates ONLY by Borsa Istanbul's official XKTUM constituent CSV.

No financial ratios, screening engine, KAP, secondary index lists or sector
exclusions are consulted for eligibility. Non-membership != non-compliance.
"""
import csv
from datetime import datetime, timezone
import hashlib
import io
import json
from pathlib import Path
import re
import urllib.request

from experiments.hybrid_gate.full_bist import discover_yahoo, write

OFFICIAL_CSV="https://borsaistanbul.com/datum/hisse_endeks_katilim_ds.csv"

def parse_official_csv(data):
    decoded=data.decode("utf-8-sig")
    rows=list(csv.reader(io.StringIO(decoded),delimiter=";"))
    if len(rows)<3 or rows[0][:3]!=["BILESEN KODU","BULTEN_ADI","ENDEKS KODU"]:
        raise ValueError("Official index CSV header unexpected")
    matched={}
    dates=set()
    index_counts={}
    for row in rows[2:]:
        if len(row)<6:
            continue
        index=row[2].strip().upper()
        index_counts[index]=index_counts.get(index,0)+1
        if index!="XKTUM":
            continue
        original=row[0].strip().upper()
        if not re.fullmatch(r"[A-Z0-9-]+\.E",original):
            raise ValueError("Unexpected XKTUM constituent code "+original)
        symbol=original.removesuffix(".E")+".IS"
        date=datetime.strptime(row[5].strip(),"%d/%m/%Y").date()
        dates.add(date.isoformat())
        if symbol in matched:
            raise ValueError("Duplicate XKTUM symbol "+symbol)
        matched[symbol]={"code":original,"company_name":row[1].strip(),
                         "date":date.isoformat(),"index":"XKTUM"}
    if not matched or len(dates)!=1:
        raise ValueError("No XKTUM membership or inconsistent file dates")
    return matched,{"official_url":OFFICIAL_CSV,"sha256":hashlib.sha256(data).hexdigest(),
                    "dates":sorted(dates),"xktum_constituents":len(matched),
                    "all_index_counts":index_counts}

def compare(universe, xktum):
    observed={x["symbol"] for x in universe}
    rows=[]
    for row in universe:
        sym=row["symbol"]
        status="xktum_uyesi" if sym in xktum else "xktum_uyesi_degil"
        rows.append({"symbol":sym,"name":row["company_name"],"source":row["source"],
                     "status":status,"xktum_asof":xktum[sym]["date"] if sym in xktum else None,
                     "financial_screen_run":False})
    return rows,sorted(set(xktum)-observed)

def main():
    import argparse
    ap=argparse.ArgumentParser()
    ap.add_argument("--output",default="bist_xktum_output")
    args=ap.parse_args()
    out=Path(args.output)
    with urllib.request.urlopen(urllib.request.Request(OFFICIAL_CSV,
           headers={"User-Agent":"Mozilla/5.0","Accept":"text/csv,*/*"}),timeout=40) as r:
        data=r.read()
    constituents,metadata=parse_official_csv(data)
    if metadata["dates"]!=[datetime.now(timezone.utc).date().isoformat()]:
        raise SystemExit("Official index CSV date is not today's UTC date, refusing current membership claim")
    universe,discovery=discover_yahoo(page_size=250,max_pages=30)
    entries=sorted(universe.values(),key=lambda x:x["symbol"])
    compared,xktum_not_in_yahoo=compare(entries,constituents)
    member_count=sum(x["status"]=="xktum_uyesi" for x in compared)
    report={"created_utc":datetime.now(timezone.utc).isoformat(),
            "eligibility_source":metadata,
            "bist_universe_source":"yfinance",
            "universe_discovery":discovery,
            "universe_count":len(entries),
            "matched_member_count":member_count,
            "yahoo_universe_not_xktum":len(entries)-member_count,
            "xktum_not_found_in_yahoo":len(xktum_not_in_yahoo),
            "non_membership_is_not_noncompliance":True,
            "all_BIST_listings_independently_verified":False,
            "financial_ratios_used":False,
            "stage3_scoring_started":False}
    write(out/"summary.json",report)
    write(out/"comparison.json",compared)
    write(out/"official_xktum_members.json",constituents)
    write(out/"xktum_missing_from_yahoo.json",xktum_not_in_yahoo)
    (out/"official_xktum_source.csv").write_bytes(data)
    print("XKTUM_REPORT",json.dumps(report,ensure_ascii=False),flush=True)
    print("XKTUM_MISSING_FROM_YAHOO",json.dumps(xktum_not_in_yahoo),flush=True)
    if discovery["errors"] or not discovery["pagination_exhausted"]:
        raise SystemExit("Yahoo BIST discovery incomplete")
    if len(entries)!=discovery["strict_IST_equities"]:
        raise SystemExit("Universe count inconsistent")
    if not constituents:
        raise SystemExit("XKTUM is empty")

if __name__=="__main__":
    main()
