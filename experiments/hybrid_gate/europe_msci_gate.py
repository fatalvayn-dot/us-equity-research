"""Europe Sharia index membership gate: official MSCI first, ETF holdings as proxy.

This experiment deliberately does NOT infer index membership from an ETF position,
a name-only top-ten listing, or absence in a partial index download.
"""
import argparse
import csv
from datetime import date, datetime, timezone
from hashlib import sha256
import io
import json
from pathlib import Path
import re
import urllib.request

MSCI_INDEX = "MSCI Europe IMI Islamic Index"
MSCI_PAGE = "https://www.msci.com/indexes/index/762539/msci-europe-imi-islamic-index"
HSBC_FUND_ISIN = "IE000AGFZM58"
HSBC_FUND_PAGE = "https://www.assetmanagement.hsbc.co.uk/en/institutional-investor/funds/ie000agfzm58"
ISHARES_WORLD_FUND_ISIN = "IE00B27YCN58"
ISHARES_WORLD_CSV = "https://www.ishares.com/uk/individual/en/products/251394/ishares-msci-world-islamic-ucits-etf/latest-holdings.csv"
EUROPE = {"Austria", "Belgium", "Denmark", "Finland", "France", "Germany", "Greece",
          "Ireland", "Italy", "Luxembourg", "Netherlands", "Norway", "Portugal",
          "Spain", "Sweden", "Switzerland", "United Kingdom", "Poland"}
YAHOO_TO_ISIN = None  # No invented cross-exchange ISIN mapping.


def fetch(url, max_bytes=4000000):
    request=urllib.request.Request(url,headers={"User-Agent":"Mozilla/5.0",
                                                "Accept":"text/csv,text/html,*/*"})
    with urllib.request.urlopen(request,timeout=35) as response:
        content=response.read(max_bytes+1)
        if len(content)>max_bytes:raise ValueError("provider file exceeds safety limit")
        return content,response.headers.get("Content-Type","")


def official_page_status(download=None):
    """No full MSCI constituent file is inferred from a public factsheet."""
    try:
        raw,_=fetch(MSCI_PAGE) if download is None else (download,"")
        txt=raw.decode("utf-8",errors="replace")
        if any(x in txt.lower() for x in ("challenge validation","checking your browser","recaptcha")):
            return {"index":MSCI_INDEX,"page_access":"challenge","full_constituents_available":False}
        count_match=re.search(r"Number of constituents\s*(?:</[^>]+>\s*)*([0-9,]+)",txt,re.I)
        count=int(count_match.group(1).replace(",","")) if count_match else None
        return {"index":MSCI_INDEX,"page_access":"ok","reported_count":count,
                "full_constituents_available":False}
    except Exception as exc:
        return {"index":MSCI_INDEX,"page_access":"error","error":str(exc)[:180],
                "full_constituents_available":False}


def load_csv(path):
    data=Path(path).read_bytes()
    text=data.decode("utf-8-sig")
    lines=text.splitlines()
    rows=list(csv.DictReader(io.StringIO(text)))
    return rows,sha256(data).hexdigest()


def index_membership(path, *, reference_date, index_name=MSCI_INDEX, expected_count=None):
    """Accept ONLY an independently sourced, complete index roster.

    Minimum schema: isin, name, asof, index_name. ISO ISIN unique. All rows
    must have same observation date, exact index name, and expected count.
    This does NOT automatically verify vendor authenticity.
    """
    if index_name!=MSCI_INDEX or expected_count is None or expected_count<1:
        raise ValueError("exact MSCI index and independently verified count required")
    rows,digest=load_csv(path)
    if len(rows)!=expected_count:raise ValueError("incomplete official membership roster")
    seen=set()
    for row in rows:
        if row.get("index_name")!=index_name:raise ValueError("mixed index methodology")
        isin=(row.get("isin") or "").upper().strip()
        if not re.fullmatch(r"[A-Z]{2}[A-Z0-9]{9}[0-9]",isin):
            raise ValueError("missing or malformed ISIN")
        if isin in seen:raise ValueError("duplicate ISIN")
        if row.get("asof")!=reference_date:raise ValueError("mixed or incorrect roster date")
        if not (row.get("name") or "").strip():raise ValueError("missing company name")
        seen.add(isin)
    return seen,{"index":index_name,"source_type":"msci_official_full_roster",
                 "source_sha256":digest,"count":len(rows),"asof":reference_date}


def etf_proxy_holdings(path, *, fund_isin, snapshot_date, provider, benchmark):
    """ETF constituents are research hints; NEVER official MSCI Europe IMI members."""
    if fund_isin not in {HSBC_FUND_ISIN,ISHARES_WORLD_FUND_ISIN}:
        raise ValueError("unsupported fund")
    if not provider or not snapshot_date or not benchmark:
        raise ValueError("source metadata required")
    rows,digest=load_csv(path)
    supported={"isin","name","country"}
    if not rows or not supported.issubset(set(rows[0])):
        raise ValueError("ETF file requires isin,name,country columns")
    output={}
    for row in rows:
        isin=(row.get("isin") or "").strip().upper()
        if not re.fullmatch(r"[A-Z]{2}[A-Z0-9]{9}[0-9]",isin):
            continue
        if row.get("country","").strip() not in EUROPE:
            continue
        output[isin]={"name":row["name"].strip(),"country":row["country"].strip(),
                      "proxy_fund_isin":fund_isin,"asof":snapshot_date}
    return output,{"source_type":"etf_portfolio_proxy_not_msci_membership",
                   "provider":provider,"fund_isin":fund_isin,
                   "benchmark":benchmark,"snapshot_date":snapshot_date,
                   "source_sha256":digest,"total_rows":len(rows),"europe_rows":len(output)}


def classify(issuer, *, official=None, proxy=None):
    """Use ISIN, never ticker-only, across countries and cross-listings."""
    isin=str(issuer.get("isin") or "").strip().upper()
    if not re.fullmatch(r"[A-Z]{2}[A-Z0-9]{9}[0-9]",isin):
        return "belirsiz_kimlik"
    if official is not None:
        if isin in official:return "resmi_msci_uyesi"
        return "resmi_listede_yok"  # not a judgement of religious suitability
    if proxy and isin in proxy:return "etf_portfoyunde_var_endeks_teyitsiz"
    return "endeks_uyeligi_dogrulanamadi"


def parse_ishares_holdings(raw):
    """Parse provider CSV, distinguishing holdings from metadata and derivatives."""
    txt=raw.decode("utf-8-sig",errors="replace")
    lines=list(csv.reader(io.StringIO(txt)))
    header_idx=None
    for i,row in enumerate(lines[:35]):
        cols=[x.strip().lstrip("\\ufeff").lower() for x in row]
        if "isin" in cols and any(x in cols for x in ("location","country")):
            header_idx=i
            break
    if header_idx is None:
        raise ValueError("iShares holdings columns not found")
    keys=[x.strip() for x in lines[header_idx]]
    data=[dict(zip(keys,row)) for row in lines[header_idx+1:] if len(row)>=len(keys)]
    isin_key=next(k for k in keys if k.lower()=="isin")
    country_key=next(k for k in keys if k.lower() in ("location","country"))
    type_key=next((k for k in keys if k.lower()=="asset class"),None)
    eu={}
    for r in data:
        isin=r.get(isin_key,"").strip().upper()
        if r.get(country_key,"").strip() not in EUROPE:
            continue
        if type_key and r.get(type_key,"").strip().lower() not in ("equity","stock"):
            continue
        if not re.fullmatch(r"[A-Z]{2}[A-Z0-9]{9}[0-9]",isin):
            continue
        eu[isin]={"name":r.get("Name") or r.get("name") or "",
                  "country":r[country_key],"isin":isin}
    return eu, len(data)


def probe_proxy():
    base="https://www.ishares.com/uk/individual/en/products/251394/ishares-msci-world-islamic-ucits-etf/"
    urls=[ISHARES_WORLD_CSV,
          base+"1478358465952.ajax?fileType=csv&fileName=ISWD_holdings&dataType=fund",
          base+"1506575576011.ajax?fileType=csv&fileName=ISWD_holdings&dataType=fund"]
    attempts=[]
    for url in urls:
        try:
            raw,ctype=fetch(url)
            preview=raw[:200].decode("utf-8-sig",errors="replace")
            eu,total=parse_ishares_holdings(raw)
            return {"status":"accessible_proxy","bytes":len(raw),
                    "source_url":url,"sha256":sha256(raw).hexdigest(),
                    "content_type":ctype,"total_rows":total,
                    "european_equity_rows":len(eu),
                    "proxy_only":True,"index_membership_verified":False}
        except Exception as exc:
            attempts.append({"url":url,"error":f"{type(exc).__name__}: {str(exc)[:120]}"})
    return {"status":"unavailable","attempts":attempts}


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--output",default="europe_gate_output")
    parser.add_argument("--official-csv")
    parser.add_argument("--official-date")
    parser.add_argument("--expected-count",type=int)
    parser.add_argument("--etf-csv")
    parser.add_argument("--etf-fund-isin",default=HSBC_FUND_ISIN)
    parser.add_argument("--etf-date")
    parser.add_argument("--etf-benchmark",default="MSCI Europe Islamic Universal Screened Select")
    args=parser.parse_args()
    out=Path(args.output);out.mkdir(parents=True,exist_ok=True)
    page=official_page_status()
    proxy_http=probe_proxy()
    official,official_meta=None,None
    proxy,proxy_meta=None,None
    if args.official_csv:
        if not (args.official_date and args.expected_count):
            parser.error("official CSV requires date and independently verified full count")
        official,official_meta=index_membership(args.official_csv,
                                      reference_date=args.official_date,expected_count=args.expected_count)
    if args.etf_csv:
        if not args.etf_date:parser.error("ETF snapshot date required")
        proxy,proxy_meta=etf_proxy_holdings(args.etf_csv,fund_isin=args.etf_fund_isin,
                                      snapshot_date=args.etf_date,provider="supplied fund holdings",
                                      benchmark=args.etf_benchmark)
    report={"timestamp_utc":datetime.now(timezone.utc).isoformat(),
            "official_index_page":page,"official_index_full_roster":official_meta,
            "etf_fallback_online_probe":proxy_http,"etf_fallback_loaded":proxy_meta,
            "verified_official_members":len(official) if official is not None else 0,
            "proxy_european_holdings":len(proxy) if proxy is not None else 0,
            "can_approve_from_official_index":official is not None,
            "etf_is_not_equivalent_to_target_index":True,
            "next_stage_scoring_authorized":official is not None}
    (out/"summary.json").write_text(json.dumps(report,ensure_ascii=False,indent=2))
    print("EUROPE_INDEX_GATE",json.dumps(report,ensure_ascii=False),flush=True)


if __name__=="__main__":
    main()
