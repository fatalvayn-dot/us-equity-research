import unittest
from datetime import date
from decimal import Decimal

from equity_research.filingcheck import filing_assets
from equity_research.providers import ProviderFailure


def html(number='359,241',attrs='',context=''):
    return f'''<html><xbrli:context id="c"><xbrli:entity><xbrli:identifier scheme="http://www.sec.gov/CIK">0000320193</xbrli:identifier>{context}</xbrli:entity><xbrli:period><xbrli:instant>2025-09-27</xbrli:instant></xbrli:period></xbrli:context><xbrli:unit id="u"><xbrli:measure>iso4217:USD</xbrli:measure></xbrli:unit><ix:nonFraction name="us-gaap:Assets" contextRef="c" unitRef="u" scale="6" {attrs}>{number}</ix:nonFraction></html>'''.encode()


class FilingTests(unittest.TestCase):
    def test_scaled_inline_fact_with_declared_currency(self):
        self.assertEqual(filing_assets(html(),cik='0000320193',period_end=date(2025,9,27)),Decimal('359241000000'))

    def test_wrong_identity_date_currency_and_dimensions_rejected(self):
        for body,cik,end in ((html(),'0000789019',date(2025,9,27)),(html(),'0000320193',date(2024,9,27)),
                             (html().replace(b'iso4217:USD',b'iso4217:EUR'),'0000320193',date(2025,9,27)),
                             (html(context='<xbrli:segment></xbrli:segment>'),'0000320193',date(2025,9,27))):
            with self.subTest(cik=cik,end=end),self.assertRaises(ProviderFailure):
                filing_assets(body,cik=cik,period_end=end)

    def test_unsupported_transform_nil_and_continuation_rejected(self):
        for attrs in ('format="ixt:num-comma-decimal"','xsi:nil="true"','continuedAt="other"'):
            with self.subTest(attrs=attrs),self.assertRaises(ProviderFailure):
                filing_assets(html(attrs=attrs),cik='0000320193',period_end=date(2025,9,27))

    def test_conflicting_values_fail_closed(self):
        with self.assertRaises(ProviderFailure):
            filing_assets(html()+html('100'),cik='0000320193',period_end=date(2025,9,27))

    def test_malformed_number_not_zero(self):
        for number in ('—','NaN','not-a-number'):
            with self.subTest(number=number),self.assertRaises(ProviderFailure):
                filing_assets(html(number),cik='0000320193',period_end=date(2025,9,27))
