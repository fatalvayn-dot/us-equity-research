import unittest
from datetime import date, timedelta
from unittest.mock import patch
from scripts import unified_aapl_backtest as audit
from scripts import market_radar_pilot as price


def bars(size=80):
    start = date(2026, 6, 1)
    return [
        {"date": (start + timedelta(days=i)).isoformat(),
         "close": 100 + i}
        for i in range(size)]


class WalkForwardTests(unittest.TestCase):
    def test_rising_history_agrees_with_naive_benchmark(self):
        result = audit.audit(bars())
        self.assertEqual(result["status"], "historical_uncalibrated_backtest")
        self.assertEqual(result["direction_hit_rate"], 1)
        self.assertEqual(result["benchmark_up_hit_rate"], 1)
        self.assertTrue(result["eligible_samples"] > 20)
        self.assertFalse(result["trained_model"])
        self.assertFalse(result["investment_approved"])

    def test_future_bars_never_enter_signal(self):
        history = bars()
        lengths = []
        original = price.signal
        def probe(prefix):
            lengths.append(len(prefix))
            return original(prefix)
        with patch.object(audit.radar, "signal", side_effect=probe):
            audit.audit(history)
        self.assertTrue(lengths)
        self.assertLessEqual(max(lengths), len(history) - 5)

    def test_future_outcomes_change_hit_rate_not_signal_rule(self):
        before = audit.audit(bars())["direction_hit_rate"]
        changed = bars()
        for i in range(len(changed)-5, len(changed)):
            changed[i]["close"] = 1 + (len(changed) - i)
        after = audit.audit(changed)["direction_hit_rate"]
        self.assertLess(after, before)

    def test_insufficient_data_and_wrong_symbol_fail_closed(self):
        self.assertIsNone(audit.audit(bars(22))["direction_hit_rate"])
        with self.assertRaisesRegex(ValueError, "AAPL-only"):
            audit.audit(bars(), symbol="MSFT")
