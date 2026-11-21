"""Regression tests for quote/history shared Yahoo chart error mapping."""
import unittest

from equity_research.prices import yahoo_chart_error_status
from equity_research.providers import Status


class YahooChartErrorStatusTests(unittest.TestCase):
    def test_access_denied(self):
        for value in ("unauthorized", "FORBIDDEN"):
            with self.subTest(value=value):
                self.assertIs(yahoo_chart_error_status({"code": value}), Status.ACCESS_DENIED)

    def test_rate_limited(self):
        for value in ("too many requests", "RateLimit"):
            with self.subTest(value=value):
                self.assertIs(yahoo_chart_error_status({"code": value}), Status.RATE_LIMIT)

    def test_other_codes_and_empty_errors(self):
        self.assertIs(yahoo_chart_error_status({"code": "not found"}), Status.API_ERROR)
        self.assertIs(yahoo_chart_error_status("unexpected"), Status.API_ERROR)

    def test_invalid_code_type_and_original_messages(self):
        with self.assertRaisesRegex(ValueError, "^invalid error code$"):
            yahoo_chart_error_status({"code": 429})
        with self.assertRaisesRegex(ValueError, "^invalid provider error code$"):
            yahoo_chart_error_status({"code": 429},
                                     invalid_code_message="invalid provider error code")


if __name__ == "__main__":
    unittest.main()
