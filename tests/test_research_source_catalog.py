"""Research catalog constraints: sources are evidence leads, never automatic trades."""
import json
import unittest
from pathlib import Path

from scripts.adaptive_investment_assistant import analyst_prompt

CATALOG = Path(__file__).resolve().parents[1] / "data/analyst/research_source_catalog.json"


class ResearchSourceCatalogTests(unittest.TestCase):
    def test_catalog_is_bounded_and_verifiable(self):
        doc = json.loads(CATALOG.read_text(encoding="utf-8"))
        self.assertEqual(doc["schema_version"], 1)
        self.assertGreaterEqual(len(doc["sources"]), 7)
        ids = [source["id"] for source in doc["sources"]]
        self.assertEqual(len(ids), len(set(ids)))
        for source in doc["sources"]:
            self.assertTrue(source["url"].startswith("https://"))
            self.assertIn(source["role"], {"primary", "secondary", "academic"})
            self.assertIn(source["priority"], {1, 2, 3})
            self.assertTrue(source["guardrail"])
        self.assertIn("sec_13f", ids)
        self.assertIn("bist_participation", ids)
        self.assertIn("fred", ids)

    def test_copycat_cannot_backdate_to_quarter_end(self):
        doc = json.loads(CATALOG.read_text(encoding="utf-8"))
        combined = " ".join(doc["global_rules"] + [
            next(h["test"] for h in doc["hypotheses"] if h["id"] == "copycat_lagged")])
        self.assertIn("yayımlanma", combined)
        self.assertIn("katılım", combined.lower())

    def test_assistant_prompt_includes_source_guardrails(self):
        packet = {
            "created_at": "2026-11-12T19:00:00+00:00",
            "markets": {"ABD": [], "BIST": [], "AVRUPA": []},
            "work_queue": [],
        }
        prompt = analyst_prompt(packet)
        self.assertIn("SEC EDGAR 13F", prompt)
        self.assertIn("Borsa İstanbul Katılım", prompt)
        self.assertIn("araştırma planıdır", prompt)
        self.assertIn("Büyük yatırımcı yoğunlaşması", prompt)


if __name__ == "__main__":
    unittest.main()
