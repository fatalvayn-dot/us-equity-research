"""Synthetic contract tests, not real-data acceptance evidence."""
import tempfile
import unittest
from dataclasses import replace
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

from equity_research.cache import FactCache
from equity_research.models import Exchange, Fact, FactRequest, Issuer, Security, SecurityType, Source
from equity_research.policy import SCORE_WEIGHTS, analysis_status
from equity_research.providers import ProviderFailure, Resolver, Status

NOW = datetime(2026, 11, 1, 17, tzinfo=timezone.utc)
END = date(2026, 9, 30)
START = date(2026, 7, 1)
PUBLIC = NOW - timedelta(days=2)


def fact(**changes):
    base = Fact("0000320193", "revenue", Decimal("100.50"), Source.YAHOO,
                START, END, "USD", "currency", NOW, PUBLIC,
                "us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax",
                "https://example.org/synthetic-fixture")
    return replace(base, **changes)


def request(**changes):
    base = FactRequest("0000320193", "revenue", START, END, "USD", "currency",
                       "us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax", NOW)
    return replace(base, **changes)


class Stub:
    def __init__(self, source, result=None):
        self.source, self.result, self.calls = source, result, 0

    def fetch(self, req):
        self.calls += 1
        if isinstance(self.result, Exception):
            raise self.result
        return self.result


class ModelTests(unittest.TestCase):
    def test_cik_canonicalization_required(self):
        for cik in ("320193", "abcdefghij", "００００３２０１９３"):
            with self.subTest(cik=cik), self.assertRaises(ValueError):
                Issuer(cik, "Synthetic issuer")

    def test_non_common_and_inactive_out_of_scope(self):
        issuer = Issuer("0000320193", "Synthetic issuer")
        for exchange in Exchange:
            for kind in SecurityType:
                security = Security(issuer, "SYNTH", exchange, kind, True, NOW)
                self.assertEqual(security.in_scope(), kind is SecurityType.COMMON_STOCK)
            self.assertFalse(Security(issuer, "SYNTH", exchange, SecurityType.COMMON_STOCK, False, NOW).in_scope())

    def test_scope_requires_explicit_types(self):
        for changes in ({"active": "yes"}, {"exchange": "NASDAQ"}, {"security_type": "common_stock"}, {"observed_at": NOW.replace(tzinfo=None)}):
            args = dict(issuer=Issuer("0000320193", "Synthetic issuer"), symbol="SYNTH", exchange=Exchange.NASDAQ, security_type=SecurityType.COMMON_STOCK, active=True, observed_at=NOW)
            args.update(changes)
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                Security(**args)

    def test_invalid_fact_values(self):
        for value in (float("nan"), 1.0, True, Decimal("NaN"), Decimal("Infinity")):
            with self.subTest(value=value), self.assertRaises(ValueError):
                fact(value=value)

    def test_real_zero_and_negative_are_retained(self):
        self.assertEqual(fact(value=Decimal(0)).value, Decimal(0))
        self.assertEqual(fact(value=Decimal(-10)).value, Decimal(-10))

    def test_invalid_metadata(self):
        cases = [{"currency": "usd"}, {"currency": None}, {"unit": ""},
                 {"accounting_definition": ""}, {"source_url": "http://example.org"},
                 {"issuer_id": "wrong"}, {"source": "Yahoo"},
                 {"period_start": date(2026, 10, 1)},
                 {"available_at": datetime(2026, 9, 1, tzinfo=timezone.utc)},
                 {"available_at": NOW + timedelta(seconds=1)},
                 {"retrieved_at": NOW.replace(tzinfo=None)}]
        for changes in cases:
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                fact(**changes)

    def test_nonmonetary_unit_without_currency(self):
        self.assertIsNone(fact(field="shares", unit="shares", currency=None).currency)

    def test_request_mismatches(self):
        changes = [{"issuer_id": "0000789019"}, {"field": "profit"},
                   {"period_start": None}, {"period_end": date(2026, 9, 29)},
                   {"currency": "EUR"}, {"unit": "currency_per_share"},
                   {"accounting_definition": "different-taxonomy"}]
        for change in changes:
            with self.subTest(change=change):
                self.assertIsNotNone(request().rejection(fact(**change)))

    def test_point_in_time_cutoff(self):
        req = request(as_of=PUBLIC - timedelta(seconds=1))
        self.assertEqual(req.rejection(fact()), "not_yet_public")

    def test_current_download_does_not_prove_historical_vintage(self):
        req = request(as_of=PUBLIC + timedelta(seconds=1))
        self.assertEqual(req.rejection(fact()), "unverified_historical_vintage")

    def test_invalid_request_time(self):
        for changes in ({"as_of": NOW.replace(tzinfo=None)}, {"period_end": date(2027, 1, 1)}, {"period_start": date(2026, 10, 1)}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                request(**changes)


class ResolverTests(unittest.TestCase):
    def test_source_order_enforced_and_first_valid_stops(self):
        yahoo = Stub(Source.YAHOO, fact())
        sec = Stub(Source.SEC, fact(source=Source.SEC))
        result = Resolver([sec, yahoo], lambda: NOW).resolve(request())
        self.assertEqual(result.fact.source, Source.YAHOO)
        self.assertEqual((yahoo.calls, sec.calls), (1, 0))

    def test_full_fallback_chain(self):
        providers = [Stub(source) for source in Source]
        providers[-1].result = fact(source=Source.FINNHUB)
        result = Resolver(providers, lambda: NOW).resolve(request())
        self.assertEqual(result.fact.source, Source.FINNHUB)
        self.assertEqual([a.source for a in result.attempts], list(Source))

    def test_all_missing_requires_four_successful_responses(self):
        result = Resolver([Stub(source) for source in Source]).resolve(request())
        self.assertTrue(result.confirmed_absent)

    def test_unconfigured_is_not_missing(self):
        result = Resolver([]).resolve(request())
        self.assertFalse(result.confirmed_absent)
        self.assertTrue(all(a.status is Status.NOT_CONFIGURED for a in result.attempts))

    def test_failure_classes_not_negative_evidence(self):
        for status in (Status.API_ERROR, Status.RATE_LIMIT, Status.SYMBOL_MISMATCH, Status.NOT_CONFIGURED):
            with self.subTest(status=status):
                providers = [Stub(source) for source in Source]
                providers[0].result = ProviderFailure(status)
                result = Resolver(providers).resolve(request())
                self.assertEqual(result.attempts[0].status, status)
                self.assertFalse(result.confirmed_absent)

    def test_unexpected_exception_is_sanitized(self):
        result = Resolver([Stub(Source.YAHOO, RuntimeError("api_key=secret"))]).resolve(request())
        self.assertEqual(result.attempts[0].detail, "RuntimeError")
        self.assertNotIn("secret", repr(result))

    def test_invalid_response_type(self):
        result = Resolver([Stub(Source.YAHOO, 0)]).resolve(request())
        self.assertEqual(result.attempts[0].status, Status.INVALID_DATA)

    def test_mismatched_identity(self):
        result = Resolver([Stub(Source.YAHOO, fact(issuer_id="0000789019"))]).resolve(request())
        self.assertEqual(result.attempts[0].status, Status.SYMBOL_MISMATCH)
        self.assertIsNone(result.fact)

    def test_wrong_source_and_period_fall_back(self):
        for bad in (fact(source=Source.NASDAQ), fact(period_start=None)):
            yahoo = Stub(Source.YAHOO, bad)
            sec = Stub(Source.SEC, fact(source=Source.SEC))
            result = Resolver([yahoo, sec]).resolve(request())
            self.assertEqual(result.fact.source, Source.SEC)
            self.assertEqual(result.attempts[0].status, Status.INVALID_DATA)

    def test_duplicate_sources_rejected(self):
        with self.assertRaises(ValueError):
            Resolver([Stub(Source.SEC), Stub(Source.SEC)])

    def test_missing_cannot_be_raised_as_error(self):
        with self.assertRaises(ValueError):
            ProviderFailure(Status.MISSING)


class CacheTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / "cache.sqlite"
        self.cache = FactCache(self.path)

    def tearDown(self):
        self.cache.close()
        self.tmp.cleanup()

    def test_decimal_roundtrip_and_restart_persistence(self):
        precise = fact(value=Decimal("1234567890.123456789"))
        self.cache.put(request(), precise, NOW)
        self.cache.close()
        self.cache = FactCache(self.path)
        self.assertEqual(self.cache.get(request(), Source.YAHOO, NOW, timedelta(hours=1)), precise)

    def test_expiry_boundary_and_clock_rollback(self):
        self.cache.put(request(), fact(), NOW)
        for time in (NOW - timedelta(seconds=1), NOW + timedelta(hours=1)):
            self.assertIsNone(self.cache.get(request(), Source.YAHOO, time, timedelta(hours=1)))

    def test_cache_does_not_cross_period_source_or_asof(self):
        self.cache.put(request(), fact(), NOW)
        for req, source in ((request(period_start=None), Source.YAHOO), (request(), Source.SEC), (request(as_of=NOW-timedelta(seconds=1)), Source.YAHOO)):
            self.assertIsNone(self.cache.get(req, source, NOW, timedelta(hours=1)))

    def test_invalid_fact_cannot_enter_cache(self):
        with self.assertRaises(ValueError):
            self.cache.put(request(), fact(currency="EUR"), NOW)

    def test_invalid_ttl_and_storage_clock(self):
        with self.assertRaises(ValueError):
            self.cache.get(request(), Source.YAHOO, NOW, timedelta(0))
        with self.assertRaises(ValueError):
            self.cache.put(request(), fact(), NOW-timedelta(seconds=1))


class PolicyTests(unittest.TestCase):
    def test_user_weights_are_exact_and_immutable(self):
        self.assertEqual(dict(SCORE_WEIGHTS), dict(financial_strength=20, valuation=20, growth=20, profitability=15, cash_flow=15, risk=10))
        self.assertEqual(sum(SCORE_WEIGHTS.values()), 100)
        with self.assertRaises(TypeError):
            SCORE_WEIGHTS["growth"] = 0

    def test_sector_and_data_gates_do_not_fabricate_scores(self):
        self.assertEqual(analysis_status(in_scope=True, complete=False, sector_model_supported=True), "pending_data")
        self.assertEqual(analysis_status(in_scope=True, complete=True, sector_model_supported=False), "unsupported_sector_model")
        self.assertEqual(analysis_status(in_scope=False, complete=True, sector_model_supported=True), "out_of_scope")
        self.assertEqual(analysis_status(in_scope=True, complete=True, sector_model_supported=True), "ready_for_model_validation")


class PipelineIntegrationTests(unittest.TestCase):
    def test_resolution_to_persistent_cache_without_network(self):
        req = request()
        yahoo = Stub(Source.YAHOO, ProviderFailure(Status.RATE_LIMIT))
        sec = Stub(Source.SEC, fact(source=Source.SEC))
        result = Resolver([yahoo, sec], lambda: NOW).resolve(req)
        self.assertEqual([a.status for a in result.attempts], [Status.RATE_LIMIT, Status.VALID])
        with tempfile.TemporaryDirectory() as tmp:
            cache = FactCache(Path(tmp) / "facts.sqlite")
            try:
                cache.put(req, result.fact, NOW)
                recovered = cache.get(req, Source.SEC, NOW+timedelta(minutes=1), timedelta(hours=1))
                self.assertEqual(recovered, result.fact)
                self.assertEqual(req.rejection(recovered), None)
            finally:
                cache.close()
