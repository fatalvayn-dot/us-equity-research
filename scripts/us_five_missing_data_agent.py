"""Read-only task queue for an SEC evidence gap research worker.

No new data retrieval, scoring, aliasing, trade approval or paid model usage.
"""
import argparse
import json
from pathlib import Path
from equity_research.mvp import save_json
from scripts.unified_us_five import COHORT

EXPECTED = dict(COHORT)
ALTERNATIVES = {
    "revenue": ["us-gaap:Revenues", "us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax"],
    "liabilities": ["us-gaap:Liabilities", "us-gaap:LiabilitiesAndStockholdersEquity", "us-gaap:StockholdersEquity"],
    "capital_expenditure": ["us-gaap:PaymentsToAcquirePropertyPlantAndEquipment", "us-gaap:PaymentsToAcquireProductiveAssets"],
    "dated_exact_share_class": ["dei:EntityCommonStockSharesOutstanding", "original 10-K A/B/C cover classes"],
}
ACTIONS = {
    "revenue": "Karşılaştırmalı FY dönemi ve hesap tanımını özgün SEC iXBRL'de denetle; Revenues otomatik eşdeğer değildir.",
    "liabilities": "Özgün bilanço yükümlülük toplamını veya kapsamı doğrulanmış bilanço denkliğini incele; toplam borca eşitleme.",
    "capital_expenditure": "PP&E ve productive-assets kapsamları ile nakit akım dönemi farklarını orijinal 10-K üzerinde uzlaştır.",
    "dated_exact_share_class": "A/B/C oy ve ekonomik haklar ile tarihli A/C fiyatlarını ayrı doğrula; B için piyasa fiyatı varsayma.",
}

def build_queue(gaps, original):
    if not isinstance(gaps, dict) or not isinstance(original, dict) or gaps.get("investment_approved") is not False or original.get("investment_approved") is not False:
        raise ValueError("unsafe source inputs")
    if gaps.get("cohort") != "US_FIVE_V1":
        raise ValueError("cohort mismatch")
    def index(rows, label, allowed):
        if not isinstance(rows, list):
            raise ValueError(label + " missing")
        found = {}
        for r in rows:
            if not isinstance(r, dict) or r.get("symbol") not in allowed or r.get("issuer_id") != EXPECTED[r["symbol"]] or r["symbol"] in found:
                raise ValueError(label + " issuer mismatch")
            found[r["symbol"]] = r
        if set(found) != set(allowed):
            raise ValueError(label + " issuer mismatch")
        return found
    by_gap = index(gaps.get("companies"), "gap", EXPECTED)
    by_original = index(original.get("issuer_reviews"), "original", {"NVDA","AMZN","GOOGL"})
    tasks = []
    for symbol, cik in COHORT:
        row=by_gap[symbol]
        findings=row.get("missing_required_facts")
        issues=row.get("gaps")
        if not isinstance(findings, list) or not isinstance(issues, list) or any(not isinstance(x,str) for x in issues):
            raise ValueError("invalid missing facts")
        fields={f.get("field"):f for f in findings if isinstance(f,dict)}
        if len(fields)!=len(findings) or set(fields) != (set(issues) & set(fields)) or (set(issues)&set(ACTIONS)-{"dated_exact_share_class"})!=set(fields):
            raise ValueError("field evidence mismatch")
        if not issues:
            continue
        src=by_original.get(symbol)
        if src is None:
            raise ValueError("original issuer mismatch")
        if src.get("source_hash_reverified") is not True or src.get("automatic_substitution") is not False or src.get("score_eligible") is not False:
            raise ValueError("unverified original source")
        sha=src.get("original_source_sha256")
        url=src.get("original_source_url")
        if not isinstance(sha,str) or len(sha)!=64 or not isinstance(url,str) or not url.startswith("https://www.sec.gov/Archives/"):
            raise ValueError("unverified original source")
        for field in issues:
            rec=fields.get(field,{})
            tasks.append({
                "symbol":symbol,"issuer_id":cik,"field":field,
                "required_concept":rec.get("required_concept") if rec else "Date-specific three-class share valuation model",
                "provider_attempts":rec.get("source_attempts",[]) if rec else [],
                "original_source_url":url,"original_source_sha256":sha,
                "observed_original_concepts":[x.get("concept") for x in src.get("disclosed_concepts",[]) if x.get("status")=="exact_original_value"],
                "concepts_to_investigate":ALTERNATIVES.get(field,[]),
                "likely_root_cause":"multi_class_valuation_model_missing" if field=="dated_exact_share_class" else "different_gaap_scope_or_missing_literal",
                "verification_state":"requires_accounting_review",
                "next_action":ACTIONS.get(field,"Özgün SEC raporu ve mevcut sağlayıcı denemelerini kontrol et."),
                "approved_substitute":None,
            })
    return {"schema_version":1,"cohort":"US_FIVE_V1",
            "agent_role":"eksik_veri_arastirma","tasks":tasks,
            "network_requests":0,"scores_generated":0,"automatic_substitution":False,
            "investment_approved":False,"expansion_to_25_approved":False}

def markdown(report):
    rows=["# Eksik Veri Araştırma Ajanı — kontrol kuyruğu","",
          "Salt okunur özgün SEC kanıtı. Hiçbir eksik alan otomatik doldurulmadı.","",
          "| Şirket | Alan | Neden | Sonraki kontrol |","|---|---|---|---|"]
    for t in report["tasks"]:
        rows.append("| "+t["symbol"]+" | "+t["field"]+" | "+t["likely_root_cause"]+" | "+t["next_action"]+" |")
    rows.extend(["","Kayıt sayısı: "+str(len(report["tasks"])),"Katılım uygunluğu veya alım izni: YOK."])
    return "\n".join(rows)+"\n"

def main():
    p=argparse.ArgumentParser()
    for name in ("gaps","original","out","markdown"):
        p.add_argument("--"+name,required=True)
    a=p.parse_args()
    load=lambda p: json.loads(Path(p).read_text(encoding="utf-8"))
    report=build_queue(load(a.gaps),load(a.original))
    save_json(a.out,report)
    Path(a.markdown).write_text(markdown(report),encoding="utf-8")
    print(json.dumps({"tasks":len(report["tasks"]),"investment_approved":False}))

if __name__=="__main__":
    main()
