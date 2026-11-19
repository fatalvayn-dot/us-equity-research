"""Offline two-issuer end-to-end replay; never passes invented data as live."""
from copy import deepcopy
import hashlib
import json
import unittest

from scripts.live_stage1_sec_verification import (
    PUBLIC_CLAIMS, companyconcept_url, expected_payload, fetch_official,
    run_once, verify_snapshot,
)


def raw_claims():
    return {companyconcept_url(c): json.dumps({
        "cik": int(c["cik"]), "taxonomy": "us-gaap", "tag": "Liabilities",
        "units": {"USD": [{
            "accn": c["accession"], "form": "10-K", "end": c["end"],
            "filed": c["filed"], "val": c["value"],
        }]},
    }, sort_keys=True).encode() for c in PUBLIC_CLAIMS}


class StageOneLiveReplayTests(unittest.TestCase):
    def test_two_exact_sources_replay_and_sha_are_deterministic(self):
        raw = raw_claims()
        report = run_once(raw, fetched_at="2026-11-19T15:00:00+00:00")
        self.assertEqual(report["verified_source_count"], 2)
        self.assertEqual(report["verified_record_count"], 2)
        self.assertEqual(report["replay_runs"], 2)
        self.assertTrue(report["replay_identical"])
        self.assertFalse(report["score_inputs_changed"])
        self.assertFalse(report["investment_approved"])
        self.assertEqual(report, run_once(raw, fetched_at="2026-11-19T15:00:00+00:00"))
        for row in report["records"]:
            self.assertEqual(row["source_raw_sha256"], hashlib.sha256(
                raw[row["source_url"]]).hexdigest())
            self.assertEqual(row["review_state"], "source_verified")
            self.assertEqual(row["unit"], "USD")

    def test_both_issuers_must_be_present(self):
        raw = raw_claims()
        raw.pop(companyconcept_url(PUBLIC_CLAIMS[1]))
        with self.assertRaisesRegex(ValueError, "exact two"):
            run_once(raw)

    def test_modified_financial_fact_and_accession_abort_all(self):
        raw = raw_claims()
        for key, bad in (("val", "123"), ("accn", "0001045810-25-000021"),
                         ("filed", "2026-03-01"), ("end", "2025-01-25")):
            altered = deepcopy(raw)
            url = companyconcept_url(PUBLIC_CLAIMS[0])
            doc = json.loads(altered[url])
            doc["units"]["USD"][0][key] = bad
            altered[url] = json.dumps(doc).encode()
            with self.subTest(field=key), self.assertRaises(ValueError):
                run_once(altered)

    def test_duplicate_filing_row_and_wrong_cik_abort(self):
        raw = raw_claims()
        url = companyconcept_url(PUBLIC_CLAIMS[1])
        doc = json.loads(raw[url])
        doc["units"]["USD"].append(deepcopy(doc["units"]["USD"][0]))
        raw[url] = json.dumps(doc).encode()
        with self.assertRaisesRegex(ValueError, "ambiguity"):
            verify_snapshot(raw)
        raw = raw_claims()
        doc = json.loads(raw[url]); doc["cik"] = 1
        raw[url] = json.dumps(doc).encode()
        with self.assertRaises(ValueError):
            verify_snapshot(raw)

    def test_official_fetch_is_bounded_to_two_static_urls(self):
        with self.assertRaises(ValueError):
            fetch_official("https://example.org/steal", "research UA")
        with self.assertRaises(ValueError):
            fetch_official(companyconcept_url(PUBLIC_CLAIMS[0]), "")
        self.assertEqual(expected_payload()["data"]["alexandria"][0]["data"]["concept"], "Liabilities")


if __name__ == "__main__":
    unittest.main()
