"""Offline source contract tests; not live KAP, ESEF or ECB rate validation."""
import unittest

from equity_research.regional_evidence import (
    ECB_KEYS, SOURCE_PROBES, audit_ecb_reference_csv, audit_regional_discovery,
)


class RegionalEvidenceTests(unittest.TestCase):
    def test_all_six_verified_source_landing_pages_are_discovery_only(self):
        for (market, symbol), source in SOURCE_PROBES.items():
            with self.subTest(market=market, symbol=symbol):
                r = audit_regional_discovery(
                    market, symbol, source["url"],
                    observed_at="2026-11-19T11:00:00+00:00",
                    as_of="2026-11-19T12:00:00+00:00",
                )
                self.assertEqual(r["decision"], "source_discovery_only")
                self.assertEqual(r["financial_facts_verified"], 0)
                self.assertFalse(r["investment_approved"])
                self.assertFalse(r["shariah_approved"])
                self.assertFalse(r["historical_price_licensed"])

    def test_unmatched_landing_identity_or_source_url_rejected(self):
        source = SOURCE_PROBES[("BIST", "ASELS")]["url"]
        for market, ticker, url in (
            ("BIST", "GARAN", source),
            ("XETRA", "ASELS", source),
            ("BIST", "ASELS", "https://evil.example/kap"),
            ("BIST", "ASELS", source + "?preview=true"),
            ("BIST", "ASELS", source.replace("kap.org.tr", "kap.org.tr.evil.example")),
            ("BIST", "ASELS", source.replace("https://", "http://")),
        ):
            with self.subTest(ticker=ticker, url=url), self.assertRaises(ValueError):
                audit_regional_discovery(market, ticker, url,
                    observed_at="2026-11-19T11:00:00+00:00",
                    as_of="2026-11-19T12:00:00+00:00")

    def test_future_source_observation_rejected(self):
        source = SOURCE_PROBES[("XETRA", "IFX")]["url"]
        with self.assertRaisesRegex(ValueError, "future"):
            audit_regional_discovery("XETRA", "IFX", source,
                observed_at="2026-11-20T11:00:00+00:00",
                as_of="2026-11-19T12:00:00+00:00")

    def test_ecb_sdmx_reference_quote_is_not_execution_price(self):
        raw = (
            "KEY,TIME_PERIOD,OBS_VALUE,OBS_STATUS\n"
            "EXR.D.USD.EUR.SP00.A,2026-11-17,1.18,A\n"
            "EXR.D.USD.EUR.SP00.A,2026-11-18,1.17,A\n"
        ).encode()
        r = audit_ecb_reference_csv(raw, currency="USD",
            observed_at="2026-11-19T11:00:00+00:00",
            as_of="2026-11-19T12:00:00+00:00")
        self.assertEqual(r["base_currency"], "EUR")
        self.assertEqual(r["reference_rates"][-1]["currency_per_eur"], "1.17")
        self.assertEqual(r["decision"], "publication_time_and_trading_rate_review_required")
        self.assertTrue(r["not_executable_broker_fx"])
        self.assertFalse(r["investment_approved"])
        self.assertEqual(set(ECB_KEYS), {"USD", "TRY"})

    def test_rejects_wrong_ecb_key_duplicate_future_and_invalid_quote(self):
        template = "KEY,TIME_PERIOD,OBS_VALUE,OBS_STATUS\n"
        for rows in (
            "EXR.D.USD.EUR.SP00.A,2026-11-20,1.1,A\n",
            "EXR.D.USD.EUR.SP00.A,2026-11-17,0,A\n",
            "EXR.D.USD.EUR.SP00.A,2026-11-17,NaN,A\n",
            "EXR.D.USD.EUR.SP00.A,2026-11-17,1.1,P\n",
            "EXR.D.TRY.EUR.SP00.A,2026-11-17,55.0,A\n",
            "EXR.D.USD.EUR.SP00.A,2026-11-17,1.1,A\n"
            "EXR.D.USD.EUR.SP00.A,2026-11-17,1.1,A\n",
        ):
            with self.subTest(rows=rows), self.assertRaises(ValueError):
                audit_ecb_reference_csv((template+rows).encode(), currency="USD",
                    observed_at="2026-11-19T11:00:00+00:00",
                    as_of="2026-11-19T12:00:00+00:00")

    def test_empty_ecb_file_and_future_fetch_are_not_success(self):
        raw = b"KEY,TIME_PERIOD,OBS_VALUE\n"
        with self.assertRaisesRegex(ValueError, "no ECB"):
            audit_ecb_reference_csv(raw, currency="TRY",
                observed_at="2026-11-19T11:00:00+00:00",
                as_of="2026-11-19T12:00:00+00:00")
        with self.assertRaisesRegex(ValueError, "observed after"):
            audit_ecb_reference_csv(b"KEY,TIME_PERIOD,OBS_VALUE\nEXR.D.TRY.EUR.SP00.A,2026-11-18,55.0\n",
                currency="TRY", observed_at="2026-11-20T11:00:00+00:00",
                as_of="2026-11-19T12:00:00+00:00")


if __name__ == "__main__":
    unittest.main()
