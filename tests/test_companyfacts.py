import json
import gzip
import tempfile
import unittest
from dataclasses import replace
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

from equity_research.cache import FactCache
from equity_research.companyfacts import SecCompanyFacts, TAGS, companyfacts_url
from equity_research.models import FactRequest, Source
from equity_research.providers import ProviderFailure, Resolver, Status
from equity_research.transport import Response, strict_json

CIK = "0000320193"
NOW = datetime(2026, 11, 1, 18, tzinfo=timezone.utc)
START, END = date(2026, 7, 1), date(2026, 9, 30)
TAG = TAGS["revenue"][0]


def row(**changes):
    value = dict(start=str(START), end=str(END), val=123, filed="2026-10-29",
                 accn="0000320193-26-000001", form="10-Q")
    value.update(changes)
    return value


def payload(rows=None):
    return {"cik": int(CIK), "entityName": "Synthetic Company", "facts": {
        "us-gaap": {TAG: {"units": {"USD": rows if rows is not None else [row()]}}}}}


def req(**changes):
    return replace(FactRequest(CIK, "revenue", START, END, "USD", "currency", "us-gaap:"+TAG, NOW), **changes)


class Transport:
    max_bytes = 16_000_000

    def __init__(self, data=None, body=None):
        self.body = body if body is not None else json.dumps(data if data is not None else payload()).encode()
        self.calls, self.now = [], NOW

    def get(self, url):
        self.calls.append(url)
        return Response(url, self.body, self.now)


class CompanyFactsTests(unittest.TestCase):
    def provider(self, data=None, **kwargs):
        transport = Transport(data)
        return SecCompanyFacts(transport, clock=lambda: NOW, **kwargs)

    def test_value_and_filing_provenance(self):
        provider = self.provider()
        fact = provider.fetch(req())
        self.assertEqual(fact.value, Decimal(123))
        self.assertEqual(fact.filing_accession, "0000320193-26-000001")
        self.assertEqual(fact.filed_on, date(2026, 10, 29))
        self.assertEqual(fact.available_at, datetime(2026, 10, 30, 5, tzinfo=timezone.utc))
        self.assertEqual(fact.source_url, companyfacts_url(CIK))
        self.assertEqual(len(fact.raw_sha256), 64)
        self.assertIsNone(req().rejection(fact))

    def test_exact_period_and_no_annual_quarter_substitution(self):
        provider = self.provider(payload([row(start="2026-01-01"), row(end="2026-09-29")]))
        self.assertIsNone(provider.fetch(req()))

    def test_zero_and_negative_preserved(self):
        for value in (0, -10):
            with self.subTest(value=value):
                self.assertEqual(self.provider(payload([row(val=value)])).fetch(req()).value, Decimal(value))

    def test_decimal_json_has_no_binary_float_loss(self):
        body = json.dumps(payload()).replace('"val": 123', '"val": 123.1234567890123456789').encode()
        provider = SecCompanyFacts(Transport(body=body), clock=lambda: NOW)
        self.assertEqual(provider.fetch(req()).value, Decimal("123.1234567890123456789"))

    def test_missing_tag_unit_and_no_alias_inference(self):
        data = payload()
        data["facts"]["us-gaap"]["Revenues"] = data["facts"]["us-gaap"].pop(TAG)
        self.assertIsNone(self.provider(data).fetch(req()))
        self.assertIsNone(self.provider().fetch(req(currency="EUR")))

    def test_unsupported_field_and_semantics(self):
        for request, status in ((req(field="unknown"), Status.UNSUPPORTED_FIELD),
                                (req(accounting_definition="us-gaap:Revenues"), Status.INVALID_DATA),
                                (req(period_start=None), Status.INVALID_DATA)):
            provider = self.provider()
            with self.subTest(request=request), self.assertRaises(ProviderFailure) as ctx:
                provider.fetch(request)
            self.assertEqual(ctx.exception.status, status)
            self.assertEqual(provider.transport.calls, [])

    def test_instant_assets_mapping(self):
        data = payload()
        asset_row = row();asset_row.pop("start")
        data["facts"]["us-gaap"] = {"Assets": {"units": {"USD": [asset_row]}}}
        fact = self.provider(data).fetch(req(field="assets", period_start=None, accounting_definition="us-gaap:Assets"))
        self.assertIsNone(fact.period_start)

    def test_latest_filing_without_same_day_conflict(self):
        rows = [row(val=99, filed="2026-10-28"), row(val=100)]
        self.assertEqual(self.provider(payload(rows)).fetch(req()).value, Decimal(100))
        with self.assertRaises(ProviderFailure):
            self.provider(payload([row(val=99), row(val=100)])).fetch(req())

    def test_future_and_same_day_filing_not_used(self):
        self.assertIsNone(self.provider(payload([row(filed="2026-11-01")])).fetch(req()))

    def test_current_snapshot_cannot_serve_historical_cutoff(self):
        with self.assertRaises(ProviderFailure) as ctx:
            self.provider().fetch(req(as_of=NOW-timedelta(days=1)))
        self.assertEqual(ctx.exception.status, Status.INVALID_DATA)

    def test_identity_mismatch_is_not_missing(self):
        data=payload();data["cik"]=789019
        with self.assertRaises(ProviderFailure) as ctx:
            self.provider(data).fetch(req())
        self.assertEqual(ctx.exception.status, Status.SYMBOL_MISMATCH)

    def test_ifrs_is_unsupported_not_missing(self):
        data=payload();data["facts"]={"ifrs-full": {}}
        with self.assertRaises(ProviderFailure) as ctx:
            self.provider(data).fetch(req())
        self.assertEqual(ctx.exception.status, Status.UNSUPPORTED_FIELD)

    def test_malformed_data(self):
        for value in (True, "123", None):
            with self.subTest(value=value), self.assertRaises(ProviderFailure):
                self.provider(payload([row(val=value)])).fetch(req())
        for changes in ({"accn": "invalid"}, {"filed": "wrong"}, {"end": "wrong"}):
            with self.subTest(changes=changes), self.assertRaises(ProviderFailure):
                self.provider(payload([row(**changes)])).fetch(req())

    def test_bad_cik_never_becomes_url(self):
        for cik in ("123", "../../etc", "００００３２０１９３", "0000000000"):
            with self.subTest(cik=cik), self.assertRaises(ValueError):
                companyfacts_url(cik)

    def test_cross_field_fetch_reuses_snapshot(self):
        provider=self.provider()
        provider.fetch(req());provider.fetch(req());provider.fetch(req(currency="EUR"))
        self.assertEqual(len(provider.transport.calls), 1)

    def test_persistent_cache_and_original_retrieval_time(self):
        with tempfile.TemporaryDirectory() as tmp:
            first=self.provider(cache_dir=tmp);one=first.fetch(req())
            second=self.provider(cache_dir=tmp);two=second.fetch(req())
            self.assertEqual(one, two)
            self.assertEqual(second.transport.calls, [])
            self.assertEqual(second.cache_events, ["disk_hit:"+CIK])

    def test_corrupt_disk_cache_refreshes_without_fabrication(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.provider(cache_dir=tmp).fetch(req())
            path=Path(tmp)/(CIK+".json")
            envelope=json.loads(path.read_text());envelope["body"]="{}"
            path.write_text(json.dumps(envelope))
            provider=self.provider(cache_dir=tmp)
            self.assertEqual(provider.fetch(req()).value, Decimal(123))
            self.assertEqual(len(provider.transport.calls), 1)
            self.assertIn("invalid_cache:"+CIK, provider.cache_events)

    def test_expired_cache_and_force_refresh(self):
        with tempfile.TemporaryDirectory() as tmp:
            first=self.provider(cache_dir=tmp);first.fetch(req())
            later=NOW+timedelta(hours=7)
            second=SecCompanyFacts(Transport(),cache_dir=tmp,clock=lambda:later)
            second.transport.now=later
            second.fetch(req(as_of=later))
            self.assertEqual(len(second.transport.calls),1)
            second.snapshot(CIK,refresh=True)
            self.assertEqual(len(second.transport.calls),2)

    def test_fact_cache_roundtrip_preserves_filing_metadata(self):
        fact=self.provider().fetch(req())
        cache=FactCache(":memory:")
        try:
            cache.put(req(),fact,NOW)
            self.assertEqual(cache.get(req(),Source.SEC,NOW,timedelta(hours=1)),fact)
        finally:cache.close()

    def test_resolver_keeps_yahoo_priority(self):
        sec=self.provider()
        class Yahoo:
            source=Source.YAHOO
            def fetch(self, request):
                return replace(CompanyFactsTests().provider().fetch(request), source=Source.YAHOO)
        result=Resolver([sec,Yahoo()],clock=lambda:NOW).resolve(req())
        self.assertEqual(result.fact.source,Source.YAHOO)
        self.assertEqual(sec.transport.calls,[])

    def test_sec_only_records_yahoo_as_unconfigured(self):
        result=Resolver([self.provider()],clock=lambda:NOW).resolve(req())
        self.assertEqual(result.attempts[0].status,Status.NOT_CONFIGURED)
        self.assertEqual(result.fact.source,Source.SEC)

    def test_existing_json_rejects_nonfinite(self):
        with self.assertRaises(ProviderFailure):strict_json(b'{"val":Infinity}')

    def test_recorded_companyfacts_and_filing_reconciliation_replay(self):
        from equity_research.filingcheck import filing_assets
        import hashlib
        root=Path(__file__).resolve().parents[1]
        report=json.loads((root/'docs/evidence/companyfacts-live.json').read_text())
        self.assertEqual(len(report['companies']),3)
        for company in report['companies']:
            body=gzip.decompress((root/company['fixture']).read_bytes())
            self.assertEqual(hashlib.sha256(body).hexdigest(),company['sha256'])
            transport=Transport(body=body)
            transport.now=datetime.fromisoformat(company['retrieved_at'])
            cutoff=datetime.fromisoformat(report['recorded_at'])
            provider=SecCompanyFacts(transport,clock=lambda:cutoff)
            for metric in company['metrics']:
                if metric['status']!='extracted':continue
                request=FactRequest(company['cik'],metric['field'],date.fromisoformat(metric['period_start']) if metric['period_start'] else None,
                                    date.fromisoformat(metric['period_end']),'USD','currency',metric['accounting_definition'],cutoff)
                # Fake transport must return the actual requested issuer URL.
                fact=provider.fetch(request)
                self.assertEqual(fact.value,Decimal(metric['value']))
                self.assertEqual(fact.filing_accession,metric['filing_accession'])
            check=company['filing_reconciliation']
            self.assertEqual(check['status'],'matched')
            filing=gzip.decompress((root/check['fixture']).read_bytes())
            self.assertEqual(hashlib.sha256(filing).hexdigest(),check['sha256'])
            self.assertEqual(filing_assets(filing,cik=company['cik'],period_end=date.fromisoformat(company['asset_candidate']['end'])),Decimal(check['value']))
