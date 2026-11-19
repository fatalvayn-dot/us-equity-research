"""Discover a fresh 100-company US cohort from the official SEC listing.

Each issuer identity and conservative SEC SIC exclusion is checked before
selection. This is *not* an investment-eligibility or common-share certificate.
Never reuse any of the original 100 issuers. No public GitHub raw SEC caches.
This script does not change a repository file or place orders.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import time
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

from equity_research.sec import DIRECTORY_URL
from equity_research.sector_policy import excluded_banking_or_insurance
from equity_research.mvp import validate_candidates

SECTORS = {
    "healthcare": """
ZTS SYK BSX EW HCA MCK CAH COR REGN BMY BIIB IDXX IQV HOLX EXAS NTRA INCY RGEN CRL ALNY BMRN UTHR SRPT EXEL AXSM NBIX RARE SMMT TGTX HIMS ELAN HSIC WST COO PODD DVA THC UHS OGN MRNA ILMN TECH HALO BEAM NTLA FATE RXRX KROS CYTK PCVX RYTM ADMA INSM""",
    "industrials": """
HON MMM EMR PH ITW OTIS CARR GNRC HUBB LECO DOV FTV WAB PTC GEHC XYL IEX AOS GWW FAST URI GPC WSO ROL CTAS IR NOC GD HII TXT TDG HEI CW RBC AL GATX NDSN FLS SNA SWK AME MAS LII J KBR TTEK SAIC LDOS HWM CMI PCAR OSK AGCO TKR CSL KEX EXP ZBRA WAT""",
    "consumer": """
LOW TGT DG DLTR ROST ORLY AZO TSCO ULTA SBUX CMG YUM DPZ DRI CAVA TXRH BROS SHAK WING CHWY ETSY EBAY EXPE BKNG ABNB MAR HLT RCL CCL NCLH DIS WBD LYV CHTR CMCSA VZ T KMX AAP BURL DECK FIVE GME BBY GAP ANF AEO LULU NKE CROX SKX""",
    "technology": """
IBM HPE HPQ KEYS TER QRVO ALGM ACLS LSCC INDI COHR VIAV CIEN GLW SMCI DOCU ZM ZS OKTA NET DDOG MDB SNOW DT PATH APP VEEV HUBS U RBLX PINS SNAP RDDT DUOL CFLT GTLB AI IOT ALAB INTA FIVN PAYC PAYX MANH CDW GEN S BOX ASAN BILL FLNC PLAB AMKR CTSH DXC CRDO""",
    "energy": """
XOM OXY EOG SLB HAL BKR DVN FANG MPC VLO PSX OKE KMI WMB LNG EQT CTRA APA NOV OII RES PBF CHRD MTDR SM RRC AR CNX GPOR CRC EXE VST NRG CEG FSLR ENPH SEDG""",
    "materials": """
SHW ECL APD FCX NEM NUE STLD RS ALB MOS CF CE FMC PPG RPM MLM VMC AA HXL CLF KALU WLK OLN AXTA SEE IFF EMN AVY""",
    "utilities": """
AEP D SO SRE EXC DUK EIX ES XEL ED WEC CMS CNP FE PCG PEG PPL AES ATO NI LNT EVRG AWK WTRG OGS""",
}
ALLOWED_EXCHANGES = {"Nasdaq", "NYSE", "NYSE American"}
EXCLUDED_WORDS = re.compile(
    r"(BANK|BANCORP|INSURANCE|REINSURANCE|BROKER|CASINO|LOTTER|"
    r"TOBACCO|CIGARETTE|VAPING|BREWER|BREWING|WINERY|ALCOHOL|"
    r"REAL ESTATE INVESTMENT TRUST|\bREIT\b|\bFUND\b|"
    r"MORTGAGE TRUST|INVESTMENT MANAGEMENT)",
    re.I,
)
SECTOR_WORDS = re.compile(
    r"(BANK|INSUR|CASINO|GAMBL|ALCOHOL|BREWER|TOBACCO|"
    r"INVESTMENT FUNDS|FINANCIAL SERVICES|REAL ESTATE INVESTMENT)",
    re.I,
)


def priority_symbols():
    groups = [raw.split() for raw in SECTORS.values()]
    symbols = []
    for i in range(max(map(len, groups))):
        for group in groups:
            if i < len(group) and group[i] not in symbols:
                symbols.append(group[i])
    return symbols


def excluded_sic(sic):
    if not isinstance(sic, str) or not re.fullmatch("[0-9]{4}", sic):
        return True
    i = int(sic)
    return (not 100 <= i <= 8999 or excluded_banking_or_insurance(sic)
            or 6000 <= i <= 6999
            or 2100 <= i <= 2199
            or i in {2082, 2083, 2084, 2085, 2086, 2087}
            or i in {7993, 7999})


def decode_directory(data):
    p = json.loads(data)
    fields = p.get("fields")
    if not isinstance(fields, list) or not {"cik", "ticker", "exchange", "name"} <= set(fields):
        raise ValueError("unexpected SEC listed company directory schema")
    result = {}
    for values in p.get("data", []):
        if not isinstance(values, list) or len(values) != len(fields):
            raise ValueError("invalid SEC company listing row")
        row = dict(zip(fields, values))
        symbol = row["ticker"]
        if not isinstance(symbol, str) or not re.fullmatch(r"[A-Z]{1,5}", symbol):
            continue
        result.setdefault(symbol, []).append(row)
    return result


def safe_candidate(ticker, row, submissions, previous):
    if ticker in previous["symbols"]:
        return None, "already_in_old_cohort"
    cik = row.get("cik")
    if type(cik) is not int or cik <= 0:
        return None, "invalid_cik"
    cik = str(cik).zfill(10)
    if cik in previous["ciks"]:
        return None, "same_issuer_in_old_cohort"
    if row.get("exchange") not in ALLOWED_EXCHANGES:
        return None, "non_us_exchange"
    if EXCLUDED_WORDS.search(row.get("name", "")):
        return None, "excluded_company_name"
    meta = submissions
    if not isinstance(meta, dict) or str(meta.get("cik")).zfill(10) != cik:
        return None, "SEC_submissions_issuer_mismatch"
    if ticker not in meta.get("tickers", []):
        return None, "ticker_not_confirmed_by_submissions"
    # Multiple public common share classes may need a separate cover audit.
    if meta.get("tickers") != [ticker]:
        return None, "multiple_or_ambiguous_share_classes"
    if meta.get("entityType") != "operating":
        return None, "nonoperating_or_unreviewed_entity"
    sic = str(meta.get("sic", ""))
    if excluded_sic(sic) or SECTOR_WORDS.search(meta.get("sicDescription", "")):
        return None, "excluded_or_unknown_SEC_SIC"
    if EXCLUDED_WORDS.search(meta.get("name", "")):
        return None, "excluded_SEC_registered_name"
    recent = meta.get("filings", {}).get("recent", {})
    forms = recent.get("form", [])
    if not any(x in {"10-K", "10-Q"} for x in forms):
        return None, "no_recent_us_financial_reports"
    return {"symbol": ticker, "issuer_id": cik}, None


def fetch(url, agent):
    if not agent or not isinstance(agent, str):
        raise ValueError("SEC_USER_AGENT required")
    if url != DIRECTORY_URL and not re.fullmatch(
        r"https://data\.sec\.gov/submissions/CIK[0-9]{10}\.json", url
    ):
        raise ValueError("only exact SEC company directory or submissions URLs allowed")
    request = Request(url, headers={
        "User-Agent": agent, "Accept": "application/json",
        "Accept-Encoding": "identity",
    })
    try:
        with urlopen(request, timeout=35) as response:
            if response.status != 200 or response.geturl() != url:
                raise ValueError("source redirect or bad HTTP code")
            body = response.read(16_000_001)
            if not body or len(body) > 16_000_000:
                raise ValueError("empty or excessive SEC JSON")
            return body
    except (HTTPError, URLError) as exc:
        raise ValueError("official SEC source unavailable") from exc


def choose(directory, old, *, loader, max_submissions=240):
    old_rows = validate_candidates(old)
    previous = {"symbols": {r["symbol"] for r in old_rows},
                "ciks": {r["issuer_id"] for r in old_rows}}
    catalog = decode_directory(directory)
    chosen, provenance, rejections, ciks = [], [], [], set()
    requests = 0
    for symbol in priority_symbols():
        if len(chosen) == 100:
            break
        if symbol in previous["symbols"]:
            continue
        hits = catalog.get(symbol, [])
        if len(hits) != 1 or hits[0].get("exchange") not in ALLOWED_EXCHANGES:
            rejections.append({"symbol": symbol, "reason": "not_unique_us_sec_listing"})
            continue
        row = hits[0]
        if not isinstance(row.get("name"), str) or EXCLUDED_WORDS.search(row["name"]):
            rejections.append({"symbol": symbol, "reason": "excluded_issuer_name"})
            continue
        if requests >= max_submissions:
            raise ValueError("SEC validation budget ended before 100 accepted companies")
        cik = str(row["cik"]).zfill(10)
        requests += 1
        data = loader(f"https://data.sec.gov/submissions/CIK{cik}.json")
        meta = json.loads(data)
        company, reject = safe_candidate(symbol, row, meta, previous)
        if reject or company["issuer_id"] in ciks:
            rejections.append({"symbol": symbol, "reason": reject or "duplicate_issuer"})
            continue
        ciks.add(company["issuer_id"])
        chosen.append(company)
        provenance.append({
            "symbol": symbol, "issuer_id": cik,
            "metadata_source": f"https://data.sec.gov/submissions/CIK{cik}.json",
            "metadata_raw_sha256": hashlib.sha256(data).hexdigest(),
            "sic": str(meta["sic"]),
            "ticker_identity_matched": True,
            "entity_type": meta.get("entityType"),
            "security_type_approved": False, "shariah_approved": False,
            "financial_model_supported": False,
        })
    if len(chosen) != 100 or len({x["issuer_id"] for x in chosen}) != 100:
        raise ValueError(f"100 distinct SEC-reviewed candidates unavailable: {len(chosen)}")
    if len(previous["symbols"] & {x["symbol"] for x in chosen}) or len(
        previous["ciks"] & {x["issuer_id"] for x in chosen}
    ):
        raise ValueError("old cohort overlap")
    validate_candidates({"companies": chosen})
    return {"companies": chosen}, {
        "schema_version": 1, "source": DIRECTORY_URL,
        "source_sha256": hashlib.sha256(directory).hexdigest(),
        "source_observed_at": datetime.now(timezone.utc).isoformat(),
        "old_issuers_excluded": len(old_rows),
        "new_issuers": len(chosen), "submissions_attempts": requests,
        "selected": provenance, "rejected": rejections,
        "claims": {
            "us_sec_directory_confirmed": True,
            "SEC_SIC_business_exclusion_reviewed": True,
            "common_share_and_index_membership_confirmed": False,
            "financial_data_and_participation_confirmed": False,
            "investment_approved": False,
        },
    }


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--prior", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--manifest", type=Path, required=True)
    a = p.parse_args()
    prior = json.loads(a.prior.read_text())
    agent = os.getenv("SEC_USER_AGENT", "")
    directory = fetch(DIRECTORY_URL, agent)
    last = [0.0]
    def loader(url):
        delay = max(0.0, 0.28 - (time.monotonic() - last[0]))
        if delay:
            time.sleep(delay)
        body = fetch(url, agent)
        last[0] = time.monotonic()
        return body
    cohort, evidence = choose(directory, prior, loader=loader)
    a.output.parent.mkdir(parents=True, exist_ok=True)
    a.manifest.parent.mkdir(parents=True, exist_ok=True)
    a.output.write_text(json.dumps(cohort, indent=2, ensure_ascii=False) + "\n")
    a.manifest.write_text(json.dumps(evidence, ensure_ascii=False, indent=2) + "\n")
    # Actions logs carry only the public list. No raw responses or secrets.
    print("FRESH100_JSON=" + json.dumps(cohort, separators=(",", ":")))
    print(json.dumps({"chosen": len(cohort["companies"]),
                      "submissions_attempts": evidence["submissions_attempts"],
                      "rejected": len(evidence["rejected"]),
                      "old_issuers_excluded": evidence["old_issuers_excluded"],
                      "directory_sha256": evidence["source_sha256"]}))


if __name__ == "__main__":
    main()
