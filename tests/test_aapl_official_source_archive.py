import json
import tempfile
import unittest
from pathlib import Path
from scripts.aapl_official_source_archive import archive, verify_bytes, OFFICIAL


def sec_body():
    return json.dumps({
        "cik": 320193, "tickers": ["AAPL"], "name": "Apple Inc.",
        "entityType": "operating", "sic": "3571",
    }).encode()


def pdf_body():
    return b"%PDF-1.6\\n" + b"x" * 40


class SourceArchiveTests(unittest.TestCase):
    def test_original_bytes_sha_and_both_sources(self):
        sources = {
            OFFICIAL["sec_submissions"][0]: sec_body(),
            OFFICIAL["sp_shariah_methodology"][0]: pdf_body(),
        }
        def fake(url):
            return sources[url], url
        with tempfile.TemporaryDirectory() as root:
            result = archive(root, "Research Team research@example.org", transport=fake)
            self.assertTrue(result["all_original_bytes_archived"])
            self.assertEqual(len(result["sources"]), 2)
            self.assertTrue(all(len(x["raw_sha256"]) == 64 for x in result["sources"]))
            self.assertTrue((Path(root) / "sec_submissions.json").is_file())
            self.assertTrue((Path(root) / "sp_shariah_methodology.pdf").is_file())
            self.assertFalse(result["issuer_financial_ratios_independently_verified"])
            self.assertFalse(result["investment_approved"])

    def test_cik_identity_mismatch_rejected(self):
        wrong = json.dumps({"cik": 789019, "tickers": ["AAPL"]}).encode()
        with self.assertRaisesRegex(ValueError, "CIK identity mismatch"):
            verify_bytes("sec_submissions", wrong + b" " * 32)

    def test_refuse_redirect_or_untrusted_url(self):
        with tempfile.TemporaryDirectory() as root:
            result = archive(root, "Research Team research@example.org",
                             transport=lambda url: (sec_body(), "https://evil.test/file"))
            self.assertFalse(result["all_original_bytes_archived"])
            self.assertEqual([s["status"] for s in result["sources"]],
                             ["unavailable", "unavailable"])
            self.assertFalse(result["investment_approved"])

    def test_untrusted_pdf_and_missing_header_fail_closed(self):
        with self.assertRaises(ValueError):
            verify_bytes("other_name", pdf_body())
        with self.assertRaisesRegex(ValueError, "PDF header"):
            verify_bytes("sp_shariah_methodology", b"not a pdf but long enough" + b"X" * 30)

    def test_failed_transport_does_not_crash_or_claim_approval(self):
        with tempfile.TemporaryDirectory() as root:
            result = archive(root, "Research Team research@example.org",
                             transport=lambda url: (_ for _ in ()).throw(OSError("fail")))
            self.assertEqual(result["participation_status"], "bilinmiyor")
            self.assertFalse(result["all_original_bytes_archived"])
            self.assertFalse(result["eligible_for_trade"])


if __name__ == "__main__":
    unittest.main()
