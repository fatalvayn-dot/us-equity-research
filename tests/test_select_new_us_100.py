"""Offline contracts for fresh SEC-listed 100 selection (no network)."""
import json
from pathlib import Path
import unittest

from scripts.select_new_us_100 import (
    choose, decode_directory, excluded_sic, priority_symbols, safe_candidate,
)

ROOT = Path(__file__).resolve().parents[1]


def mocks():
    old = json.loads((ROOT / "docs/evidence/archived100/candidates-2026-11-19.json").read_text())
    symbols = [s for s in priority_symbols() if s not in {r["symbol"] for r in old["companies"]}]
    fields = ["cik", "name", "ticker", "exchange"]
    records = []
    source = {}
    for i, ticker in enumerate(symbols):
        cik = 900000000 + i
        records.append([cik, ticker + " Research Manufacturer Inc", ticker, "Nasdaq"])
        source[str(cik).zfill(10)] = {
            "cik": cik, "tickers": [ticker], "entityType": "operating",
            "sic": "3674", "sicDescription": "Semiconductors",
            "name": ticker + " Research Manufacturer Inc",
            "filings": {"recent": {"form": ["10-K"]}},
        }
    directory = json.dumps({"fields": fields, "data": records}).encode()
    calls = []
    def loader(url):
        cik = url.split("CIK")[-1].removesuffix(".json")
        calls.append(cik)
        return json.dumps(source[cik]).encode()
    return old, directory, source, calls, loader


class Fresh100SelectionTests(unittest.TestCase):
    def test_100_distinct_old_cohort_free_issuer_and_sec_identity(self):
        old, directory, sources, calls, loader = mocks()
        chosen, proof = choose(directory, old, loader=loader)
        self.assertEqual(len(chosen["companies"]), 100)
        self.assertEqual(proof["old_issuers_excluded"], 100)
        self.assertEqual(len(proof["selected"]), 100)
        self.assertEqual(proof["submissions_attempts"], len(calls))
        self.assertFalse(proof["claims"]["investment_approved"])
        self.assertFalse(proof["claims"]["common_share_and_index_membership_confirmed"])
        self.assertFalse({x["issuer_id"] for x in chosen["companies"]} &
                         {x["issuer_id"] for x in old["companies"]})
        self.assertEqual(len(set(x["symbol"] for x in chosen["companies"])), 100)

    def test_bank_insurance_reit_tobacco_alcohol_gambling_is_blocked(self):
        for sic in ("6021", "6331", "6211", "6411", "6798", "6512",
                    "2111", "2082", "7999", "0000", "999"):
            with self.subTest(sic=sic):
                self.assertTrue(excluded_sic(sic))
        row = {"cik": 900001234, "name": "Blue River Manufacturing Inc",
               "exchange": "Nasdaq"}
        baseline = {"ciks": set(), "symbols": set()}
        record = {"cik": 900001234, "tickers": ["EXMP"],
                  "entityType": "operating", "sic": "3674",
                  "sicDescription": "Semiconductors", "name": "Blue River Inc",
                  "filings": {"recent": {"form": ["10-K"]}}}
        self.assertEqual(safe_candidate("EXMP", row, record, baseline)[0]["symbol"], "EXMP")
        for sic in ("6021", "6331", "6798", "2111", "2082", "7993"):
            bad = dict(record, sic=sic)
            self.assertIsNone(safe_candidate("EXMP", row, bad, baseline)[0])
        for change in (dict(tickers=["EXMP", "EXMPA"]),
                       dict(entityType="other"), dict(sicDescription="Gambling"),
                       dict(name="Example Casino Inc")):
            bad = dict(record, **change)
            self.assertIsNone(safe_candidate("EXMP", row, bad, baseline)[0])

    def test_invalid_listing_duplicate_and_out_of_scope_rejected(self):
        old, body, _m, _calls, loader = mocks()
        directory = json.loads(body)
        directory["data"] = directory["data"][:12]
        with self.assertRaisesRegex(ValueError, "100 distinct"):
            choose(json.dumps(directory).encode(), old, loader=loader)
        directory["data"].append(directory["data"][0])
        found = decode_directory(json.dumps(directory).encode())
        self.assertEqual(len(found[directory["data"][0][2]]), 2)
        self.assertTrue(priority_symbols())

    def test_maximum_source_requests_not_silently_exceeded(self):
        old, directory, _, calls, loader = mocks()
        with self.assertRaisesRegex(ValueError, "budget"):
            choose(directory, old, loader=loader, max_submissions=3)
        self.assertEqual(len(calls), 3)


if __name__ == "__main__":
    unittest.main()
