import gzip
import json
import re
import unittest
from dataclasses import replace
from datetime import date, datetime, timedelta
from pathlib import Path

from equity_research.legal_evidence import registration_legal_evidence, annual_legal_evidence
from equity_research.providers import ProviderFailure
from equity_research.transport import Response

ROOT = Path(__file__).resolve().parents[1]
ROWS = json.loads((ROOT/'docs/evidence/registration-source-manifest.json').read_text())['observations']


def response(index=0):
    row = ROWS[index]
    return Response(row['source_url'], gzip.decompress((ROOT/row['fixture']).read_bytes()), datetime.fromisoformat(row['retrieved_at']))


def parse(r=None, index=0, **changes):
    row = ROWS[index]
    r = r or response(index)
    args = dict(cik=row['issuer_id'], disclosure_date=date.fromisoformat(row['disclosure_date']),
                document_type=row['document_type'], as_of=r.retrieved_at)
    args.update(changes)
    return registration_legal_evidence(r, **args)


def changed(old, new, index=0):
    r = response(index)
    assert old in r.body
    return replace(r, body=r.body.replace(old, new))


class RegistrationLegalTests(unittest.TestCase):
    def test_original_bdc_ballot_boxes(self):
        got = parse()['disclosures']
        self.assertIs(got['business_development_company']['value'], True)
        self.assertIs(got['registered_closed_end_fund']['value'], False)

    def test_original_fund_fixed_transforms(self):
        got = parse(index=1)['disclosures']
        self.assertIs(got['business_development_company']['value'], False)
        self.assertIs(got['registered_closed_end_fund']['value'], True)

    def test_reported_false_does_not_approve_common_share_scope(self):
        got = parse(index=1)
        self.assertFalse(got['scope_approved']); self.assertFalse(got['legal_type_approved'])
        self.assertFalse(got['investment_approved']); self.assertFalse(got['fiscal_period_inferred'])

    def test_original_hash_timestamp_and_date_retained(self):
        for i, row in enumerate(ROWS):
            got = parse(index=i)
            self.assertEqual(got['raw_sha256'], row['raw_sha256'])
            self.assertEqual(got['retrieved_at'], row['retrieved_at'])
            self.assertEqual(got['disclosure_date'], row['disclosure_date'])

    def test_registration_never_enters_annual_context_path(self):
        with self.assertRaises(ProviderFailure):
            annual_legal_evidence(response(), cik=ROWS[0]['issuer_id'], report_end=date(2026,8,21), document_type='10-K', as_of=response().retrieved_at)

    def test_wrong_date_type_or_issuer_never_matches(self):
        for changes in (dict(disclosure_date=date(2026,8,22)), dict(document_type='N-2'), dict(cik='0000320193')):
            with self.assertRaises(ProviderFailure): parse(**changes)

    def test_unsupported_form_requires_explicit_registration_type(self):
        with self.assertRaises(ValueError): parse(document_type='10-K')

    def test_future_cutoff_and_future_disclosure_rejected(self):
        with self.assertRaises(ProviderFailure): parse(as_of=response().retrieved_at-timedelta(seconds=1))
        with self.assertRaises(ProviderFailure): parse(disclosure_date=date(2099,1,1))

    def test_endpoint_query_or_wrong_host_rejected(self):
        for url in (response().url+'?token=secret', response().url.replace('www.sec.gov','evil.example')):
            with self.assertRaises(ProviderFailure): parse(replace(response(),url=url))

    def test_annual_length_context_not_reused_as_registration_date(self):
        r = changed(b'<xbrli:startDate>2026-08-21', b'<xbrli:startDate>2026-01-01')
        with self.assertRaises(ProviderFailure): parse(r)

    def test_dimension_context_never_matches(self):
        r = changed(b'</xbrli:entity>', b'<xbrli:segment><xbrldi:explicitMember>ClassA</xbrldi:explicitMember></xbrli:segment></xbrli:entity>')
        with self.assertRaises(ProviderFailure): parse(r)

    def test_forged_transform_namespace_is_unknown(self):
        r = changed(b'http://www.sec.gov/inlineXBRL/transformation/2015-08-31', b'http://evil.example/transform')
        got = parse(r)['disclosures']['business_development_company']
        self.assertEqual(got['status'],'unsupported_encoding_or_value'); self.assertIsNone(got['value'])

    def test_unknown_ballot_character_never_guessed(self):
        r = changed(b'&#9746;', b'Y')
        self.assertIsNone(parse(r)['disclosures']['business_development_company']['value'])

    def test_conflicting_duplicate_flags_have_no_value(self):
        f = b'<ix:nonNumeric name="cef:BusinessDevelopmentCompanyFlag" contextRef="c0">false</ix:nonNumeric>'
        r = changed(b'</body>', f+b'</body>')
        got = parse(r)['disclosures']['business_development_company']
        self.assertEqual(got['status'],'conflicting'); self.assertIsNone(got['value'])

    def test_missing_disclosure_not_inferred_from_other_flag(self):
        r = response(); b,n = re.subn(rb'<ix:nonNumeric[^>]*name="cef:BusinessDevelopmentCompanyFlag"[^>]*>.*?</ix:nonNumeric>',b'',r.body,flags=re.S)
        self.assertEqual(n,1)
        self.assertEqual(parse(replace(r,body=b))['disclosures']['business_development_company']['status'],'unknown')

    def test_form_and_cik_anchors_cannot_be_cross_joined(self):
        r = changed(b'name="dei:DocumentType"', b'contextRef="other" name="dei:DocumentType"')
        with self.assertRaises(ProviderFailure): parse(r)

    def test_fixed_transform_uses_verified_constant_semantics(self):
        r = changed(b'format="ixt:fixed-false"', b'format="ixt:fixed-true"',index=1)
        self.assertIs(parse(r,index=1)['disclosures']['business_development_company']['value'],True)

    def test_transform_prefix_rebinding_and_truncated_facts_fail_closed(self):
        r = changed(b'name="cef:BusinessDevelopmentCompanyFlag"', b'xmlns:ixt-sec="http://evil.example" name="cef:BusinessDevelopmentCompanyFlag"')
        self.assertIsNone(parse(r)['disclosures']['business_development_company']['value'])
        r = changed(b'</body>', b'<ix:nonNumeric name="cef:BusinessDevelopmentCompanyFlag" contextRef="c0">true</body>')
        with self.assertRaises(ProviderFailure): parse(r)
