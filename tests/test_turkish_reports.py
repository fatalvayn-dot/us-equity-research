"""Turkish views preserve financial evidence and filter machine contracts."""
import copy
import gzip
import json
import unittest
from html.parser import HTMLParser
from pathlib import Path

from equity_research.assessment import CHECKS
from equity_research.fields import SPECS
from equity_research.financial_cohort import render_cohort_html, render_cohort_markdown
from equity_research.providers import Status
from equity_research.score_html import render_score_html
from equity_research.scoring import render_score_markdown
from equity_research.turkish import label

ROOT = Path(__file__).resolve().parents[1]


def recorded(name):
    return json.loads(gzip.decompress((ROOT / 'docs/evidence' / name / 'report.json.gz').read_bytes()))


class VisibleText(HTMLParser):
    def __init__(self):
        super().__init__(); self.parts = []; self.suppressed = 0
    def handle_starttag(self, tag, attrs):
        if tag in ('script', 'style'): self.suppressed += 1
    def handle_endtag(self, tag):
        if tag in ('script', 'style'): self.suppressed -= 1
    def handle_data(self, data):
        if not self.suppressed: self.parts.append(data)


class TurkishReportTests(unittest.TestCase):
    def test_financial_views_translate_diagnostics_preserving_evidence_and_filters(self):
        report = recorded('common-financial100'); before = copy.deepcopy(report)
        page = render_cohort_html(report); md = render_cohort_markdown(report)
        self.assertEqual(report, before)
        self.assertIn('lang="tr"', page)
        self.assertIn('<option value="critical_review_required">Kritik inceleme gerekiyor</option>', page)
        for c in report['companies']:
            gate = c['financial_assessment']['quantitative_gate']
            self.assertIn('data-gate="'+gate+'"', page)
        parser = VisibleText(); parser.feed(page); visible = ' '.join(parser.parts)
        for text in (visible, md):
            for token in ('Finansal inceleme', 'Faaliyetlerden nakit akışı', 'Kaynakta bulunamadı', 'Yapılandırılmadı'):
                self.assertIn(token, text)
            for token in ('review_required', 'unsupported_field', 'not_configured', 'Reported operating income'):
                self.assertNotIn(token, text)
        for c in report['companies']:
            for row in c['fields']:
                f = row['fact']
                if f:
                    self.assertIn(f['raw_sha256'], page)
                    self.assertIn(row['query']['accounting_definition'], md)
                    self.assertIn(str(f['value']), page)

    def test_score_view_translates_blockers_components_and_keeps_all_scores(self):
        report = recorded('current-score100'); before = copy.deepcopy(report)
        page = render_score_html(report); md = render_score_markdown(report)
        self.assertIn('Puanın hesaplanmama nedenleri', md)
        self.assertIn('Yarı iletkenler (v1)', md)
        self.assertEqual(report, before)
        parser = VisibleText(); parser.feed(page); visible = ' '.join(parser.parts)
        for token in ('Finansal sağlamlık', 'Araştırma modeli puanı hesaplandı', 'Toplam yükümlülükler', 'Kritik inceleme gerekiyor'):
            self.assertIn(token, visible)
        for token in ('scored_research_hypothesis', 'valuation_source_evidence_required', 'liabilities_to_assets', 'semiconductors_v1'):
            self.assertNotIn(token, visible)
        self.assertEqual(page.count('data-scored="true"'), 13)
        self.assertEqual(page.count('data-scored="false"'), 87)
        for c in report['companies']:
            if c['total_score'] is not None:
                self.assertIn(str(c['total_score'])+' / 100', page)
        self.assertIn(report['as_of'], page)

    def test_known_provider_field_and_check_labels_have_turkish_coverage(self):
        for value in [s.value for s in Status] + list(SPECS) + [r[3] for r in CHECKS]:
            self.assertNotEqual(label(value), value, value)

    def test_unrecognized_diagnostics_and_primary_evidence_are_never_invented(self):
        for value in ('new_unknown_failure', 'https://sec.gov/x?field=assets', 'us-gaap:Liabilities', '2026-11-03T05:36:21+00:00'):
            self.assertEqual(label(value), value)
        self.assertIn('Toplam yükümlülükler', label('financial_confirmation.liabilities'))
        self.assertIn('financial_confirmation.liabilities', label('financial_confirmation.liabilities'))
