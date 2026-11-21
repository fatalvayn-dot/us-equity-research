"""Recorded five-company SEC balance-equation proof; not live acceptance."""
import json
import unittest
from datetime import date
from decimal import Decimal
from pathlib import Path

from equity_research.evidence_bundle import read_bundle
from equity_research.filingcheck import filing_derived_liabilities

ROOT=Path(__file__).resolve().parents[1]


class RecordedLiabilityEquationTests(unittest.TestCase):
    def test_five_selected_liabilities_reconcile_from_exact_original_filings(self):
        report=json.loads((ROOT/'docs/evidence/liability-equation5/report.json').read_text())
        responses={response.url:response for response in read_bundle(ROOT/'tests/fixtures/liability-equation5-sources')}
        self.assertEqual(report['summary'],dict(candidates=5,matched=5,rejected=0))
        self.assertEqual(len(responses),5);self.assertEqual(report['new_http_requests'],0)
        self.assertFalse(report['automatic_substitution']);self.assertFalse(report['mvp_accepted'])
        for company in report['companies']:
            expected=company['confirmation'];response=responses[expected['source_url']]
            actual=filing_derived_liabilities(response.body,cik=company['issuer_id'],
                period_end=date.fromisoformat(company['selected']['period_end']))
            self.assertEqual(actual,{k:v for k,v in expected.items() if k not in ('source_url','retrieved_at')})
            self.assertEqual(Decimal(actual['value']),Decimal(company['selected']['value']))
        intel=next(c for c in report['companies'] if c['symbol']=='INTC')['confirmation']
        self.assertEqual(intel['operands'][1]['concept'],
            'us-gaap:StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest')
        self.assertEqual(intel['operands'][2]['value'],'114281000000')
        self.assertEqual(intel['operands'][3]['value'],'12079000000')
