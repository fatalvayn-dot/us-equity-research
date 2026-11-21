"""Offline, exact-source tests for the read-only Alexandria/SEC bridge."""
from copy import deepcopy
import importlib.util
from pathlib import Path
import unittest

PATH = Path(__file__).resolve().parents[1] / "scripts/audit_alexandria_sec_concept.py"
spec = importlib.util.spec_from_file_location("audit_alexandria_sec_concept", PATH)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

CIK = "0000320193"
URL = f"https://data.sec.gov/api/xbrl/companyconcept/CIK{CIK}/us-gaap/Assets.json"


def sample():
    return {"data": {"alexandria": [{
        "provider": "sec-gov", "capability": "filings/concept",
        "data": {
            "cik": CIK, "concept": "Assets", "taxonomy": "us-gaap",
            "source_url": URL, "observed_at_ms": 1795078114482, "count": 1,
            "facts": [{"accession_number": "0000320193-26-000026",
                       "end": "2026-09-26", "filed": "2026-11-03",
                       "start": None, "form": "10-K", "unit": "USD",
                       "value": 404548000000}],
        },
    }]}}


class AlexandriaAuditTests(unittest.TestCase):
    def test_exact_companyconcept_returns_only_unverified_evidence(self):
        result = module.audit_alexandria(sample())
        item = result["results"][0]
        self.assertEqual(item["issuer_id"], CIK)
        self.assertEqual(item["source_url"], URL)
        self.assertEqual(item["facts"][0]["value"], 404548000000)
        self.assertIsNone(item["source_raw_sha256"])
        self.assertEqual(item["decision"], "manual_review_only")
        self.assertFalse(result["investment_approved"])
        self.assertEqual(result["scored_companies"], 0)
        self.assertNotIn("total_score", str(result))

    def test_bare_alexandria_envelope_is_supported(self):
        raw = sample()["data"]
        self.assertEqual(module.audit_alexandria(raw)["results"][0]["concept"], "Assets")

    def test_wrong_url_or_filing_identity_rejected(self):
        for edit in (("source_url", URL.replace("data.sec.gov", "example.org")),
                     ("cik", "0000000001"), ("count", 2)):
            payload = deepcopy(sample())
            payload["data"]["alexandria"][0]["data"][edit[0]] = edit[1]
            with self.subTest(edit=edit), self.assertRaises(ValueError):
                module.audit_alexandria(payload)

    def test_wrong_accession_and_noncanonical_dates_rejected(self):
        for field, bad in (("accession_number", "0000789019-26-000026"),
                           ("filed", "2026-02-30"),
                           ("filed", "2025-01-01"), ("end", "2026-9-26")):
            payload = deepcopy(sample())
            payload["data"]["alexandria"][0]["data"]["facts"][0][field] = bad
            with self.subTest(field=field, bad=bad), self.assertRaises(ValueError):
                module.audit_alexandria(payload)

    def test_missing_or_unknown_provider_is_not_silent_success(self):
        payload = deepcopy(sample())
        payload["data"]["alexandria"][0]["provider"] = "unknown"
        with self.assertRaises(ValueError):
            module.audit_alexandria(payload)
        with self.assertRaises(ValueError):
            module.audit_alexandria({"data": {"alexandria": []}})

    def test_nan_or_wrong_unit_is_not_accepted(self):
        payload = deepcopy(sample())
        payload["data"]["alexandria"][0]["data"]["facts"][0]["value"] = float("nan")
        with self.assertRaises(ValueError):
            module.audit_alexandria(payload)
        payload = deepcopy(sample())
        payload["data"]["alexandria"][0]["data"]["facts"][0]["unit"] = None
        with self.assertRaises(ValueError):
            module.audit_alexandria(payload)


if __name__ == "__main__":
    unittest.main()
