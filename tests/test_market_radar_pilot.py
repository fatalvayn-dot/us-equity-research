"""Offline deterministic pilot tests, no network or account credentials."""
import unittest
from datetime import date, timedelta
from scripts.market_radar_pilot import signal, evaluate, run, news_digest

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

    def test_rss_dated_news_preserves_source_hash_and_prevents_future_leak(self):
        from unittest.mock import patch
        from datetime import datetime, timezone, timedelta
        from email.utils import format_datetime
        import hashlib
        now = datetime.now(timezone.utc)
        past = format_datetime(now-timedelta(days=1))
        future = format_datetime(now+timedelta(days=1))
        xml = ('<rss><channel><item><title>Apple tariff update</title>'
               '<pubDate>'+past+'</pubDate><link>https://example.org/1</link></item>'
               '<item><title>Apple future embargo</title><pubDate>'+future+
               '</pubDate></item><item><title>Apple undated rumor</title></item>'
               '</channel></rss>').encode()
        class FakeResponse:
            def __enter__(self): return self
            def __exit__(self, *args): return False
            def read(self, size): return xml
        with patch("scripts.market_radar_pilot.urllib.request.urlopen",
                   return_value=FakeResponse()):
            result = news_digest("https://news.example/rss")
        self.assertEqual(result["source_sha256"], hashlib.sha256(xml).hexdigest())
        self.assertEqual(result["dated_items"], 1)
        self.assertEqual(result["undated_items"], 1)
        self.assertEqual(result["future_dated_excluded"], 1)
        self.assertEqual(result["risk_count"], 1)
        self.assertFalse(result["event_price_impact_validated"])
        self.assertEqual(len(result["items"]), 2)

    def test_rss_missing_dates_cannot_be_claimed_as_time_validated(self):
        from unittest.mock import patch
        xml = b'<rss><channel><item><title>Apple news</title></item></channel></rss>'
        class FakeResponse:
            def __enter__(self): return self
            def __exit__(self, *args): return False
            def read(self, size): return xml
        with patch("scripts.market_radar_pilot.urllib.request.urlopen",
                   return_value=FakeResponse()):
            result = news_digest("https://news.example/rss")
        self.assertEqual(result["dated_items"], 0)
        self.assertEqual(result["undated_items"], 1)
        self.assertIsNone(result["items"][0]["published_at_utc"])

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
