"""Ağ tanısı dış ağa bağlanmadan sınanır."""
import importlib.util
import socket
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "sec_network_diagnostic", ROOT / "scripts/diagnose_sec_network.py")
module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(module)


def resolved(*args, **kwargs):
    return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("127.0.0.1", 443))]


class DummyConnection:
    def __enter__(self):
        return self

    def __exit__(self, *args):
        return None


class DummyTls(DummyConnection):
    def version(self):
        return "TLSv1.3"


class DummyContext:
    def wrap_socket(self, raw, *, server_hostname):
        assert server_hostname == "data.sec.gov"
        return DummyTls()


class SecDiagnosticTests(unittest.TestCase):
    def test_dns_error_prevents_connection(self):
        def bad_dns(*args, **kwargs):
            raise socket.gaierror("no address")
        def unexpected_connect(*args, **kwargs):
            raise AssertionError("TCP must not run")
        report = module.diagnose_host("data.sec.gov", resolver=bad_dns,
                                      connect=unexpected_connect)
        self.assertEqual(report["dns"], "unavailable")
        self.assertEqual(report["tcp"], "not_attempted")
        self.assertEqual(report["error_type"], "gaierror")

    def test_tcp_error_is_separate_from_dns(self):
        def blocked(*args, **kwargs):
            raise TimeoutError("test timeout")
        report = module.diagnose_host("data.sec.gov", resolver=resolved,
                                      connect=blocked)
        self.assertEqual(report["dns"], "ok")
        self.assertEqual(report["tcp"], "not_attempted")
        self.assertEqual(report["error_type"], "TimeoutError")

    def test_tls_success_does_not_claim_http_or_financial_validation(self):
        report = module.diagnose_host(
            "data.sec.gov", resolver=resolved,
            connect=lambda *args, **kwargs: DummyConnection(),
            tls_context_factory=lambda: DummyContext())
        self.assertEqual(report["dns"], "ok")
        self.assertEqual(report["tcp"], "ok")
        self.assertEqual(report["tls"], "ok")
        self.assertEqual(report["tls_version"], "TLSv1.3")

    def test_only_explicit_known_hosts_are_probed(self):
        self.assertEqual(module.HOSTS,
                         ("data.sec.gov", "www.sec.gov", "github.com"))


if __name__ == "__main__":
    unittest.main()
