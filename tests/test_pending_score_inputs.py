import gzip
import sys
import unittest
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

from equity_research.transport import Response

ROOT = Path(__file__).resolve().parents[1]
with patch.object(sys, 'path', [str(ROOT / 'scripts'), *sys.path]):
    from verify_pending_score_inputs import audit_original_gaps

CIK = '0001045810'
CUTOFF = datetime(2026, 11, 8, tzinfo=timezone.utc)
URL = 'https://www.sec.gov/Archives/edgar/data/1045810/000104581026000021/nvda-20260125.htm'
FIXTURE = ROOT / 'tests/fixtures/annual/0001045810-0001045810-26-000021.html.gz'


class OriginalScoreGapTests(unittest.TestCase):
    def diagnose(self, original, **overrides):
        inputs = dict(cik=CIK, start=date(2025, 1, 27), end=date(2026, 1, 25),
                      missing_fields=['revenue', 'capital_expenditure'], cutoff=CUTOFF)
        return audit_original_gaps(original, **(inputs | overrides))

    def test_original_nvda_filing_keeps_both_accounting_scopes_separate(self):
        original = Response(URL, gzip.decompress(FIXTURE.read_bytes()), CUTOFF)
        result = self.diagnose(original)
        self.assertEqual(result['source']['sha256'], original.sha256)
        self.assertFalse(result['automatic_substitution'])
        revenue, capex = result['fields']
        for row, required, related, value in [
            (revenue, 'RevenueFromContractWithCustomerExcludingAssessedTax', 'Revenues', '215938000000'),
            (capex, 'PaymentsToAcquirePropertyPlantAndEquipment', 'PaymentsToAcquireProductiveAssets', '6042000000'),
        ]:
            self.assertEqual(row['required']['concept'], 'us-gaap:' + required)
            self.assertEqual(row['required']['status'], 'concept_not_disclosed')
            self.assertIsNone(row['required']['value'])
            self.assertEqual(row['related']['concept'], 'us-gaap:' + related)
            self.assertEqual(row['related']['value'], value)

    def test_cutoff_and_unknown_annual_period_prevent_disclosure(self):
        late = Response(URL, b'body', CUTOFF + timedelta(seconds=1))
        self.assertEqual(self.diagnose(late)['status'], 'original_unavailable_at_cutoff')
        original = Response(URL, b'body', CUTOFF)
        self.assertEqual(self.diagnose(original, start=None)['status'], 'annual_period_unavailable')
        self.assertEqual(self.diagnose(original)['status'], 'original_diagnostic_unavailable')
        self.assertIsNone(self.diagnose(original, missing_fields=['assets']))
