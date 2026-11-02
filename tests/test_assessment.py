import copy
import gzip
import json
import unittest
import subprocess
import sys
import tempfile
import os
import hashlib
from dataclasses import replace
from datetime import date, datetime, timezone, timedelta
from decimal import Decimal
from pathlib import Path

from equity_research.assessment import assess_financials
from equity_research.fields import SPECS
from equity_research.models import Fact, Source
from equity_research.reporting import build_report, render_markdown
from equity_research.report_html import render_html

CIK = '0000320193'
START, END = date(2025,1,1), date(2025,12,31)
NOW = datetime(2026,11,2,18,tzinfo=timezone.utc)


def facts(**changes):
    values = dict(assets='100', liabilities='70', net_income='10', operating_cash_flow='12',
                  operating_income='15', current_assets='40', current_liabilities='20')
    values.update(changes)
    return {k: Fact(CIK, k, Decimal(v), Source.SEC, None if SPECS[k].instant else START,
                   END, 'USD', 'currency', NOW, NOW, SPECS[k].accounting_definition,
                   'https://data.sec.gov/recorded', raw_sha256='a'*64) for k,v in values.items() if v is not None}


def assess(values, **changes):
    args = dict(issuer_id=CIK, period_start=START, period_end=END, currency='USD', as_of=NOW)
    args.update(changes)
    return assess_financials(values, **args)


class AssessmentTests(unittest.TestCase):
    def test_complete_positive_screen_does_not_clear_overall_risk_or_approve(self):
        r=assess(facts())
        self.assertEqual(r['quantitative_gate'],'no_screen_trigger')
        self.assertTrue(all(c['status']=='not_triggered' for c in r['checks']))
        self.assertFalse(r['overall_risk_cleared']);self.assertFalse(r['investment_approved'])

    def test_balance_deficit_requires_review_even_with_positive_profit_and_cash(self):
        r=assess(facts(liabilities='101'))
        self.assertEqual(r['quantitative_gate'],'critical_review_required')
        self.assertEqual(r['critical_flags'],['balance_deficit'])
        self.assertEqual(len(r['checks'][0]['inputs']),2)
        self.assertIn('does not establish insolvency',r['checks'][0]['explanation'])

    def test_combined_loss_and_cash_burn_cannot_be_offset_by_large_assets(self):
        r=assess(facts(assets='10000000',net_income='-1',operating_cash_flow='-2'))
        self.assertEqual(r['critical_flags'],['loss_and_operating_cash_outflow'])
        self.assertEqual(r['quantitative_gate'],'critical_review_required')

    def test_single_loss_zero_and_missing_are_distinct(self):
        self.assertFalse(assess(facts(net_income='-1'))['critical_flags'])
        self.assertFalse(assess(facts(net_income='0',operating_cash_flow='0'))['critical_flags'])
        r=assess(facts(operating_cash_flow=None))
        self.assertEqual(r['quantitative_gate'],'unresolved')
        self.assertIsNone(r['checks'][1]['triggered'])
        self.assertEqual(r['checks'][1]['missing_fields'],['operating_cash_flow'])

    def test_current_shortfall_and_operating_loss_are_watch_not_insolvency(self):
        r=assess(facts(current_assets='10',operating_income='-2'))
        self.assertEqual(r['critical_flags'],[])
        self.assertEqual(set(r['watch_flags']),{'current_balance_shortfall','operating_loss'})
        self.assertFalse(r['overall_risk_cleared'])

    def test_critical_gate_survives_missing_other_evidence(self):
        r=assess(facts(liabilities='110',operating_income=None))
        self.assertEqual(r['quantitative_gate'],'critical_review_required')
        self.assertIn('operating_loss',r['unresolved_checks'])

    def test_exact_identity_currency_definition_period_and_source_proof_required(self):
        for change in (dict(issuer_id='0000789019'),dict(currency='EUR'),dict(period_end=date(2025,12,30)),
                       dict(accounting_definition='us-gaap:LiabilitiesCurrent'),dict(raw_sha256=None),
                       dict(retrieved_at=NOW+timedelta(days=1))):
            f=facts();f['liabilities']=replace(f['liabilities'],**change)
            r=assess(f)
            self.assertEqual(r['checks'][0]['status'],'unresolved')
            self.assertIsNone(r['checks'][0]['triggered'])

    def test_negative_balance_not_favorable_or_absolute_value(self):
        r=assess(facts(liabilities='-100'))
        self.assertEqual(r['checks'][0]['status'],'unresolved')
        self.assertEqual(r['checks'][0]['rejections'][0]['reason'],'unsupported_balance_sign')

    def test_no_quarterly_or_guessed_annual_flow(self):
        for start in (None,date(2025,10,1)):
            r=assess(facts(),period_start=start)
            self.assertEqual(r['checks'][1]['status'],'unresolved')
            self.assertEqual(r['checks'][0]['status'],'not_triggered')

    def test_stale_financial_period_does_not_become_fresh_after_retrieval(self):
        r=assess(facts(),as_of=NOW+timedelta(days=500))
        self.assertEqual(r['quantitative_gate'],'unresolved')
        self.assertTrue(all(c['rejections'] for c in r['checks']))

    def test_operands_retain_original_source_and_input_is_not_mutated(self):
        f=facts();before=copy.deepcopy(f);r=assess(f)
        self.assertEqual(f,before)
        self.assertEqual(r['checks'][0]['inputs'][0]['raw_sha256'],'a'*64)
        self.assertEqual(r['checks'][0]['inputs'][0]['retrieved_at'],NOW)

    def test_recorded_hundred_report_preserves_numeric_counts_and_recomputes_risk(self):
        root=Path(__file__).resolve().parents[1]
        batch=json.loads(gzip.decompress((root/'docs/evidence/liquidity100/batch.json.gz').read_bytes()))
        batch['companies'][0].update(financial_assessment={'overall_risk_cleared':True},total_score=100)
        report=build_report(batch)
        self.assertEqual(report['summary']['accepted_facts'],843)
        self.assertEqual(report['summary']['arithmetic_results'],576)
        self.assertEqual(sum(report['financial_review_summary'].values()),100)
        self.assertEqual(report['financial_review_summary'],dict(no_screen_trigger=52,unresolved=44,critical_review_required=4))
        self.assertEqual({c['symbol'] for c in report['companies'] if c['financial_assessment']['critical_flags']},{'ABBV','PM','DELL','MCD'})
        for c in report['companies']:
            self.assertFalse(c['financial_assessment']['overall_risk_cleared'])
            self.assertIsNone(c['total_score'])
            self.assertIn('source_bound_valuation_required',c['score_blockers'])
        self.assertIn('Financial review gate:',render_markdown(report))

    def test_published_browser_and_assessments_reproduce_with_original_source_times(self):
        root=Path(__file__).resolve().parents[1];evidence=root/'docs/evidence/risk100'
        source=root/'docs/evidence/liquidity100/batch.json.gz'
        r=build_report(json.loads(gzip.decompress(source.read_bytes())))
        self.assertEqual((evidence/'report.html').read_text(),render_html(r))
        audit=json.loads(gzip.decompress((evidence/'assessment.json.gz').read_bytes()))
        self.assertEqual(audit['source_sha256'],hashlib.sha256(source.read_bytes()).hexdigest())
        self.assertEqual(audit['as_of'],r['as_of'])
        self.assertFalse(audit['mvp_accepted'])
        for row in json.loads((evidence/'manifest.json').read_text())['files']:
            self.assertEqual(row['sha256'],hashlib.sha256((evidence/row['file']).read_bytes()).hexdigest())

    def test_invalid_company_is_isolated_and_cannot_receive_favorable_risk_screen(self):
        root=Path(__file__).resolve().parents[1]
        batch=json.loads((root/'docs/evidence/archived-eight-financial.json').read_text())
        batch['companies'][0]['issuer_id']='not-a-cik'
        report=build_report(batch)
        self.assertEqual(report['companies'][0]['financial_assessment']['quantitative_gate'],'invalid_evidence')
        self.assertEqual(report['summary']['companies'],8)

    def test_html_escapes_company_text_and_keeps_missing_scores_unavailable(self):
        root=Path(__file__).resolve().parents[1]
        batch=json.loads((root/'docs/evidence/archived-eight-financial.json').read_text())
        batch['companies'][0]['symbol']='</h2><script>alert(1)</script>'
        report=build_report(batch);page=render_html(report)
        self.assertNotIn('<script>alert(1)</script>',page)
        self.assertIn('&lt;script&gt;alert(1)&lt;/script&gt;',page)
        self.assertEqual(page.count('<article '),8)
        self.assertIn('Score: unavailable',page)
        self.assertIn('aria-live="polite"',page)

    def test_cli_produces_html_and_refuses_overwriting_its_source(self):
        root=Path(__file__).resolve().parents[1]
        source=root/'docs/evidence/archived-eight-financial.json'
        env={**os.environ,'PYTHONPATH':str(root/'src')}
        with tempfile.TemporaryDirectory() as td:
            out=Path(td)/'report.json';page=Path(td)/'report.html'
            cmd=[sys.executable,'-m','equity_research','research-report','--input',str(source),'--output',str(out),'--html',str(page)]
            run=subprocess.run(cmd,env=env,capture_output=True,text=True)
            self.assertEqual(run.returncode,0,run.stdout+run.stderr)
            self.assertEqual(page.read_text().count('<article '),8)
            self.assertIn('financial_review_summary',json.loads(out.read_text()))
            original=source.read_bytes();cmd[-1]=str(source)
            refused=subprocess.run(cmd,env=env,capture_output=True,text=True)
            self.assertEqual(refused.returncode,2);self.assertEqual(source.read_bytes(),original)


if __name__=='__main__':unittest.main()
