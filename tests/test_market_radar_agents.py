"""Offline tests for time-bounded append-only research agent loop."""
import json
import pathlib
import tempfile
import unittest
from datetime import datetime, timezone, timedelta
from scripts import market_radar_agents as agents


def sample(mode="live_attempt"):
    return {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "mode": mode,
        "forecasts": [{
            "symbol": "SPY",
            "as_of": (datetime.now(timezone.utc) - timedelta(days=1)).date().isoformat(),
            "direction": "yukari", "source": "stooq_daily", "close": 100.0,
            "method": "5d_20d_momentum_baseline",
            "eligibility": "bilinmiyor", "investment_advice": False,
        }],
        "evaluation": [], "errors": [],
        "news": {"status": "not_configured"},
        "coverage": {"forecast_count": 1, "requested": 7},
    }


class ScheduledAgentTests(unittest.TestCase):
    def test_append_once_per_date(self):
        raw = sample()
        summary, preds, outcomes = agents.process(raw, [], [])
        self.assertEqual(summary["new_predictions"], 1)
        self.assertFalse(preds[0]["investment_advice"])
        second, again, _ = agents.process(raw, preds, outcomes)
        self.assertEqual(second["new_predictions"], 0)
        self.assertEqual(len(again), 1)

    def test_fixture_never_live(self):
        summary, preds, _ = agents.process(sample("historical_fixture"), [], [])
        self.assertEqual(summary["status"], "test_verisi")
        self.assertEqual(preds, [])

    def test_future_and_permission_guard(self):
        raw = sample()
        raw["forecasts"][0]["as_of"] = (
            datetime.now(timezone.utc) + timedelta(days=2)).date().isoformat()
        _, preds, _ = agents.process(raw, [], [])
        self.assertEqual(preds, [])
        raw = sample()
        raw["forecasts"][0]["investment_advice"] = True
        summary, preds, _ = agents.process(raw, [], [])
        self.assertEqual(preds, [])
        self.assertTrue(summary["warnings"])

    def test_maturity_evaluated_once(self):
        raw = sample()
        _, old, _ = agents.process(raw, [], [])
        raw["forecasts"] = []
        raw["evaluation"] = [{
            "symbol": old[0]["symbol"], "as_of": old[0]["as_of"],
            "status": "evaluated", "actual": "yukari",
            "realized_5d": 0.034, "hit": True,
        }]
        summary, _, evaluated = agents.process(raw, old, [])
        self.assertEqual(summary["new_evaluations"], 1)
        self.assertEqual(summary["direction_hit_rate"], 1)
        second, _, same = agents.process(raw, old, evaluated)
        self.assertEqual(second["new_evaluations"], 0)
        self.assertEqual(same, evaluated)

    def test_invalid_ledger_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            file = pathlib.Path(tmp) / "ledger.jsonl"
            file.write_text('{"broken":}\n', encoding="utf-8")
            with self.assertRaises(json.JSONDecodeError):
                agents.read_jsonl(file)

    def test_zero_live_data_not_success(self):
        raw = sample()
        raw["forecasts"] = []
        summary, _, _ = agents.process(raw, [], [])
        self.assertEqual(summary["status"], "canli_veri_yok")


if __name__ == "__main__":
    unittest.main()
