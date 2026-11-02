import unittest
from pathlib import Path
from xml.etree import ElementTree as ET
from dataclasses import replace
from datetime import datetime, timedelta, timezone

from equity_research.legal_evidence import annual_legal_evidence, INVESTMENT_TYPES
from equity_research.providers import ProviderFailure
from equity_research.transport import Response
from test_annual_period import document, CIK, END

NOW = datetime(2026, 11, 2, tzinfo=timezone.utc)
URL = f'https://www.sec.gov/Archives/edgar/data/{int(CIK)}/000032019326000079/aapl-20260926.htm'


def body(facts=''):
    b = document().replace(b'<html ', b'<html xmlns:ix="http://www.xbrl.org/2013/inlineXBRL" xmlns:xbrli="http://www.xbrl.org/2003/instance" xmlns:cef="http://xbrl.sec.gov/cef/2026" ')
    return b.replace(b'</html>', facts.encode() + b'</html>')


def flag(text='true', name='cef:BusinessDevelopmentCompanyFlag', context='d', attrs=''):
    return f'<ix:nonNumeric name="{name}" contextRef="{context}" {attrs}>{text}</ix:nonNumeric>'


def parse(b, **changes):
    args = dict(cik=CIK, report_end=END, document_type='10-K', as_of=NOW)
    args.update(changes)
    return annual_legal_evidence(Response(URL, b, NOW), **args)


class LegalEvidenceTests(unittest.TestCase):
    def test_contract_matches_recorded_official_taxonomy(self):
        root = Path(__file__).resolve().parents[1]/'tests/fixtures/taxonomy'
        ns = {'xs': 'http://www.w3.org/2001/XMLSchema'}
        dei = ET.parse(root/'dei-2026.xsd')
        values = {e.attrib['value'] for e in dei.findall('.//xs:complexType[@name="invCompanyType"]//xs:enumeration', ns)}
        self.assertEqual(values, INVESTMENT_TYPES)
        cef = ET.parse(root/'cef-2026.xsd')
        for name in ('BusinessDevelopmentCompanyFlag', 'RegisteredClosedEndFundFlag'):
            e = cef.find(f'.//xs:element[@name="{name}"]', ns)
            self.assertEqual(e.attrib['type'], 'xbrli:booleanItemType')
            self.assertEqual(e.attrib['{http://www.xbrl.org/2003/instance}periodType'], 'duration')

    def disclosure(self, b, field='business_development_company'):
        return parse(b)['disclosures'][field]

    def test_explicit_true_and_false_flags_remain_reported_disclosures(self):
        for text, expected in [('true', True), ('1', True), ('false', False), ('0', False)]:
            got = self.disclosure(body(flag(text)))
            self.assertEqual(got['status'], 'reported')
            self.assertIs(got['value'], expected)

    def test_absence_never_means_false(self):
        got = self.disclosure(body())
        self.assertEqual(got['status'], 'unknown')
        self.assertIsNone(got['value'])

    def test_nil_remains_unknown(self):
        self.assertIsNone(self.disclosure(body(flag(attrs='xsi:nil="true"')))['value'])

    def test_conflicting_duplicates_are_not_selected(self):
        got = self.disclosure(body(flag('true') + flag('false')))
        self.assertEqual(got['status'], 'conflicting')
        self.assertIsNone(got['value'])

    def test_equal_duplicates_preserve_both_context_evidence_rows(self):
        got = self.disclosure(body(flag() + flag()))
        self.assertIs(got['value'], True)
        self.assertEqual(len(got['evidence']), 2)

    def test_unknown_transform_or_boolean_text_not_guessed(self):
        for f in (flag('Yes'), flag('true', attrs='format="ixt:fixed-true"'), flag('true', attrs='xsi:nil="unknown"')):
            got = self.disclosure(body(f))
            self.assertEqual(got['status'], 'unsupported_encoding_or_value')
            self.assertIsNone(got['value'])

    def test_registered_closed_end_flag_not_bdc(self):
        got = parse(body(flag(name='cef:RegisteredClosedEndFundFlag')))
        self.assertIs(got['disclosures']['registered_closed_end_fund']['value'], True)
        self.assertIsNone(got['disclosures']['business_development_company']['value'])

    def test_exact_investment_type_token_is_not_renamed(self):
        for text in ('N-2', 'N-5', 'S-1 or S-3'):
            got = self.disclosure(body(flag(text, 'dei:EntityInvCompanyType')), 'investment_company_type')
            self.assertEqual(got['value'], text)
        self.assertIsNone(self.disclosure(body(flag('S-3', 'dei:EntityInvCompanyType')), 'investment_company_type')['value'])

    def test_obsolete_or_lookalike_concept_is_not_an_alias(self):
        got = self.disclosure(body(flag('N-2', 'dei:EntityInvestmentCompanyType')), 'investment_company_type')
        self.assertIsNone(got['value'])

    def test_separate_or_security_dimension_context_cannot_win(self):
        self.assertIsNone(self.disclosure(body(flag(context='other')))['value'])
        context = document(dimension='<xbrli:segment><xbrldi:explicitMember>ClassA</xbrldi:explicitMember></xbrli:segment>').split(b'>', 1)[1].split(b'<ix:nonNumeric', 1)[0]
        context = context.replace(b'id="d"', b'id="other"')
        b = body(flag(context='other')).replace(b'</html>', context+b'</html>')
        self.assertIsNone(self.disclosure(b)['value'])

    def test_wrong_namespace_or_rebinding_has_no_value(self):
        for b in (body(flag()).replace(b'http://xbrl.sec.gov/cef/2026', b'http://example.org/cef/2026'),
                  body(flag(attrs='xmlns:cef="http://example.org/cef/2026"'))):
            self.assertIsNone(self.disclosure(b)['value'])

    def test_fake_inline_element_cannot_be_a_disclosure(self):
        b = body(flag().replace('ix:nonNumeric', 'evil:nonNumeric'))
        self.assertIsNone(self.disclosure(b)['value'])

    def test_invalid_inline_or_context_namespace_rejected(self):
        for b in (body().replace(b'http://www.xbrl.org/2013/inlineXBRL', b'http://evil/inlineXBRL'),
                  body().replace(b'xbrli:identifier', b'evil:identifier')):
            with self.assertRaises(ProviderFailure): parse(b)

    def test_truncated_continued_or_excluded_facts_fail_closed(self):
        for b in (body(flag(attrs='continuedAt="other"')), body(flag('<ix:exclude>true</ix:exclude>')),
                  body().replace(b'</html>', b'<ix:nonNumeric name="cef:BusinessDevelopmentCompanyFlag" contextRef="d">true')):
            with self.assertRaises(ProviderFailure): parse(b)

    def test_issuer_period_and_form_are_bound_to_annual_context(self):
        for changes in (dict(cik='0000789019'), dict(document_type='20-F')):
            with self.assertRaises(ProviderFailure): parse(body(flag()), **changes)

    def test_future_retrieval_or_wrong_issuer_url_rejected(self):
        with self.assertRaises(ProviderFailure): parse(body(), as_of=NOW-timedelta(seconds=1))
        with self.assertRaises(ProviderFailure):
            annual_legal_evidence(Response(URL+'?key=secret', body(), NOW), cik=CIK, report_end=END, document_type='10-K', as_of=NOW)

    def test_provenance_and_no_legal_or_scope_approval(self):
        b = body(flag()); got = parse(b)
        self.assertEqual(got['raw_sha256'], Response(URL, b, NOW).sha256)
        self.assertEqual(got['retrieved_at'], NOW.isoformat())
        self.assertFalse(got['legal_type_approved']); self.assertFalse(got['scope_approved'])
        self.assertIsNone(got['disclosures']['reit']['value'])
