import copy
import unittest
from datetime import datetime, timezone
from scripts.adaptive_multiactive_watchlist import collect, validate_watchlist

T = datetime(2026, 11, 12, 16, tzinfo=timezone.utc)
DATA = {"schema_version": 1, "instruments": [
    {"symbol": "SPY", "asset_class": "etf", "currency": "USD"},
    {"symbol": "BTC-USD", "asset_class": "crypto", "currency": "USD"}]}


def mock_fetch(symbol):
    kind = "ETF" if symbol == "SPY" else "CRYPTOCURRENCY"
    return {"chart": {"error": None, "result": [{"meta": {
        "symbol": symbol, "currency": "USD", "instrumentType": kind,
        "regularMarketPrice": 100.0, "regularMarketTime": int(T.timestamp()) - 50
    }}]}}, "https://example.org/" + symbol


class MultiactiveTests(unittest.TestCase):
    def test_distinct_etf_and_crypto_without_trade_signals(self):
        r = collect(DATA, fetch=mock_fetch, clock=T)
        self.assertEqual([x["status"] for x in r["instruments"]], ["observed", "observed"])
        self.assertEqual(r["instruments"][0]["asset_class"], "etf")
        self.assertEqual(r["instruments"][1]["asset_class"], "crypto")
        self.assertNotIn("change_1d_pct", r["instruments"][0])
        self.assertIsNone(r["instruments"][0]["investment_action"])
        self.assertFalse(r["personal_portfolio_included"])

    def test_incorrect_asset_class_and_currency_are_unavailable(self):
        def wrong(symbol):
            r, url = mock_fetch(symbol)
            r["chart"]["result"][0]["meta"]["currency"] = "EUR"
            return r, url
        self.assertTrue(all(x["price"] is None for x in collect(DATA, fetch=wrong, clock=T)["instruments"]))

    def test_provider_error_never_invents_price(self):
        def fail(symbol):
            raise TimeoutError("failed")
        r = collect(DATA, fetch=fail, clock=T)
        self.assertTrue(all(x["status"] == "unavailable" for x in r["instruments"]))

    def test_duplicates_and_unexpected_fields_rejected(self):
        duplicate = copy.deepcopy(DATA)
        duplicate["instruments"].append(dict(duplicate["instruments"][0]))
        with self.assertRaises(ValueError):
            validate_watchlist(duplicate)
        bad = copy.deepcopy(DATA)
        bad["instruments"][0]["account_shares"] = 20
        with self.assertRaises(ValueError):
            validate_watchlist(bad)


if __name__ == "__main__":
    unittest.main()
