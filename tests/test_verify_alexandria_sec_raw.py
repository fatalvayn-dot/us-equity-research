"""Synthetic original-byte reconciliation, without network or DB access."""
import json
from pathlib import Path
import tempfile
import unittest

from scripts.verify_alexandria_sec_raw import verify_raw_sources

CIK = "0000320193"
SRC = f"https://data.sec.gov/api/xbrl/companyconcept/CIK{CIK}/us-gaap/Assets.json"


def firecrawl():
    return {"data": {"alexandria": [{
        "provider": "sec-gov", "capability": "filings/concept",
        "data": {
            "cik": CIK, "concept": "Assets", "taxonomy": "us-gaap",
            "source_url": SRC, "observed_at_ms": 1795078114482,
            "count": 1, "facts": [{
                "accession_number": "0000320193-26-000026",
                "end": "2026-09-26", "start": None, "filed": "2026-11-03",
                "form": "10-K", "unit": "USD", "value": 404548000000,
            }]
        },
    }]}}


def official():
    return {
        "cik": 320193, "taxonomy": "us-gaap", "tag": "Assets",
        "units": {"USD": [
            {"accn": "0000320193-26-000026", "end": "2026-09-26",
             "filed": "2026-11-03", "form": "10-K", "val": 404548000000}
        ]},
    }


class SecRawTests(unittest.TestCase):
    def write(self, root, value):
        path = Path(root) / f"{CIK}_us-gaap_Assets.json"
        raw = json.dumps(value).encode()
        path.write_bytes(raw)
        return path, raw

    def test_exact_raw_bytes_match_but_no_investment_approval(self):
        with tempfile.TemporaryDirectory() as folder:
            path, raw = self.write(folder, official())
            report = verify_raw_sources(firecrawl(), folder)
            self.assertEqual(report["verified_source_count"], 1)
            self.assertEqual(report["sources"][0]["matched_rows"], 1)
            self.assertFalse(report["investment_approved"])
            self.assertEqual(report["scored_companies"], 0)
            self.assertEqual(report["sources"][0]["decision"], "raw_sec_bytes_matched_not_approved")
            self.assertTrue(report["sources"][0]["source_raw_sha256"])
            self.assertFalse("404548000000" in json.dumps(report))
            self.assertTrue(path.exists())

    def test_mismatched_value_or_filing_is_not_verified(self):
        with tempfile.TemporaryDirectory() as folder:
            for key, bad in (("val", 4000), ("accn", "0000320193-25-000026"),
                             ("filed", "2026-11-04")):
                doc = official()
                doc["units"]["USD"][0][key] = bad
                self.write(folder, doc)
                with self.subTest(key=key), self.assertRaises(ValueError):
                    verify_raw_sources(firecrawl(), folder)

    def test_mismatched_company_and_concept_aborts(self):
        with tempfile.TemporaryDirectory() as folder:
            for key, bad in (("cik", 789019), ("taxonomy", "dei"), ("tag", "Liabilities")):
                doc = official()
                doc[key] = bad
                self.write(folder, doc)
                with self.subTest(key=key), self.assertRaisesRegex(ValueError, "mismatch"):
                    verify_raw_sources(firecrawl(), folder)

    def test_duplicate_raw_rows_fail_closed(self):
        with tempfile.TemporaryDirectory() as folder:
            doc = official()
            doc["units"]["USD"].append(dict(doc["units"]["USD"][0]))
            self.write(folder, doc)
            with self.assertRaisesRegex(ValueError, "ambiguity"):
                verify_raw_sources(firecrawl(), folder)

    def test_missing_original_fails_closed(self):
        with tempfile.TemporaryDirectory() as folder:
            with self.assertRaises(FileNotFoundError):
                verify_raw_sources(firecrawl(), folder)


if __name__ == "__main__":
    unittest.main()
