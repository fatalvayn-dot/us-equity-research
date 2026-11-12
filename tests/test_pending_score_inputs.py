import gzip
import sys
import unittest
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

from equity_research.transport import Response

ROOT = Path(__file__).resolve().parents[1]
with patch.object(sys, 'path', [str(ROOT / 'scripts'), *sys.path]):
    from verify_pending_score_inputs import audit_original_gaps, selected_operating_symbols, missing_companyfacts_result, audit_liability_equation
from test_filingcheck import equation_html

CIK = '0001045810'
CUTOFF = datetime(2026, 11, 8, tzinfo=timezone.utc)
URL = 'https://www.sec.gov/Archives/edgar/data/1045810/000104581026000021/nvda-20260125.htm'
FIXTURE = ROOT / 'tests/fixtures/annual/0001045810-0001045810-26-000021.html.gz'


class OriginalScoreGapTests(unittest.TestCase):
    def diagnose(self, original, **overrides):
        inputs = dict(cik=CIK, start=date(2025, 1, 27), end=date(2026, 1, 25),
                      missing_fields=['revenue', 'capital_expenditure'], cutoff=CUTOFF)
        return audit_original_gaps(original, **(inputs | overrides))

    def test_all_modeled_operating_issuers_excludes_bank_insurer_and_reit(self):
        def row(symbol, sic, entity='operating'):
            return dict(symbol=symbol, issuer_id=f'{sum(ord(c) for c in symbol):010d}',
                        snapshot=dict(sic_label=sic, entity_type_label=entity))
        metadata = dict(companies=[
            row('TECH', '3674'), row('PHARMA', '2834'),
            row('BANK', '6021'), row('INSURE', '6331'),
            row('REIT', '6798'), row('FUND', '3674', 'investment'),
            row('UNKNOWN', None),
        ])
        self.assertEqual(selected_operating_symbols(metadata), ['TECH', 'PHARMA'])
        self.assertEqual(len(metadata['companies']), 7)

    def test_all_modeled_refuses_ambiguous_metadata_identity(self):
        safe = dict(symbol='ABC', issuer_id='0000000001',
                    snapshot=dict(sic_label='3674', entity_type_label='operating'))
        with self.assertRaises(ValueError):
            selected_operating_symbols(dict(companies=[safe, dict(safe)]))
        with self.assertRaises(ValueError):
            selected_operating_symbols(dict(companies=[dict(safe, issuer_id='bad')]))
        self.assertEqual(selected_operating_symbols(dict(companies=[
            dict(safe, snapshot=None)])), [])

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

    def test_missing_sec_companyfacts_does_not_stop_other_originals_or_invent_values(self):
        company=dict(symbol='GEV', issuer_id='0001996810',
                     period_start='2025-01-01',
                     fields=[dict(query=dict(field='assets'), fact=dict(value='100'))])
        annual=dict(accession='0001996810-26-000001', report_end='2025-12-31')
        row=missing_companyfacts_result(company, annual, None, CUTOFF)
        self.assertEqual(row['source_status'], 'sec_companyfacts_cache_missing')
        self.assertEqual(row['confirmed_fields'], 0)
        self.assertTrue(all(c['status']=='source_cache_missing' for c in row['checks']))
        self.assertEqual(row['original_score_input_gaps']['status'],
                         'original_unavailable_at_cutoff')
        self.assertEqual(row['original_score_input_gaps']['fields'],
                         ['revenue', 'capital_expenditure'])

    def test_missing_liability_equation_proves_only_original_scope_not_score(self):
        original=Response('https://www.sec.gov/Archives/edgar/data/320193/original.htm',
                          equation_html(), CUTOFF)
        got=audit_liability_equation(original, cik='0000320193',
                                    end=date(2025,9,27),missing=True,cutoff=CUTOFF)
        self.assertEqual(got['status'], 'original_balance_equation_proven')
        self.assertEqual(got['proof']['value'], '40')
        self.assertEqual(got['source']['sha256'], original.sha256)
        self.assertFalse(got['automatic_substitution'])
        self.assertFalse(got['score_generated'])
        self.assertIsNone(audit_liability_equation(original,cik='0000320193',
                         end=date(2025,9,27),missing=False,cutoff=CUTOFF))

    def test_missing_liability_equation_rejects_wrong_scope_and_stale_cutoff(self):
        source=Response('https://www.sec.gov/Archives/edgar/data/320193/original.htm',
                        equation_html(),CUTOFF)
        wrong=audit_liability_equation(source,cik='0000789019',
                                      end=date(2025,9,27),missing=True,cutoff=CUTOFF)
        self.assertEqual(wrong['status'],'equation_not_proven')
        late=audit_liability_equation(source,cik='0000320193',
                                     end=date(2025,9,27),missing=True,
                                     cutoff=CUTOFF-timedelta(minutes=1))
        self.assertEqual(late['status'],'original_unavailable_at_cutoff')

    def test_cutoff_and_unknown_annual_period_prevent_disclosure(self):
        late = Response(URL, b'body', CUTOFF + timedelta(seconds=1))
        self.assertEqual(self.diagnose(late)['status'], 'original_unavailable_at_cutoff')
        original = Response(URL, b'body', CUTOFF)
        self.assertEqual(self.diagnose(original, start=None)['status'], 'annual_period_unavailable')
        self.assertEqual(self.diagnose(original)['status'], 'original_diagnostic_unavailable')
        self.assertIsNone(self.diagnose(original, missing_fields=['assets']))
