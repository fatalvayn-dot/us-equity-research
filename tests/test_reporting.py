import copy
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from equity_research.cache import encode
from equity_research.reporting import build_report, render_markdown

ROOT=Path(__file__).resolve().parents[1]


def batch():
    return json.loads((ROOT/'docs/evidence/archived-eight-financial.json').read_text())


def collected(b):
    return next(f for c in b['companies'] for f in c['fields'] if f['fact'])


class ReportingTests(unittest.TestCase):
    def test_recorded_facts_and_exact_arithmetic_reported_without_scores(self):
        r=build_report(batch())
        self.assertEqual(r['summary']['companies'],8)
        self.assertEqual(r['summary']['accepted_facts'],43)
        self.assertEqual(r['summary']['arithmetic_results'],17)
        self.assertEqual(r['ranking'],[])
        self.assertEqual(sum(r['score_weights'].values()),100)
        self.assertTrue(all(c['total_score'] is None for c in r['companies']))
        self.assertFalse(r['mvp_accepted'])

    def test_original_input_not_mutated(self):
        b=batch(); before=copy.deepcopy(b);build_report(b);self.assertEqual(b,before)

    def test_missing_data_and_unattempted_sources_remain_explicit(self):
        r=build_report(batch())
        for old,new in zip(batch()['companies'],r['companies']):
            for a,b in zip(old['fields'],new['fields']):
                self.assertEqual(a['attempts'],b['attempts'])
                self.assertEqual(a['fact'] is None,b['fact'] is None)

    def test_unstarted_is_not_missing_or_attempted(self):
        b=batch();row=collected(b);row.update(state='not_started',fact=None,attempts=[])
        r=build_report(b);self.assertEqual(r['companies'][0]['fields'][1]['attempts'],[])
        self.assertEqual(r['summary']['accepted_facts'],42)

    def test_future_observation_invalidates_only_affected_company(self):
        b=batch();collected(b)['fact']['retrieved_at']='2099-01-01T00:00:00+00:00'
        r=build_report(b)
        self.assertEqual(r['companies'][0]['status'],'invalid_evidence')
        self.assertEqual(r['companies'][0]['fields'],[])
        self.assertTrue(all(c['status']=='review_required' for c in r['companies'][1:]))

    def test_wrong_identity_definition_currency_or_period_cannot_reach_arithmetic(self):
        for key,value in [('issuer_id','0000320193'),('accounting_definition','us-gaap:Revenues'),('currency','EUR'),('period_end','2025-01-01')]:
            b=batch();collected(b)['fact'][key]=value
            r=build_report(b);self.assertEqual(r['companies'][0]['status'],'invalid_evidence')
            self.assertEqual(r['companies'][0]['calculations'],[])

    def test_hashless_fact_is_not_accepted(self):
        b=batch();collected(b)['fact']['raw_sha256']=None
        self.assertEqual(build_report(b)['companies'][0]['status'],'invalid_evidence')

    def test_out_of_order_or_skipped_source_not_accepted(self):
        b=batch();row=collected(b);row['attempts']=row['attempts'][1:]
        self.assertEqual(build_report(b)['companies'][0]['status'],'invalid_evidence')

    def test_fallback_after_first_valid_is_rejected(self):
        b=batch();row=collected(b);row['attempts'][0]['status']='valid'
        self.assertEqual(build_report(b)['companies'][0]['status'],'invalid_evidence')

    def test_missing_fact_with_valid_attempt_is_invalid(self):
        b=batch();collected(b)['fact']=None
        self.assertEqual(build_report(b)['companies'][0]['status'],'invalid_evidence')

    def test_duplicate_field_or_mixed_context_not_silently_overwritten(self):
        for mode in ('duplicate','mixed'):
            b=batch();c=b['companies'][0]
            if mode=='duplicate':c['fields'].append(copy.deepcopy(c['fields'][0]))
            else:c['fields'][0]['query']['period_end']='2025-01-25'
            self.assertEqual(build_report(b)['companies'][0]['status'],'invalid_evidence')

    def test_duplicate_issuer_cannot_inflate_acceptance_count(self):
        b=batch();b['companies'].append(copy.deepcopy(b['companies'][0]))
        with self.assertRaises(ValueError):build_report(b)

    def test_caller_scope_or_score_does_not_grant_approval(self):
        b=batch();b['companies'][0].update(scope_status='approved',total_score=100,investment_approved=True)
        c=build_report(b)['companies'][0]
        self.assertEqual(c['status'],'invalid_evidence');self.assertIsNone(c['total_score']);self.assertFalse(c['investment_approved'])

    def test_out_of_scope_company_not_calculated_or_ranked(self):
        b=batch();b['companies'][0]['scope_status']='out_of_scope'
        c=build_report(b)['companies'][0]
        self.assertEqual(c['status'],'out_of_scope');self.assertEqual(c['calculations'],[]);self.assertIsNone(c['rank'])

    def test_markdown_contains_sources_hashes_definitions_ratios_and_missing_reasons(self):
        r=build_report(batch());text=render_markdown(r)
        for token in ('https://','us-gaap:',collected(batch())['fact']['raw_sha256'],'Puan / 100','Mevcut değil','Piyasa fiyatı','Faaliyetlerden nakit akışı'):
            self.assertIn(token,text)

    def test_cli_exports_json_and_markdown_without_network(self):
        with tempfile.TemporaryDirectory() as tmp:
            dest=Path(tmp)
            cmd=[sys.executable,'-m','equity_research','research-report','--input',str(ROOT/'docs/evidence/archived-eight-financial.json'),'--output',str(dest/'report.json'),'--markdown',str(dest/'report.md')]
            r=subprocess.run(cmd,cwd=ROOT,env={**os.environ,'PYTHONPATH':str(ROOT/'src')},capture_output=True,text=True,timeout=20)
            self.assertEqual(r.returncode,0,r.stderr);self.assertEqual(json.loads((dest/'report.json').read_text())['summary']['accepted_facts'],43)
            self.assertTrue((dest/'report.md').exists())

    def test_report_destination_cannot_overwrite_input(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'input.json';p.write_text('{}')
            r=subprocess.run([sys.executable,'-m','equity_research','research-report','--input',str(p),'--output',str(p)],cwd=ROOT,env={**os.environ,'PYTHONPATH':str(ROOT/'src')},capture_output=True,text=True,timeout=20)
            self.assertNotEqual(r.returncode,0);self.assertEqual(p.read_text(),'{}')
