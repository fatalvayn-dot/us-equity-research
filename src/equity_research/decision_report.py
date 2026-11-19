"""Read-only Turkish decision-support presentation for already computed scores.

This is deliberately NOT a trading strategy, buy/sell engine or recalculation
of a score. Participation screenings from the research prototype never
constitute approved investment eligibility.
"""
from datetime import datetime
from decimal import Decimal, InvalidOperation
from html import escape
import re

from .turkish import label

ACTION_VOCABULARY = ("AL", "TUT", "AZALT", "SAT", "BEKLE")
COMPONENT_NAMES = (
    "financial_strength", "growth", "profitability", "cash_flow",
    "valuation", "risk",
)
SCORE_ID = re.compile(r"[0-9]{10}\Z")


def _cutoff(value):
    if not isinstance(value, str):
        raise ValueError("timezone-aware source cutoff required")
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        raise ValueError("invalid source cutoff") from None
    if dt.tzinfo is None or dt.utcoffset() is None:
        raise ValueError("timezone-aware source cutoff required")
    return dt


def _score(value):
    if type(value) not in (str, int, Decimal):
        raise ValueError("exact source score required")
    try:
        num = Decimal(value)
    except InvalidOperation:
        raise ValueError("invalid source score") from None
    if not num.is_finite() or not 0 <= num <= 100:
        raise ValueError("source score outside 0..100")
    return str(num)


def _participation_index(rows, cutoff):
    if rows is None:
        return {}
    if not isinstance(rows, list):
        raise ValueError("participation evidence must be a list")
    by_issuer = {}
    for p in rows:
        if not isinstance(p, dict):
            raise ValueError("participation evidence row required")
        key = p.get("issuer_key")
        if not isinstance(key, str) or not re.fullmatch(r"SEC:[0-9]{10}", key):
            raise ValueError("US participation must use exact SEC issuer key")
        if key in by_issuer:
            raise ValueError("conflicting or duplicate participation record")
        if _cutoff(p.get("as_of")) > cutoff:
            raise ValueError("future participation assessment")
        if p.get("status") not in ("uygunsuz", "bilinmiyor", "kosullu_esik_gecisi"):
            raise ValueError("unknown participation research status")
        # Stage-6 model is noncertifying. Do not accept approval injected by callers.
        if any(p.get(field) is not False for field in (
            "qualified_for_investment", "shariah_certified",
            "investment_approved", "eligible_for_automatic_order"
        )):
            raise ValueError("unverified participation approval cannot be presented")
        by_issuer[key] = p
    return by_issuer


def _sources(company):
    sources = []
    for origin in (company.get("sector_evidence"), company.get("market_risk")):
        if isinstance(origin, dict) and origin.get("source_url") and origin.get("raw_sha256"):
            sources.append({"url": origin["source_url"], "sha256": origin["raw_sha256"]})
    for proof in company.get("evidence", {}).get("financial_confirmations", []):
        raw = proof.get("selected") if isinstance(proof, dict) else None
        if isinstance(raw, dict) and raw.get("source_url") and raw.get("raw_sha256"):
            sources.append({"url": raw["source_url"], "sha256": raw["raw_sha256"]})
    return sources


def build_decision_report(score_report, participation_reports=None):
    """Re-present existing evidence, preserving missing values as NULL."""
    if not isinstance(score_report, dict) or not isinstance(score_report.get("companies"), list):
        raise ValueError("complete score report required")
    if score_report.get("schema_version") != 1:
        raise ValueError("unsupported score report version")
    cutoff = _cutoff(score_report.get("as_of"))
    participation = _participation_index(participation_reports, cutoff)
    records = []
    unique = set()
    for c in score_report["companies"]:
        if not isinstance(c, dict):
            raise ValueError("score company object required")
        cik, symbol = c.get("issuer_id"), c.get("symbol")
        if (not isinstance(cik, str) or not SCORE_ID.fullmatch(cik) or
                not isinstance(symbol, str) or not symbol.strip() or
                (cik, symbol) in unique):
            raise ValueError("exact unique company identity required")
        unique.add((cik, symbol))
        status = c.get("status")
        total = c.get("total_score")
        if (total is None and status == "scored_research_hypothesis") or (
            total is not None and status != "scored_research_hypothesis"
        ):
            raise ValueError("score/status conflict")
        components = c.get("components")
        if not isinstance(components, dict) or set(COMPONENT_NAMES) != set(components):
            raise ValueError("complete original component contract required")
        vals = {}
        for k in COMPONENT_NAMES:
            row = components[k]
            if not isinstance(row, dict) or "score" not in row or "weight" not in row:
                raise ValueError("score component source missing")
            points = None if row["score"] is None else _score(row["score"])
            weight = _score(row["weight"])
            if (total is None) != (points is None):
                raise ValueError("unscored company has fabricated component")
            if points is not None and Decimal(points) > Decimal(weight):
                raise ValueError("component exceeds source weight")
            vals[k] = {"puan": points, "agirlik": weight}
        if total is not None:
            score = _score(total)
            if sum((Decimal(vals[k]["puan"]) for k in COMPONENT_NAMES), Decimal(0)) != Decimal(score):
                raise ValueError("source score/component discrepancy")
        else:
            score = None

        p = participation.get("SEC:" + cik)
        if p is not None and p.get("symbol") != symbol:
            raise ValueError("participation issuer/ticker mismatch")
        participation_status = p["status"] if p else "bilinmiyor"
        if status == "excluded_sector":
            participation_status = "uygunsuz"
        blockers = c.get("blockers")
        if not isinstance(blockers, list) or any(not isinstance(x, str) for x in blockers):
            raise ValueError("missing blocker evidence")
        if participation_status == "uygunsuz":
            reasons = ["Katılım/kalıcı sektör dışlama: araştırma kapsamında uygun değil"]
        else:
            reasons = ["Katılım onayı tamamlanmadı"]
        if status != "scored_research_hypothesis":
            reasons.append("Finansal araştırma puanı hesaplanamadı")
        if blockers:
            reasons += [label(x) for x in blockers]
        if c.get("failed_validation_stage"):
            reasons.append("Doğrulama aşaması: " + str(c["failed_validation_stage"]))

        records.append({
            "symbol": symbol,
            "issuer_id": cik,
            "kaynak_durumu": status,
            "arastirma_sirasi": c.get("rank") if score is not None else None,
            "arastirma_puani": score,
            "finansal": {k: vals[k] for k in (
                "financial_strength", "growth", "profitability", "cash_flow")},
            "degerleme": vals["valuation"],
            "risk": vals["risk"],
            "katilim_durumu": participation_status,
            "katilim_standart": p.get("rulebook_id") if p else None,
            "katilim_surumu": p.get("rulebook_version") if p else None,
            "katilim_kosullu_sonuc_sertifika_degil": participation_status == "kosullu_esik_gecisi",
            "engeller": reasons,
            "kaynaklar": _sources(c),
            "uzman_karari": None,  # not BEKLE/TUT without a verified decision or holding
            "karar_sozlugu": list(ACTION_VOCABULARY),
            "otomatik_emir": False,
            "yatirim_onayi": False,
            "kur_eur_performans": None,
            "karsilastirma_endeksi_eur": None,
            "komisyon": None,
            "veri_inceleme_durumu": "uzman_incelemesi_bekleniyor",
        })
    if not records:
        raise ValueError("nonempty research universe required")
    summary = score_report.get("summary")
    if not isinstance(summary, dict) or (
        summary.get("candidates") != len(records) or
        summary.get("scored_companies") != sum(x["arastirma_puani"] is not None for x in records)
    ):
        raise ValueError("score count/provenance contradiction")
    ids = {c["issuer_id"] for c in records}
    if any(key.removeprefix("SEC:") not in ids for key in participation):
        raise ValueError("participation evidence for a foreign issuer")
    records.sort(key=lambda x: (x["arastirma_puani"] is None,
                                -Decimal(x["arastirma_puani"] or "0"), x["symbol"], x["issuer_id"]))
    return {
        "schema_version": 1,
        "sunum_turu": "turkce_kanit_ayrimli_arastirma",
        "orijinal_kaynak_kesimi": score_report["as_of"],
        "orijinal_model": score_report.get("model_version"),
        "kaynak_ozet": score_report.get("input_provenance"),
        "aday_sayisi": len(records),
        "puanli_sirket": sum(x["arastirma_puani"] is not None for x in records),
        "yatirim_onayli_sirket": 0,
        "bilinmeyen_katilim": sum(x["katilim_durumu"] == "bilinmiyor" for x in records),
        "eur_ve_komisyon": "Veri sunulmadı; sıfır varsayılmaz",
        "mvp_kabul": False,
        "yatirim_onayi": False,
        "uyari": "Sayısal puanlar araştırma hipotezidir, katılım/AL-TUT-SAT onayı değildir.",
        "sirketler": records,
    }


def render_decision_markdown(report):
    """A view, not a recommendation. No arbitrary score threshold maps to AL."""
    if report.get("sunum_turu") != "turkce_kanit_ayrimli_arastirma":
        raise ValueError("wrong decision report")
    def cell(v):
        return escape("Bilinmiyor" if v is None else str(v)).replace("|", "&#124;").replace("\n", " ")
    lines = [
        "# Adaptif Yatırım Uzmanı — Türkçe karar destek araştırması", "",
        f"Özgün puanlama kesimi: {cell(report['orijinal_kaynak_kesimi'])}; model: {cell(report['orijinal_model'])}.",
        f"{report['aday_sayisi']} aday; {report['puanli_sirket']} araştırma puanı; yatırım onaylı: 0.", "",
        "**Bu rapor alım/satım önerisi veya katılım uygunluk belgesi değildir.**",
        "AL / TUT / AZALT / SAT / BEKLE kararları uzman onayı olmadan otomatik verilmez.",
        "Özellikle TUT/SAT kararları mevcut pozisyon bilgisi olmadan oluşturulamaz.",
        "EUR bazlı gerçekleşmiş getiri, kur, karşılaştırma endeksi ve işlem komisyonu verilmediyse hesaplanmadı; sıfır kabul edilmedi.", "",
        "| Sembol | Puan | Finansal (güç/büyüme/kârlılık/nakit) | Değerleme | Risk | Katılım | Uzman kararı |",
        "| --- | ---: | --- | --- | --- | --- | --- |",
    ]
    for c in report["sirketler"]:
        financial = " / ".join(
            "—" if c["finansal"][k]["puan"] is None else c["finansal"][k]["puan"] +
            "/" + c["finansal"][k]["agirlik"]
            for k in ("financial_strength", "growth", "profitability", "cash_flow"))
        valuation = c["degerleme"]["puan"]
        risk = c["risk"]["puan"]
        data = (c["symbol"],
                "—" if c["arastirma_puani"] is None else c["arastirma_puani"]+"/100",
                financial, "—" if valuation is None else valuation+"/"+c["degerleme"]["agirlik"],
                "—" if risk is None else risk+"/"+c["risk"]["agirlik"],
                c["katilim_durumu"], "Verilmedi")
        lines.append("| " + " | ".join(cell(x) for x in data) + " |")
    lines += ["", "## Kaynak ve inceleme engelleri", ""]
    for c in report["sirketler"]:
        lines.append("### " + cell(c["symbol"]))
        lines.append("İnceleme: " + cell("; ".join(c["engeller"])) + ".")
        lines.append("Katılım standardı / sürümü: " +
                     cell(c["katilim_standart"]) + " / " + cell(c["katilim_surumu"]) + ".")
        for source in c["kaynaklar"]:
            url = source["url"]
            if isinstance(url, str) and url.startswith("https://"):
                lines.append("Özgün kaynak: " + cell(url) + " · SHA-256: " +
                             cell(source["sha256"]) + ".")
        lines.append("")
    return "\n".join(lines) + "\n"
