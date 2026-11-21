"""Offline guardrails for enlarging price observations from public files."""
import json
import pathlib
import tempfile
import unittest

from scripts.market_radar_pilot import DEFAULT_WATCH, run
from scripts.market_radar_universe import load_public_watch


def example():
    return {
        "schema_version": 1,
        "markets": {
            "ABD": [{"symbol": "MSFT", "currency": "USD"},
                    {"symbol": "NVDA", "currency": "USD"}],
            "BIST": [{"symbol": "ASELS.IS", "currency": "TRY"},
                     {"symbol": "TUPRS.IS", "currency": "TRY"}],
            "AVRUPA": [{"symbol": "SAP.DE", "currency": "EUR"}],
        },
    }


class UniverseGuardTests(unittest.TestCase):
    def load(self, data, base=DEFAULT_WATCH):
        with tempfile.TemporaryDirectory() as td:
            file = pathlib.Path(td) / "public.json"
            file.write_text(json.dumps(data), encoding="utf-8")
            return load_public_watch(file, base)

    def test_merge_preserves_pilot_and_deduplicates_known_symbols(self):
        watch, audit = self.load(example())
        self.assertEqual(audit["total_requested_symbols"], 11)
        self.assertEqual(sum(map(len, watch.values())), 11)
        self.assertEqual(watch["ABD_HISSE"]["MSFT"], "msft.us")
        self.assertIsNone(watch["ABD_HISSE"]["NVDA"])
        self.assertIsNone(watch["BIST_HISSE_ORNEK"]["TUPRS.IS"])
        self.assertEqual(audit["source_count_by_market"],
                         {"ABD": 2, "BIST": 2, "AVRUPA": 1})
        self.assertFalse(audit["investment_candidates"])
        self.assertFalse(audit["participation_verified"])

    def test_reject_private_or_unexpected_fields(self):
        data = example()
        data["markets"]["BIST"][0]["private_portfolio_quantity"] = 42
        with self.assertRaises(ValueError):
            self.load(data)

    def test_reject_duplicate_and_wrong_currency(self):
        data = example()
        data["markets"]["ABD"][1]["symbol"] = "MSFT"
        with self.assertRaises(ValueError):
            self.load(data)
        data = example()
        data["markets"]["AVRUPA"][0]["currency"] = "USD"
        with self.assertRaises(ValueError):
            self.load(data)

    def test_reject_unmapped_market_suffix(self):
        data = example()
        data["markets"]["BIST"][0]["symbol"] = "ASELS.DE"
        with self.assertRaises(ValueError):
            self.load(data)

    def test_finite_budget_enforced_before_fetch(self):
        data = example()
        data["markets"]["ABD"] = [
            {"symbol": "TEST" + str(i), "currency": "USD"} for i in range(6)
        ]
        with self.assertRaises(ValueError):
            self.load(data)

    def test_fixture_expansion_does_not_claim_market_research(self):
        data = example()
        with tempfile.TemporaryDirectory() as td:
            folder = pathlib.Path(td)
            file = folder / "universe.json"
            file.write_text(json.dumps(data), encoding="utf-8")
            prices = folder / "prices.json"
            prices.write_text(json.dumps({
                "NVDA": [{"date": "2026-09-" + str(i).zfill(2),
                          "close": 100 + i} for i in range(1, 29)]
            }), encoding="utf-8")
            out = run(fixture=str(prices), universe=str(file))
        self.assertEqual(out["coverage"]["requested"], 11)
        self.assertEqual(out["coverage"]["forecast_count"], 1)
        self.assertEqual(out["forecasts"][0]["symbol"], "NVDA")
        self.assertEqual(out["forecasts"][0]["source"], "fixture")
        self.assertFalse(out["universe"]["official_listing_verified"])
        self.assertFalse(out["restrictions"]["trading_recommendations"])

    def test_repo_public_list_loads_as_observational_sample(self):
        path = pathlib.Path("data/analyst/radar_small_us_trial.json")
        watch, audit = load_public_watch(path, DEFAULT_WATCH)
        self.assertEqual(audit["source_count_by_market"],
                         {"ABD": 5, "BIST": 0, "AVRUPA": 0})
        self.assertEqual(audit["total_requested_symbols"], 14)
        self.assertEqual(sum(map(len, watch.values())), 14)
        self.assertEqual(set(watch["ABD_HISSE"]),
                         {"AAPL", "MSFT", "NVDA", "AVGO", "AMZN", "GOOGL", "META"})

    def test_reject_original_full_research_file_at_small_trial_limit(self):
        path = pathlib.Path("data/analyst/public_research_universe.json")
        with self.assertRaises(ValueError):
            load_public_watch(path, DEFAULT_WATCH)


if __name__ == "__main__":
    unittest.main()
