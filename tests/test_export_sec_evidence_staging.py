"""Synthetic offline regression for the MotherDuck SEC staging CSV exporter."""
import csv
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from scripts.export_sec_evidence_staging import prepare_export, staging_rows

CIK = "0000320193"
URL = f"https://data.sec.gov/api/xbrl/companyconcept/CIK{CIK}/us-gaap/Assets.json"


def sample():
    return {"data": {"alexandria": [{
        "provider": "sec-gov",
        "capability": "filings/concept",
        "data": {
            "cik": CIK, "concept": "Assets", "taxonomy": "us-gaap",
            "source_url": URL, "count": 1,
            "observed_at_ms": 1795078114482,
            "facts": [{
                "accession_number": "0000320193-26-000026",
                "form": "10-K", "end": "2026-09-26",
                "filed": "2026-11-03", "start": None,
                "unit": "USD", "value": 404548000000
            }],
        }
    }]}}


class StagingTests(unittest.TestCase):
    def test_csv_digest_exact_fields_and_no_automatic_approval(self):
        with tempfile.TemporaryDirectory() as d:
            csv_path = Path(d) / "sec.csv"
            manifest_path = Path(d) / "manifest.json"
            result = prepare_export(sample(), csv_path=csv_path,
                                    manifest_path=manifest_path)
            self.assertEqual(result["row_count"], 1)
            self.assertFalse(result["database_write_performed"])
            self.assertFalse(result["scoring_performed"])
            self.assertEqual(result["csv_sha256"],
                             hashlib.sha256(csv_path.read_bytes()).hexdigest())
            self.assertEqual(result, json.loads(manifest_path.read_text()))
            with csv_path.open(newline="", encoding="utf-8") as fh:
                rows = list(csv.DictReader(fh))
            self.assertEqual(rows[0]["reported_value"], "404548000000")
            self.assertEqual(rows[0]["review_state"], "exact_concept_candidate_unverified")
            self.assertEqual(rows[0]["source_raw_sha256"], "")
            self.assertEqual(rows[0]["period_start"], "")

    def test_same_observation_deduplicated(self):
        payload = sample()
        payload["data"]["alexandria"].append(deepcopy(payload["data"]["alexandria"][0]))
        self.assertEqual(len(staging_rows(payload)), 1)

    def test_conflicting_duplicate_aborts(self):
        payload = sample()
        additional = deepcopy(payload["data"]["alexandria"][0])
        additional["data"]["facts"][0]["value"] = 1
        payload["data"]["alexandria"].append(additional)
        with self.assertRaisesRegex(ValueError, "conflicting SEC evidence"):
            staging_rows(payload)

    def test_overflow_nonfinite_and_precision_aborts(self):
        for value in (10**33, 1.0000001, float("nan"), "1000"):
            payload = sample()
            payload["data"]["alexandria"][0]["data"]["facts"][0]["value"] = value
            with self.subTest(value=value), self.assertRaises(ValueError):
                staging_rows(payload)

    def test_source_forgery_rejected_not_written(self):
        payload = sample()
        payload["data"]["alexandria"][0]["data"]["source_url"] = "https://wrong.example/data"
        with tempfile.TemporaryDirectory() as d:
            out = Path(d) / "not.csv"
            with self.assertRaises(ValueError):
                prepare_export(payload, csv_path=out, manifest_path=Path(d) / "m.json")
            self.assertFalse(out.exists())

    def test_same_output_file_refused(self):
        with tempfile.TemporaryDirectory() as d, self.assertRaisesRegex(ValueError, "different"):
            prepare_export(sample(), csv_path=Path(d) / "same", manifest_path=Path(d) / "same")


if __name__ == "__main__":
    unittest.main()
