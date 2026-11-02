import gzip
import json
import unittest
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path

from equity_research.sector_policy import assess_profile, calculate_with_sector_guard
from equity_research.transport import Response
from test_calculations import fact, CIK, START, END, NOW

ROOT = Path(__file__).resolve().parents[1]


def metadata(sic='3674', **changes):
    body = dict(cik=int(CIK), name='Synthetic issuer', tickers=['TEST'], sic=sic,
                entityType='operating', filings=dict(files=[], recent={key: [] for key in
                ('accessionNumber', 'form', 'filingDate', 'reportDate', 'primaryDocument', 'acceptanceDateTime')}))
    body.update(changes)
    return Response(f'https://data.sec.gov/submissions/CIK{CIK}.json', json.dumps(body).encode(), NOW)


class SectorPolicyTests(unittest.TestCase):
    def profile(self, response, **changes):
        args = dict(issuer_id=CIK, as_of=NOW)
        args.update(changes)
        return assess_profile(response, **args)

    def test_bank_codes_require_special_model(self):
        for code in ('6021', '6022', '6029', '6035', '6036'):
            self.assertEqual(self.profile(metadata(code))['profile'], 'banking_signal')

    def test_insurance_and_health_plan_signals(self):
        for code in ('6311', '6321', '6324', '6331', '6351', '6361', '6399'):
            self.assertEqual(self.profile(metadata(code))['profile'], 'insurance_signal')

    def test_reit_is_signal_not_legal_approval(self):
        got = self.profile(metadata('6798'))
        self.assertEqual(got['profile'], 'reit_signal')
        self.assertFalse(got['legal_type_approved'])

    def test_investment_sic_does_not_claim_bdc_or_fund(self):
        self.assertEqual(self.profile(metadata('6799'))['profile'], 'investment_vehicle_review')

    def test_other_financial_and_real_estate_codes_fail_closed(self):
        for code in ('6211', '6199', '6411', '6512', '6099'):
            self.assertEqual(self.profile(metadata(code))['profile'], 'finance_real_estate_review')

    def test_operating_and_name_do_not_override_financial_sic(self):
        self.assertEqual(self.profile(metadata('6021', name='Software Corporation'))['profile'], 'banking_signal')

    def test_other_industry_never_grants_generic_model(self):
        got = self.profile(metadata())
        self.assertEqual(got['profile'], 'other_industry_review')
        for flag in ('sector_model_supported', 'generic_cash_flow_eligible', 'investment_approved', 'scope_approved'):
            self.assertIs(got[flag], False)

    def test_unknown_codes_are_not_normalized_or_guessed(self):
        for code in (None, '', '0', '0000', '9999', ' 6021', '6021 ', 'bank'):
            got = self.profile(metadata(code))
            self.assertEqual(got['profile'], 'unknown')
            self.assertEqual(got['status'], 'unknown_sic')

    def test_missing_metadata_has_no_approval(self):
        self.assertEqual(self.profile(None)['status'], 'metadata_unavailable')

    def test_invalid_json_duplicate_keys_or_metadata_shape(self):
        for body in (b'{}', b'{"cik":320193,"cik":19617}', b'not json'):
            self.assertEqual(self.profile(replace(metadata(), body=body))['status'], 'invalid_metadata')

    def test_wrong_issuer_cannot_classify(self):
        got = self.profile(metadata('6021', cik=19617))
        self.assertEqual(got['status'], 'invalid_metadata')
        self.assertEqual(got['failure_status'], 'symbol_mismatch')

    def test_wrong_endpoint_never_persists_untrusted_url(self):
        got = self.profile(replace(metadata(), url='https://example.org/?key=secret'))
        self.assertEqual(got['status'], 'invalid_metadata')
        self.assertIsNone(got['evidence'])

    def test_future_and_stale_original_observations_rejected(self):
        self.assertEqual(self.profile(metadata(), as_of=NOW-timedelta(seconds=1))['status'], 'future_metadata')
        self.assertEqual(self.profile(metadata(), as_of=NOW+timedelta(hours=6, seconds=1))['status'], 'stale_metadata')
        self.assertEqual(self.profile(metadata(), as_of=NOW+timedelta(hours=6))['status'], 'metadata_signal_only')

    def test_original_hash_and_observation_retained(self):
        response = metadata()
        got = self.profile(response)
        self.assertEqual(got['evidence']['raw_sha256'], response.sha256)
        self.assertEqual(got['evidence']['retrieved_at'], NOW.isoformat())

    def test_invalid_cutoff_identity_or_ttl_raises(self):
        for changes in (dict(as_of=NOW.replace(tzinfo=None)), dict(issuer_id='320193'), dict(max_age=timedelta(0))):
            with self.assertRaises(ValueError):
                self.profile(metadata(), **changes)

    def test_arithmetic_separate_from_withheld_interpretation(self):
        values = {'operating_cash_flow': fact('operating_cash_flow', '100'), 'capital_expenditure': fact('capital_expenditure', '20')}
        for code, reason in [('6021', 'specialized_model_required'), ('6331', 'specialized_model_required'),
                             ('6798', 'specialized_model_required'), ('6799', 'specialized_model_required'),
                             ('3674', 'sector_model_validation_pending'), (None, 'profile_evidence_required')]:
            got = calculate_with_sector_guard('cash_after_ppe_payments', values, metadata_response=metadata(code),
                issuer_id=CIK, period_start=START, period_end=END, currency='USD', as_of=NOW)
            self.assertEqual(got['arithmetic']['value'], 80)
            self.assertIsNone(got['interpreted_value'])
            self.assertEqual(got['interpretation_status'], reason)
            self.assertFalse(got['generic_cash_flow_eligible'])

    def test_missing_arithmetic_never_filled_by_profile(self):
        got = calculate_with_sector_guard('cash_after_ppe_payments', {}, metadata_response=metadata(),
            issuer_id=CIK, period_start=START, period_end=END, currency='USD', as_of=NOW)
        self.assertEqual(got['arithmetic']['status'], 'pending_data')
        self.assertIsNone(got['arithmetic']['value'])

    def test_real_recorded_issuer_routes(self):
        cases = [('0000019617', 'banking_signal'), ('0000896159', 'insurance_signal'),
                 ('0000766704', 'reit_signal'), ('0000886982', 'finance_real_estate_review')]
        for cik, route in cases:
            body = gzip.decompress((ROOT/f'tests/fixtures/submissions/CIK{cik}.json.gz').read_bytes())
            response = Response(f'https://data.sec.gov/submissions/CIK{cik}.json', body, NOW)
            got = assess_profile(response, issuer_id=cik, as_of=NOW)
            self.assertEqual(got['profile'], route)
            self.assertFalse(got['investment_approved'])
