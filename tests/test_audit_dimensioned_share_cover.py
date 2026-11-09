import hashlib
import unittest
from datetime import date

from scripts.audit_dimensioned_share_cover import audit
from test_valuation import CIK, filing


def body_for_classes():
    body = filing(title="Class A Common Stock").body.decode()
    body = body.replace("<html ", '<html xmlns:us-gaap="http://fasb.org/us-gaap/2026" '
                        'xmlns:xbrldi="http://xbrl.org/2006/xbrldi" ', 1)
    start = body.index('<xbrli:context id="shares">')
    end = body.index("</xbrli:context>", start) + len("</xbrli:context>")
    common = body[start:end]
    def context(member):
        return common.replace('id="shares"', f'id="shares-{member}"').replace(
            "</xbrli:entity>", '<xbrli:segment><xbrldi:explicitMember '
            'dimension="us-gaap:StatementClassOfStockAxis">'
            f'us-gaap:CommonClass{member}Member</xbrldi:explicitMember>'
            "</xbrli:segment></xbrli:entity>")
    body = body[:start] + context("A") + context("B") + body[end:]
    body = body.replace('contextRef="shares"', 'contextRef="shares-A"')
    return body.replace("</html>", '<ix:nonFraction name="dei:EntityCommonStockSharesOutstanding" '
                        'contextRef="shares-B" unitRef="u" decimals="0">30</ix:nonFraction></html>').encode()


class DimensionedShareCoverAuditTests(unittest.TestCase):
    def run_audit(self, body, sha=None, **options):
        return audit(body, cik=CIK, symbol="AAPL", report_end=date(2026, 9, 30),
                     document_type="10-Q", sha256=sha or hashlib.sha256(body).hexdigest(),
                     **options)

    def test_balance_sheet_reads_only_exact_instant_and_explicit_zero(self):
        body = (body_for_classes().replace(b"2026-10-20", b"2026-09-30")
                .replace(b"dei:EntityCommonStockSharesOutstanding", b"us-gaap:CommonStockSharesOutstanding")
                .replace(b"<html ", b'<html xmlns:ixt="http://www.xbrl.org/inlineXBRL/transformation/2020-02-12" ')
                .replace(b'>30</ix:nonFraction>', b' format="ixt:fixed-zero">no</ix:nonFraction>'))
        result = self.run_audit(body, balance_sheet=True)
        self.assertEqual(result["class_count_concept"], "us-gaap:CommonStockSharesOutstanding")
        self.assertEqual([r["shares"] for r in result["class_counts"]], [100, 0])
        self.assertFalse(result["valuation_eligible"])
        for changed in (body.replace(b'2026-09-30</xbrli:instant>', b'2026-09-29</xbrli:instant>'),
                        body.replace(b'format="ixt:fixed-zero">no', b'format="ixt:fixed-zero">'),
                        body.replace(b'/transformation/2020-02-12', b'/transformation/2099-01-01')):
            with self.subTest(changed=changed[-180:]), self.assertRaises(ValueError):
                self.run_audit(changed, balance_sheet=True)

    def test_reports_exact_classes_without_valuation_total(self):
        result = self.run_audit(body_for_classes())
        self.assertEqual(result["listed_class_member"], "us-gaap:CommonClassAMember")
        self.assertEqual([r["shares"] for r in result["class_counts"]], [100, 30])
        self.assertFalse(result["valuation_eligible"])
        self.assertFalse(result["scope_approved"])

    def test_tamper_and_unsupported_class_context_rejected(self):
        body = body_for_classes()
        with self.assertRaisesRegex(ValueError, "SHA-256"):
            self.run_audit(body, "0" * 64)
        with self.assertRaisesRegex(ValueError, "hisse sınıfı bağlamı"):
            self.run_audit(body.replace(b"StatementClassOfStockAxis", b"OtherAxis"))
        with self.assertRaisesRegex(ValueError, "Tekrarlı"):
            self.run_audit(body.replace(b"CommonClassBMember", b"CommonClassAMember"))

    def test_missing_listed_class_count_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "sayımı tekil"):
            self.run_audit(body_for_classes().replace(b"CommonClassAMember", b"CommonClassCMember"))
