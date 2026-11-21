"""Network-free tests for the upstream yfinance adapter and source priority."""
import sys
import unittest
from datetime import date, timedelta
from types import SimpleNamespace
from unittest.mock import patch

from scripts import market_radar_pilot as pilot


def history_rows():
    start = date(2026, 9, 1)
    return [{"date": (start + timedelta(days=i)).isoformat(),
             "close": float(100 + i)} for i in range(32)]


class FakeHistory:
    empty = False

    def iterrows(self):
        for row in history_rows():
            yield (date.fromisoformat(row["date"]), {"Close": row["close"]})


class YFinanceAdapterTests(unittest.TestCase):
    def test_upstream_history_parses_completed_closes(self):
        ticker = SimpleNamespace(history=lambda **kwargs: FakeHistory())
        stub = SimpleNamespace(Ticker=lambda symbol: ticker)
        with patch.dict(sys.modules, {"yfinance": stub}):
            rows = pilot.fetch_yfinance("ASELS.IS")
        self.assertEqual(len(rows), 32)
        self.assertEqual(rows[-1]["close"], 131.0)

    def test_empty_upstream_history_rejected(self):
        empty = SimpleNamespace(empty=True)
        ticker = SimpleNamespace(history=lambda **kwargs: empty)
        with patch.dict(sys.modules, {"yfinance": SimpleNamespace(Ticker=lambda symbol: ticker)}):
            with self.assertRaises(ValueError):
                pilot.fetch_yfinance("BAD.IS")

    def test_bist_provider_uses_upstream_without_extra_requests(self):
        with patch.object(pilot, "DEFAULT_WATCH", {"BIST_HISSE_ORNEK": {"ASELS.IS": None}}):
            with patch.object(pilot, "fetch_yfinance", return_value=history_rows()) as yf:
                with patch.object(pilot, "fetch_yahoo_chart", side_effect=AssertionError("unexpected")):
                    result = pilot.run()
        self.assertEqual(result["coverage"]["forecast_count"], 1)
        self.assertEqual(result["forecasts"][0]["source"], "yfinance_daily")
        self.assertEqual(result["forecasts"][0]["symbol"], "ASELS.IS")
        self.assertEqual(result["forecasts"][0]["investment_advice"], False)
        yf.assert_called_once_with("ASELS.IS")

    def test_yahoo_fallback_records_true_provider(self):
        with patch.object(pilot, "DEFAULT_WATCH", {"BIST_HISSE_ORNEK": {"ASELS.IS": None}}):
            with patch.object(pilot, "fetch_yfinance", side_effect=ValueError("unavailable")):
                with patch.object(pilot, "fetch_yahoo_chart", return_value=history_rows()):
                    result = pilot.run()
        self.assertEqual(result["forecasts"][0]["source"], "yahoo_chart_daily")
        self.assertEqual(result["errors"], [])

    def test_all_providers_missing_records_an_error_not_price(self):
        with patch.object(pilot, "DEFAULT_WATCH", {"BIST_HISSE_ORNEK": {"ASELS.IS": None}}):
            with patch.object(pilot, "fetch_yfinance", side_effect=ValueError("blocked")):
                with patch.object(pilot, "fetch_yahoo_chart", side_effect=ValueError("blocked")):
                    result = pilot.run()
        self.assertEqual(result["forecasts"], [])
        self.assertEqual(result["coverage"]["forecast_count"], 0)
        self.assertEqual(len(result["errors"][0]["attempts"]), 2)


if __name__ == "__main__":
    unittest.main()
