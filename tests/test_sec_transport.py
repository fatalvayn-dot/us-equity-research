"""Synthetic response fixtures; live evidence is recorded separately."""
import io
import json
import subprocess
import sys
import unittest
from pathlib import Path
from datetime import datetime, timezone
from email.message import Message
from urllib.error import HTTPError, URLError

from equity_research.providers import ProviderFailure, Status
from equity_research.sec import DIRECTORY_URL, SecDirectory, parse_directory
from equity_research.transport import HttpTransport, NoRedirect, RateLimiter, Response, strict_json

NOW = datetime(2026, 11, 1, 17, tzinfo=timezone.utc)
BODY = json.dumps({"fields": ["cik", "name", "ticker", "exchange"],
                   "data": [[320193, "Apple Inc.", "AAPL", "Nasdaq"],
                            [1067983, "Berkshire Hathaway Inc.", "BRK-B", "NYSE"],
                            [1067983, "Berkshire Hathaway Inc.", "BRK-A", "NYSE"]]}).encode()


class Clock:
    def __init__(self):
        self.value, self.sleeps = 100.0, []

    def monotonic(self):
        return self.value

    def sleep(self, value):
        self.sleeps.append(value)
        self.value += value


class FakeResponse(io.BytesIO):
    status = 200

    def __init__(self, body=BODY, headers=None, url=DIRECTORY_URL):
        super().__init__(body)
        self.headers = headers or {}
        self.url = url

    def geturl(self):
        return self.url


class Opener:
    def __init__(self, *responses):
        self.responses, self.calls = list(responses), []

    def open(self, req, timeout):
        self.calls.append((req, timeout))
        value = self.responses.pop(0)
        if isinstance(value, Exception):
            raise value
        return value


def http_error(code, retry_after=None):
    headers = Message()
    if retry_after:
        headers['Retry-After'] = retry_after
    return HTTPError(DIRECTORY_URL, code, "fixture", headers, io.BytesIO(b"do not log"))


class TransportTests(unittest.TestCase):
    def transport(self, opener, **changes):
        self.clock = Clock()
        args = dict(user_agent="Synthetic tests contact@example.org", allowed_hosts={"www.sec.gov"},
                    monotonic=self.clock.monotonic, sleep=self.clock.sleep,
                    clock=lambda: NOW, opener=opener)
        args.update(changes)
        return HttpTransport(**args)

    def test_headers_deadline_and_checksum(self):
        opener = Opener(FakeResponse())
        response = self.transport(opener).get(DIRECTORY_URL)
        self.assertEqual(response.body, BODY)
        self.assertEqual(response.retrieved_at, NOW)
        self.assertEqual(len(response.sha256), 64)
        req, timeout = opener.calls[0]
        self.assertEqual(req.get_header("Accept-encoding"), "identity")
        self.assertIn("Synthetic tests", req.get_header("User-agent"))
        self.assertEqual(timeout, 10)

    def test_url_allowlist(self):
        transport = self.transport(Opener())
        for url in ("http://www.sec.gov/a", "https://evil.sec.gov/a", "https://www.sec.gov.evil.org/a",
                    "https://user:secret@www.sec.gov/a", "https://www.sec.gov:123/a",
                    "https://www.sec.gov/a#x", "https://www.sec.gov/a\n"):
            with self.subTest(url=url), self.assertRaises(ValueError):
                transport.get(url)

    def test_redirect_handler_never_follows(self):
        self.assertIsNone(NoRedirect().redirect_request(None, None, 302, "", {}, "https://evil.org"))

    def test_redirect_and_404_are_not_missing_financial_data(self):
        for code in (301, 302, 404):
            opener = Opener(http_error(code))
            with self.subTest(code=code), self.assertRaises(ProviderFailure) as ctx:
                self.transport(opener).get(DIRECTORY_URL)
            self.assertEqual(ctx.exception.status, Status.API_ERROR)
            self.assertEqual(len(opener.calls), 1)

    def test_access_denied_does_not_retry(self):
        for code in (401, 403):
            opener = Opener(http_error(code))
            with self.subTest(code=code), self.assertRaises(ProviderFailure) as ctx:
                self.transport(opener).get(DIRECTORY_URL)
            self.assertEqual(ctx.exception.status, Status.ACCESS_DENIED)
            self.assertEqual(len(opener.calls), 1)

    def test_429_honors_retry_after_then_recovers(self):
        opener = Opener(http_error(429, "3"), FakeResponse())
        transport = self.transport(opener)
        self.assertEqual(transport.get(DIRECTORY_URL).body, BODY)
        self.assertEqual(self.clock.sleeps, [3.0])

    def test_retry_after_exceeding_budget_never_retries_early(self):
        opener = Opener(http_error(429, "600"))
        with self.assertRaises(ProviderFailure) as ctx:
            self.transport(opener).get(DIRECTORY_URL)
        self.assertEqual(ctx.exception.status, Status.RATE_LIMIT)
        self.assertEqual(len(opener.calls), 1)
        self.assertEqual(self.clock.sleeps, [])

    def test_http_date_retry_after(self):
        opener = Opener(http_error(503, "Sun, 01 Nov 2026 17:00:02 GMT"), FakeResponse())
        self.transport(opener).get(DIRECTORY_URL)
        self.assertEqual(self.clock.sleeps, [2.0])

    def test_bounded_transient_retries(self):
        opener = Opener(*(http_error(503) for _ in range(3)))
        with self.assertRaises(ProviderFailure) as ctx:
            self.transport(opener).get(DIRECTORY_URL)
        self.assertEqual(ctx.exception.status, Status.API_ERROR)
        self.assertEqual(len(opener.calls), 3)
        self.assertEqual(self.clock.sleeps, [1.0, 2.0])

    def test_timeout_and_network_error_classification(self):
        for error, status in ((TimeoutError(), Status.TIMEOUT), (URLError(TimeoutError()), Status.TIMEOUT), (URLError("secret"), Status.API_ERROR)):
            with self.subTest(status=status), self.assertRaises(ProviderFailure) as ctx:
                self.transport(Opener(error), max_attempts=1).get(DIRECTORY_URL)
            self.assertEqual(ctx.exception.status, status)
            self.assertNotIn("secret", str(ctx.exception))

    def test_payload_limits_and_encoding(self):
        for response in (FakeResponse(b"12345"), FakeResponse(b"x", {"Content-Length": "99"}),
                         FakeResponse(b"x", {"Content-Length": "2"}),
                         FakeResponse(b"x", {"Content-Encoding": "gzip"})):
            with self.subTest(headers=response.headers), self.assertRaises(ProviderFailure) as ctx:
                self.transport(Opener(response), max_bytes=4).get(DIRECTORY_URL)
            self.assertEqual(ctx.exception.status, Status.INVALID_DATA)

    def test_unexpected_response_destination_rejected(self):
        with self.assertRaises(ProviderFailure):
            self.transport(Opener(FakeResponse(url="https://evil.org"))).get(DIRECTORY_URL)

    def test_rate_limiter_spaces_sequential_requests(self):
        opener = Opener(FakeResponse(), FakeResponse())
        transport = self.transport(opener)
        transport.get(DIRECTORY_URL)
        transport.get(DIRECTORY_URL)
        self.assertEqual(self.clock.sleeps, [0.5])

    def test_limiter_budget_exhaustion(self):
        clock = Clock()
        limiter = RateLimiter(interval=1, monotonic=clock.monotonic, sleep=clock.sleep)
        limiter.wait(101)
        with self.assertRaises(ProviderFailure) as ctx:
            limiter.wait(100.5)
        self.assertEqual(ctx.exception.status, Status.TIMEOUT)

    def test_bad_config(self):
        for kwargs in ({"user_agent": ""}, {"user_agent": "bad\r\nheader"}, {"allowed_hosts": set()},
                       {"timeout": float("inf")}, {"budget": 0}, {"max_attempts": 99}, {"max_bytes": 0}):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                self.transport(Opener(), **kwargs)


class DirectoryTests(unittest.TestCase):
    def parse(self, payload):
        return parse_directory(Response(DIRECTORY_URL, json.dumps(payload).encode(), NOW))

    def test_identity_exact_punctuation_and_multiple_classes(self):
        snapshot = parse_directory(Response(DIRECTORY_URL, BODY, NOW))
        self.assertEqual(snapshot.lookup(" aapl ").issuer.cik, "0000320193")
        self.assertEqual(snapshot.lookup("BRK-B").issuer.cik, snapshot.lookup("BRK-A").issuer.cik)
        self.assertIsNone(snapshot.lookup("BRK.B"))
        self.assertIsNone(snapshot.lookup("NOT_PRESENT"))
        self.assertEqual(snapshot.source_url, DIRECTORY_URL)

    def test_identity_mismatch_not_missing(self):
        snapshot = parse_directory(Response(DIRECTORY_URL, BODY, NOW))
        with self.assertRaises(ProviderFailure) as ctx:
            snapshot.lookup("AAPL", expected_cik="0000789019")
        self.assertEqual(ctx.exception.status, Status.SYMBOL_MISMATCH)

    def test_schema_column_reordering(self):
        snapshot = self.parse({"fields": ["ticker", "exchange", "name", "cik"],
                               "data": [["ABC", None, "Synthetic Company", 12]]})
        self.assertEqual(snapshot.lookup("ABC").issuer.cik, "0000000012")
        self.assertIsNone(snapshot.lookup("ABC").exchange_label)
        self.assertFalse(hasattr(snapshot.lookup("ABC"), "active"))

    def test_bad_schema_and_rows_fail_closed(self):
        fields = ["cik", "name", "ticker", "exchange"]
        payloads = [[], {}, {"fields": fields, "data": []},
                    {"fields": fields + ["cik"], "data": [[1, "x", "X", "NYSE", 1]]}]
        bad_rows = [[True, "x", "X", "NYSE"], [0, "x", "X", "NYSE"],
                    ["320193", "x", "X", "NYSE"], [1, "", "X", "NYSE"],
                    [1, "x", "", "NYSE"], [1, "x", "X", 12], [1, "x", "X"]]
        payloads.extend({"fields": fields, "data": [row]} for row in bad_rows)
        payloads.append({"fields": fields, "data": [[1, "x", "X", "NYSE"], [2, "y", "x", "NYSE"]]})
        for payload in payloads:
            with self.subTest(payload=payload), self.assertRaises(ProviderFailure) as ctx:
                self.parse(payload)
            self.assertEqual(ctx.exception.status, Status.INVALID_DATA)

    def test_strict_json_rejects_duplicates_nan_and_html(self):
        for body in (b'{"x":1,"x":2}', b'{"x":NaN}', b'<html>blocked</html>', b'\xff'):
            with self.subTest(body=body), self.assertRaises(ProviderFailure):
                strict_json(body)

    def test_transport_to_directory_integration(self):
        opener = Opener(FakeResponse())
        clock = Clock()
        transport = HttpTransport(user_agent="Synthetic contact@example.org", allowed_hosts={"www.sec.gov"},
                                  opener=opener, monotonic=clock.monotonic, sleep=clock.sleep, clock=lambda: NOW)
        snapshot = SecDirectory(transport).fetch()
        self.assertEqual(snapshot.lookup("AAPL").issuer.legal_name, "Apple Inc.")
        self.assertEqual(len(opener.calls), 1)

    def test_replay_recorded_official_response(self):
        root = Path(__file__).resolve().parents[1]
        body = (root / "tests/fixtures/sec-directory-recorded.json").read_bytes()
        evidence = json.loads((root / "docs/evidence/sec-directory-live.json").read_text())
        response = Response(DIRECTORY_URL, body, datetime.fromisoformat(evidence["retrieved_at"]))
        self.assertEqual(response.sha256, evidence["sha256"])
        snapshot = parse_directory(response)
        self.assertEqual(len(snapshot.entries), evidence["directory_entries"])
        for check in evidence["identity_checks"]:
            self.assertEqual(snapshot.lookup(check["ticker"]).issuer.cik, check["cik"])


class CliTests(unittest.TestCase):
    def test_status_never_claims_financial_acceptance(self):
        run = subprocess.run([sys.executable, "-m", "equity_research", "status"], capture_output=True, text=True, check=True)
        result = json.loads(run.stdout)
        self.assertEqual(result["implemented_identity_adapters"], ["SEC"])
        self.assertFalse(result["production_accepted"])
        self.assertEqual(result["real_companies_validated"], 0)
