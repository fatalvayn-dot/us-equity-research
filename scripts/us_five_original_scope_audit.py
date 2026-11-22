"""Inspect archived ORIGINAL FY2025/26 SEC 10-K iXBRL evidence for three blocked issuers.

No external requests, no GAAP aliases, no automated score or trade approval.
The archived filing SHA is verified against the existing evidence manifest.
"""
import argparse
import gzip
import hashlib
import json
import re
from html.parser import HTMLParser
from datetime import date
from pathlib import Path

from equity_research.concept_diagnostics import inspect_concepts
from equity_research.filingcheck import filing_derived_liabilities
from equity_research.mvp import save_json
from equity_research.providers import ProviderFailure

TARGETS = {
    "NVDA": ("0001045810", ("revenue", "capital_expenditure")),
    "AMZN": ("0001018724", ("liabilities", "capital_expenditure")),
    "GOOGL": ("0001652044", ("revenue", "dated_exact_share_class")),
}
CANDIDATES = {
    "NVDA": ("us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax",
             "us-gaap:Revenues",
             "us-gaap:PaymentsToAcquirePropertyPlantAndEquipment",
             "us-gaap:PaymentsToAcquireProductiveAssets"),
    "AMZN": ("us-gaap:Liabilities",
             "us-gaap:LiabilitiesAndStockholdersEquity",
             "us-gaap:StockholdersEquity",
             "us-gaap:PaymentsToAcquirePropertyPlantAndEquipment",
             "us-gaap:PaymentsToAcquireProductiveAssets"),
    "GOOGL": ("us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax",
              "us-gaap:Revenues"),
}
# Exact alternate concepts are DISCLOSURES, never automatically approved
# substitutes for the canonical nine inputs of research-batch-v2.
LIMITATIONS = {
    "NVDA": "Revenue and productive-asset-payment concepts have different "
            "accounting definitions from the mandatory contract revenue and PP&E cash capex.",
    "AMZN": "A reconciled liabilities-equation proof is not a literal SEC Liabilities "
            "fact. Productive-asset cash flow is not automatically PP&E purchases.",
    "GOOGL": "Class A/B/C share counts and economic rights require a multi-class "
             "valuation model. A single class' price times aggregate shares is prohibited.",
}



class _VisibleText(HTMLParser):
    """Collect visible filing text without guessing at XBRL class dimensions."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []

    def handle_data(self, data):
        self.parts.append(data)


def googl_cover_classes(original_html):
    """Read explicitly dated A/B/C counts; this is NOT class-market valuation."""
    parser = _VisibleText()
    parser.feed(original_html.decode("utf-8"))
    text = re.sub(r"\s+", " ", " ".join(parser.parts))
    markers = list(re.finditer(
        r"As of\s+January\s+28,\s*2026\s*,\s*there\s+wer\s*e", text, flags=re.I
    ))
    if len(markers) != 1:
        raise ValueError("Alphabet original cover date absent or ambiguous")
    excerpt = text[markers[0].end():markers[0].end() + 850]
    matches = list(re.finditer(
        r"([0-9][0-9,]*)\s+million\s+shares\s+of\s+"
        r"(?:(?:the\s+)?Alphabet[’']s\s+)?"
        r"Class\s+([ABC])\s+(?:common\s+|capital\s+)?stock\s+outstanding",
        excerpt, re.I
    ))
    if [m.group(2).upper() for m in matches] != ["A", "B", "C"]:
        raise ValueError("Alphabet three-class share cover not proven")
    counts = {m.group(2).upper(): int(m.group(1).replace(",", "")) for m in matches}
    if any(count <= 0 or count > 100000 for count in counts.values()):
        raise ValueError("Alphabet class count out of bounds")
    return dict(cover_as_of="2026-01-28", reported_units="million_shares",
                reported_class_counts_million=counts,
                valuation_approved=False, shares_approved=False)


def original_review(*, root):
    root = Path(root)
    manifest = json.loads((root / "docs/evidence/annual-document-resume.json").read_text(encoding="utf-8"))
    companies = manifest.get("companies")
    if not isinstance(companies, list):
        raise ValueError("original annual filing manifest invalid")
    by = {}
    for c in companies:
        symbol = c.get("symbol") if isinstance(c, dict) else None
        if symbol in TARGETS:
            if symbol in by:
                raise ValueError("duplicate original issuer")
            by[symbol] = c
    if set(by) != set(TARGETS):
        raise ValueError("original annual filing missing")
    output = {
        "schema_version": 1, "scope": "US_FIVE_V1_MISSING_THREE_ORIGINAL_FY",
        "network_requests": 0, "scores_generated": 0, "issuer_reviews": [],
        "accounting_substitutions_approved": False,
        "multi_class_valuation_approved": False,
        "participation": "bilinmiyor", "investment_approved": False,
    }
    for symbol, (cik, gaps) in TARGETS.items():
        c = by[symbol]
        if c.get("issuer_id") != cik or not isinstance(c.get("period"), dict):
            raise ValueError("original CIK/annual period mismatch")
        src = c.get("source_evidence")
        if not isinstance(src, dict):
            raise ValueError("original source manifest unavailable")
        relative = src.get("fixture")
        if (not isinstance(relative, str) or not relative.startswith("tests/fixtures/")
                or ".." in Path(relative).parts or not relative.endswith(".html.gz")):
            raise ValueError("original fixture path unsafe")
        body = gzip.decompress((root / relative).read_bytes())
        sha = hashlib.sha256(body).hexdigest()
        if sha != src.get("sha256"):
            raise ValueError("original SEC SHA mismatch")
        period = c["period"]
        if period.get("issuer_id") != cik or period.get("raw_sha256") != sha:
            raise ValueError("original period provenance mismatch")
        start, end = date.fromisoformat(period["period_start"]), date.fromisoformat(period["period_end"])
        scanned = inspect_concepts(body, cik=cik, concepts=CANDIDATES[symbol],
                                   period_start=start, period_end=end)
        if scanned["raw_sha256"] != sha:
            raise ValueError("reparsed SEC source mismatch")
        concepts = [
            {"concept": row["concept"], "status": row["status"],
             "value": row["value"], "period_matches": len(row["matches"]),
             "dimensional_facts": row["dimensional_facts"],
             "other_period_facts": row["other_period_facts"]}
            for row in scanned["concepts"]
        ]
        review = {
            "symbol": symbol, "issuer_id": cik,
            "annual_period_start": start.isoformat(),
            "annual_period_end": end.isoformat(),
            "original_source_url": src["url"],
            "original_source_sha256": sha,
            "source_hash_reverified": True,
            "existing_missing_fields": list(gaps),
            "disclosed_concepts": concepts,
            "semantic_assessment": LIMITATIONS[symbol],
            "automatic_substitution": False, "score_eligible": False,
            "independent_participation_verified": False,
        }
        if symbol == "AMZN":
            try:
                # Existing conservative proof checks equity/minority/mezzanine
                # before doing a liabilities balance-equation reconciliation.
                proof = filing_derived_liabilities(body, cik=cik, period_end=end)
                review["liabilities_equation"] = {
                    "status": "verified_derived_not_literal",
                    "value": proof["value"],
                    "raw_sha256": proof["raw_sha256"],
                    "scope_approved": False,
                }
            except ProviderFailure:
                review["liabilities_equation"] = {
                    "status": "not_verified", "value": None,
                    "scope_approved": False,
                }
        if symbol == "GOOGL":
            review["security_class"] = {
                "status": "multiple_class_counts_verified_valuation_model_still_required",
                "classes": ("A", "B", "C"),
                **googl_cover_classes(body),
                "counts_source_sha256_verified": True,
            }
        output["issuer_reviews"].append(review)
    return output


def markdown(document):
    lines = [
        "# ABD beşli pilot: 3 eksik şirketin özgün 10-K denetimi", "",
        "Özgün SEC dosyaları SHA-256 ile yeniden doğrulandı. Ağ çağrısı: 0.",
        "Alternatif GAAP kavramları ve hisse sınıfları otomatik olarak mevcut skora aktarılmaz.",
        "",
    ]
    for row in document["issuer_reviews"]:
        lines += [
            "## " + row["symbol"], "",
            "CIK: " + row["issuer_id"] + " · 10-K dönem sonu: " + row["annual_period_end"],
            "SEC: " + row["original_source_url"],
            "SHA-256: " + row["original_source_sha256"], "",
            "| Özgün GAAP kavramı | Durum | USD değeri |",
            "|---|---|---:|",
        ]
        for c in row["disclosed_concepts"]:
            lines.append("| " + c["concept"] + " | " + c["status"] + " | "
                         + (c["value"] or "—") + " |")
        lines += ["", row["semantic_assessment"], ""]
        if row.get("liabilities_equation"):
            lines.append("AMZN yükümlülük köprüsü: "
                         + row["liabilities_equation"]["status"]
                         + " (doğrudan SEC Liabilities alanı değildir).")
        if row.get("security_class"):
            classes = row["security_class"]
            lines.append("GOOGL A/B/C hisse sınıfı analizi: "
                         + classes["status"])
            lines.append("10-K kapak payları (" + classes["cover_as_of"] + ", milyon): "
                         + ", ".join(c + "=" + str(n) for c, n in
                                     classes["reported_class_counts_million"].items()))
            lines.append("B sınıfı halka açık piyasa fiyatı yok; hisselerin toplamı "
                         "GOOGL fiyatı ile çarpılıp değerleme yapılamaz.")
        lines.append("")
    lines.append("Sonuç: 3 şirkete otomatik puan ve alım yetkisi verilmedi.")
    return "\n".join(lines) + "\n"


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--root", default=".")
    p.add_argument("--out", required=True)
    p.add_argument("--markdown", required=True)
    args = p.parse_args()
    doc = original_review(root=args.root)
    save_json(args.out, doc)
    Path(args.markdown).write_text(markdown(doc), encoding="utf-8")
    print(json.dumps({"status": "original_filing_audit_complete",
                      "source_hash_verified": len(doc["issuer_reviews"]),
                      "new_scores": 0,
                      "investment_approved": False}))


if __name__ == "__main__":
    main()
