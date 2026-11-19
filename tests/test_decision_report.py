"""Offline contract tests for Turkish, non-trading decision report."""
from copy import deepcopy
from datetime import datetime, timezone
import gzip
import json
from pathlib import Path
import unittest

from equity_research.decision_report import build_decision_report, render_decision_markdown

ROOT = Path(__file__).resolve().parents[1]
FIELDS = {
    "financial_strength": ("10", 20),
    "valuation": ("5", 20),
    "growth": ("5", 20),
    "profitability": ("10", 15),
    "cash_flow": ("5", 15),
    "risk": ("8", 10),
}


def example():
    row = dict(
        symbol="SYNTH", issuer_id="0000320193", status="scored_research_hypothesis",
        rank=1, total_score="43", model_id="synthetic-test-only",
        components={k: {"score": s, "weight": w} for k, (s, w) in FIELDS.items()},
        blockers=[], sector_evidence={"source_url": "https://data.sec.gov/submissions/CIK0000320193.json",
                                      "raw_sha256": "b" * 64},
        market_risk={"source_url": "https://query1.finance.yahoo.com/sample",
                     "raw_sha256": "c" * 64},
        evidence={"financial_confirmations": [{"selected": {
            "source_url": "https://data.sec.gov/api/xbrl/companyfacts/CIK0000320193.json",
            "raw_sha256": "a" * 64,
        }}]},
    )
    return dict(schema_version=1, model_version="synthetic-test-only",
                as_of="2026-11-19T12:00:00+00:00",
                summary={"candidates": 1, "scored_companies": 1},
                companies=[row], input_provenance={"batches": {}})


def screen(status="kosullu_esik_gecisi"):
    return dict(issuer_key="SEC:0000320193", symbol="SYNTH",
                as_of="2026-11-19T11:00:00+00:00",
                status=status, rulebook_id="SYNTH_TEST", rulebook_version="v0",
                qualified_for_investment=False, shariah_certified=False,
                investment_approved=False, eligible_for_automatic_order=False)


class DecisionReportTests(unittest.TestCase):
    def test_report_keeps_score_provenance_and_separates_all_components(self):
        src = example()
        before = deepcopy(src)
        doc = build_decision_report(src)
        self.assertEqual(src, before)
        self.assertEqual(doc["puanli_sirket"], 1)
        c = doc["sirketler"][0]
        self.assertEqual(c["arastirma_puani"], "43")
        self.assertEqual(c["finansal"]["financial_strength"]["puan"], "10")
        self.assertEqual(c["degerleme"]["puan"], "5")
        self.assertEqual(c["risk"]["puan"], "8")
        self.assertEqual(c["katilim_durumu"], "bilinmiyor")
        self.assertEqual(len(c["kaynaklar"]), 3)
        self.assertIsNone(c["komisyon"])
        self.assertIsNone(c["kur_eur_performans"])
        self.assertIsNone(c["uzman_karari"])
        self.assertFalse(doc["yatirim_onayi"])
        self.assertFalse(c["otomatik_emir"])

    def test_conditional_pass_cannot_be_presented_as_investment_approval(self):
        d = build_decision_report(example(), [screen()])
        self.assertEqual(d["sirketler"][0]["katilim_durumu"], "kosullu_esik_gecisi")
        self.assertTrue(d["sirketler"][0]["katilim_kosullu_sonuc_sertifika_degil"])
        self.assertEqual(d["yatirim_onayli_sirket"], 0)
        self.assertIsNone(d["sirketler"][0]["uzman_karari"])
        fake = screen()
        fake["investment_approved"] = True
        with self.assertRaisesRegex(ValueError, "unverified participation approval"):
            build_decision_report(example(), [fake])

    def test_rejects_future_or_issuer_mismatched_participation(self):
        for key, value in (("as_of", "2026-11-20T09:00:00+00:00"),
                           ("symbol", "OTHER"),
                           ("issuer_key", "SEC:0000000001")):
            p = screen()
            p[key] = value
            with self.subTest(field=key), self.assertRaises(ValueError):
                build_decision_report(example(), [p])
        with self.assertRaises(ValueError):
            build_decision_report(example(), [screen(), screen()])

    def test_excluded_financial_sector_never_becomes_buy_eligible(self):
        src = example()
        c = src["companies"][0]
        c["status"] = "excluded_sector"
        c["total_score"] = None
        c["rank"] = None
        c["blockers"] = ["banking_or_insurance_permanently_excluded"]
        for value in c["components"].values():
            value["score"] = None
        src["summary"]["scored_companies"] = 0
        d = build_decision_report(src)
        self.assertEqual(d["sirketler"][0]["katilim_durumu"], "uygunsuz")
        self.assertIsNone(d["sirketler"][0]["arastirma_puani"])
        self.assertIsNone(d["sirketler"][0]["degerleme"]["puan"])
        self.assertIsNone(d["sirketler"][0]["uzman_karari"])

    def test_source_score_mismatch_and_fake_missing_zero_refused(self):
        src = example()
        src["companies"][0]["total_score"] = "99"
        with self.assertRaisesRegex(ValueError, "discrepancy"):
            build_decision_report(src)
        src = example()
        src["companies"][0]["components"]["risk"]["score"] = None
        with self.assertRaises(ValueError):
            build_decision_report(src)
        src = example()
        src["companies"][0]["components"]["risk"]["score"] = "22"
        with self.assertRaises(ValueError):
            build_decision_report(src)

    def test_turkish_report_preserves_unapproved_decisions_and_missing_fx(self):
        doc = build_decision_report(example())
        rendered = render_decision_markdown(doc)
        for token in ("Finansal (güç/büyüme/kârlılık/nakit)", "Değerleme", "Risk",
                      "Katılım", "Uzman kararı", "Verilmedi", "Bilinmiyor",
                      "AL / TUT / AZALT / SAT / BEKLE", "sıfır kabul edilmedi",
                      "https://data.sec.gov/", "SHA-256"):
            self.assertIn(token, rendered)
        self.assertNotIn("AL önerisi", rendered)

    def test_real_recorded_100_company_archive_presentation_only(self):
        raw = (ROOT / "docs/evidence/current-score100/report.json.gz").read_bytes()
        recorded = json.loads(gzip.decompress(raw))
        doc = build_decision_report(recorded)
        self.assertEqual(doc["aday_sayisi"], 100)
        self.assertEqual(doc["puanli_sirket"], recorded["summary"]["scored_companies"])
        self.assertEqual(doc["orijinal_kaynak_kesimi"], recorded["as_of"])
        self.assertEqual(doc["yatirim_onayli_sirket"], 0)
        self.assertEqual(sum(x["uzman_karari"] is None for x in doc["sirketler"]), 100)
        self.assertNotIn("mvp_accepted", doc)
        rendered = render_decision_markdown(doc)
        self.assertIn("Puan", rendered)
        self.assertIn("Katılım", rendered)


if __name__ == "__main__":
    unittest.main()
