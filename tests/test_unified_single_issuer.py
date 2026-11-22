"""Deterministic whole-pipeline smoke; fixture is never labeled live."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts import unified_single_issuer as target


class OneIssuer(unittest.TestCase):
    def fixture(self, root):
        path = Path(root) / "sample.json"
        path.write_text(json.dumps({"AAPL": [
            {"date": "2026-09-%02d" % day, "close": 100 + day}
            for day in range(1, 31)
        ]}), encoding="utf-8")
        return str(path)

    def test_fixture_end_to_end_no_false_approval(self):
        with tempfile.TemporaryDirectory() as root:
            report = target.build("AAPL", fixture=self.fixture(root))
        self.assertEqual(report["source"], "fixture")
        self.assertEqual(report["summary"]["mode"], "historical_fixture")
        self.assertEqual(report["summary"]["status"], "test_verisi")
        self.assertEqual(report["gates"]["fundamentals"], "blocked_missing_filing_evidence")
        self.assertEqual(report["gates"]["participation"], "unknown")
        self.assertFalse(report["eligible_for_trade"])
        self.assertFalse(report["investment_advice"])
        self.assertEqual(report["llm"]["status"], "disabled")

    def test_mock_five_handoffs_and_one_price_fetch(self):
        calls = []
        def fake_provider(payload):
            calls.append(payload["model"])
            return {"choices": [{"message": {"content": "Kanıt eksik, yatırım önerisi yok."}}]}
        with tempfile.TemporaryDirectory() as root:
            with patch.object(target, "price_history", wraps=target.price_history) as prices:
                report = target.build(
                    "AAPL", fixture=self.fixture(root),
                    agent_transport=fake_provider, enable_llm=True)
                prices.assert_called_once()
        self.assertEqual(calls, ["openrouter/free"] * 5)
        self.assertEqual(report["llm"]["llm_calls"], 5)
        self.assertFalse(report["eligible_for_trade"])

    def test_missing_fixture_fails_closed(self):
        with tempfile.TemporaryDirectory() as root:
            with self.assertRaisesRegex(ValueError, "missing"):
                target.build("MSFT", fixture=self.fixture(root))

    def test_live_price_source_failure_fails_closed(self):
        with patch.object(target.pilot, "fetch_yfinance", side_effect=OSError("offline")), \
             patch.object(target.pilot, "fetch_yahoo_chart", side_effect=OSError("offline")), \
             patch.object(target.pilot, "fetch_prices", side_effect=OSError("offline")):
            with self.assertRaisesRegex(RuntimeError, "no verified price history"):
                target.build("AAPL")


if __name__ == "__main__":
    unittest.main()
