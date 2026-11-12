import unittest
from datetime import datetime, timezone
from scripts.adaptive_daily_brief import build_brief, validate_universe, render_markdown


SAMPLE = {"schema_version": 1, "markets": {
    "ABD": [{"symbol": "MSFT", "currency": "USD"}],
    "BIST": [{"symbol": "ASELS.IS", "currency": "TRY"}],
    "AVRUPA": [{"symbol": "IFX.DE", "currency": "EUR"}]}}
ASOF = datetime(2026, 11, 12, 12, tzinfo=timezone.utc)


def fake_chart(symbol):
    currency = {"MSFT": "USD", "ASELS.IS": "TRY", "IFX.DE": "EUR"}[symbol]
    return {"chart": {"error": None, "result": [{
        "meta": {"symbol": symbol, "currency": currency, "instrumentType": "EQUITY",
                 "regularMarketPrice": 120, "previousClose": 115,
                 "regularMarketTime": int(ASOF.timestamp()) - 60}
    }]}}, "https://example.test/price/" + symbol


class DailyBriefTests(unittest.TestCase):
    def test_three_independent_markets_and_price_triggers(self):
        doc = build_brief(SAMPLE, fetch=fake_chart, clock=ASOF)
        self.assertEqual(list(doc["markets"]), ["ABD", "BIST", "AVRUPA"])
        self.assertEqual(doc["markets"]["ABD"][0]["price"], 120)
        self.assertEqual(doc["markets"]["BIST"][0]["research_trigger"], "price_move_abs_3pct")
        self.assertFalse(doc["portfolio_positions_included"])
        self.assertFalse(doc["participation_compliance_confirmed"])
        self.assertIn("ASELS.IS", render_markdown(doc))

    def test_daily_return_uses_dated_previous_session_not_chart_window_base(self):
        def yahoo_live(symbol):
            data, url = fake_chart(symbol)
            item = data["chart"]["result"][0]
            meta = item["meta"]
            meta.pop("previousClose")
            meta["chartPreviousClose"] = 75  # five-day starting price, NOT yesterday
            meta["exchangeTimezoneName"] = "America/New_York"
            item["timestamp"] = [
                int(datetime(2026, 11, 11, 15, tzinfo=timezone.utc).timestamp()),
                int(datetime(2026, 11, 12, 15, tzinfo=timezone.utc).timestamp())]
            item["indicators"] = {"quote": [{"close": [115, 120]}]}
            return data, url
        report = build_brief(SAMPLE, fetch=yahoo_live, clock=ASOF)
        row = report["markets"]["ABD"][0]
        self.assertEqual(row["change_1d_pct"], round((120/115-1)*100, 3))
        self.assertEqual(row["baseline_method"], "prior_dated_trading_session_close")
        self.assertEqual(row["baseline_date"], "2026-11-11")
        self.assertEqual(row["research_trigger"], "price_move_abs_3pct")

    def test_window_start_price_must_not_be_used_as_previous_close(self):
        def no_dated_bars(symbol):
            data, url = fake_chart(symbol)
            meta = data["chart"]["result"][0]["meta"]
            meta.pop("previousClose")
            meta["chartPreviousClose"] = 75
            return data, url
        report = build_brief(SAMPLE, fetch=no_dated_bars, clock=ASOF)
        self.assertIsNone(report["markets"]["ABD"][0]["change_1d_pct"])
        self.assertEqual(report["markets"]["ABD"][0]["research_trigger"],
                         "price_baseline_missing")

    def test_missing_previous_close_is_explicitly_flagged(self):
        def no_baseline(symbol):
            data, url = fake_chart(symbol)
            data["chart"]["result"][0]["meta"].pop("previousClose")
            return data, url
        report = build_brief(SAMPLE, fetch=no_baseline, clock=ASOF)
        self.assertIsNone(report["markets"]["ABD"][0]["change_1d_pct"])
        self.assertEqual(report["markets"]["ABD"][0]["research_trigger"],
                         "price_baseline_missing")

    def test_missing_provider_data_never_becomes_a_price(self):
        def failed(symbol):
            raise TimeoutError("provider down")
        doc = build_brief(SAMPLE, fetch=failed, clock=ASOF)
        for group in doc["markets"].values():
            self.assertIsNone(group[0]["price"])
            self.assertEqual(group[0]["status"], "source_unavailable")

    def test_currency_mismatch_is_rejected(self):
        def wrong(symbol):
            data, url = fake_chart(symbol)
            data["chart"]["result"][0]["meta"]["currency"] = "USD" if symbol != "MSFT" else "EUR"
            return data, url
        doc = build_brief(SAMPLE, fetch=wrong, clock=ASOF)
        self.assertTrue(all(group[0]["price"] is None for group in doc["markets"].values()))

    def test_reject_duplicate_symbols_and_unknown_market(self):
        duplicate = {"schema_version": 1, "markets": {
            "ABD": [{"symbol": "MSFT", "currency": "USD"}],
            "BIST": [{"symbol": "MSFT", "currency": "USD"}], "AVRUPA": []}}
        with self.assertRaises(ValueError):
            validate_universe(duplicate)
        with self.assertRaises(ValueError):
            validate_universe({"schema_version": 1, "markets": {"ABD": []}})


if __name__ == "__main__":
    unittest.main()
