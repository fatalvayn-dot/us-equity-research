"""Offline deterministic pilot tests, no network or account credentials."""
import unittest
from datetime import date, timedelta
from scripts.market_radar_pilot import signal, evaluate, run

def prices(n=30, rate=0.01):
    d=date(2026, 8, 1)
    return [{"date": (d+timedelta(days=i)).isoformat(), "close": round(100*(1+rate)**i, 6)} for i in range(n)]

class MarketRadarPilotTests(unittest.TestCase):
    def test_uptrend(self):
        out=signal(prices())
        self.assertEqual(out["direction"], "yukari")
        self.assertIsNone(out["confidence"])
        self.assertFalse(out["investment_advice"])

    def test_decline(self):
        self.assertEqual(signal(prices(rate=-0.01))["direction"], "asagi")

    def test_missing_data_rejected(self):
        with self.assertRaises(ValueError):
            signal(prices(n=21))

    def test_future_only_evaluation(self):
        rows=prices()
        early={"symbol":"SPY","as_of":rows[10]["date"],"direction":"yukari"}
        late={"symbol":"SPY","as_of":rows[-3]["date"],"direction":"yukari"}
        result=evaluate([early,late],{"SPY":rows})
        self.assertEqual(result[0]["hit"], True)
        self.assertEqual(result[1]["status"],"pending")

    def test_empty_fixture_not_fabricated(self):
        import json, tempfile, pathlib
        with tempfile.TemporaryDirectory() as directory:
            path=pathlib.Path(directory)/"sample.json"
            path.write_text(json.dumps({}),encoding="utf-8")
            r=run(fixture=str(path))
            self.assertEqual(r["forecasts"],[])
            self.assertEqual(r["coverage"]["bist"],"unavailable")

if __name__ == "__main__":
    unittest.main()
