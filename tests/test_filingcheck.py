import unittest
from datetime import date
from decimal import Decimal

from equity_research.filingcheck import filing_assets,filing_derived_liabilities
from equity_research.providers import ProviderFailure


def html(number='359,241',attrs='',context=''):
    return f'''<html><xbrli:context id="c"><xbrli:entity><xbrli:identifier scheme="http://www.sec.gov/CIK">0000320193</xbrli:identifier>{context}</xbrli:entity><xbrli:period><xbrli:instant>2025-09-27</xbrli:instant></xbrli:period></xbrli:context><xbrli:unit id="u"><xbrli:measure>iso4217:USD</xbrli:measure></xbrli:unit><ix:nonFraction name="us-gaap:Assets" contextRef="c" unitRef="u" scale="6" {attrs}>{number}</ix:nonFraction></html>'''.encode()


def equation_html(*,assets='100',combined='100',equity='60',total_equity=None,
                  minority=None,literal=None,temporary=None,extra=''):
    values={'Assets':assets,'LiabilitiesAndStockholdersEquity':combined,'StockholdersEquity':equity}
    optional={'StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest':total_equity,
              'MinorityInterest':minority,'Liabilities':literal,'TemporaryEquityCarryingAmount':temporary}
    values.update({k:v for k,v in optional.items() if v is not None})
    facts=''.join(f'<ix:nonFraction name="us-gaap:{name}" contextRef="c" unitRef="u">{value}</ix:nonFraction>'
                  for name,value in values.items())
    return f'''<html xmlns:ixt="http://www.xbrl.org/inlineXBRL/transformation/2020-02-12" xmlns:us-gaap="http://fasb.org/us-gaap/2025" xmlns:iso4217="http://www.xbrl.org/2003/iso4217"><xbrli:context id="c"><xbrli:entity><xbrli:identifier scheme="http://www.sec.gov/CIK">0000320193</xbrli:identifier></xbrli:entity><xbrli:period><xbrli:instant>2025-09-27</xbrli:instant></xbrli:period></xbrli:context><xbrli:unit id="u"><xbrli:measure>iso4217:USD</xbrli:measure></xbrli:unit>{facts}{extra}</html>'''.encode()


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

    def test_liabilities_equation_requires_exact_original_totals_and_equity(self):
        proof=filing_derived_liabilities(equation_html(),cik='0000320193',period_end=date(2025,9,27))
        self.assertEqual(proof['value'],'40');self.assertEqual(proof['currency'],'USD')
        self.assertEqual(proof['literal_liabilities_status'],'concept_not_disclosed')
        self.assertFalse(proof['automatic_substitution']);self.assertFalse(proof['scope_approved'])

    def test_liabilities_equation_reconciles_total_equity_and_minority_interest(self):
        proof=filing_derived_liabilities(equation_html(equity='60',minority='15',total_equity='75'),
            cik='0000320193',period_end=date(2025,9,27))
        self.assertEqual(proof['value'],'25')
        self.assertEqual([row['value'] for row in proof['operands']],['100','75','60','15'])

    def test_liabilities_equation_rejects_scope_or_arithmetic_ambiguity(self):
        cases=(equation_html(combined='101'),equation_html(equity='60',total_equity='75'),
               equation_html(temporary='1'),equation_html(literal='40'),
               equation_html(equity='110'))
        for body in cases:
            with self.subTest(body=body),self.assertRaises(ProviderFailure):
                filing_derived_liabilities(body,cik='0000320193',period_end=date(2025,9,27))
