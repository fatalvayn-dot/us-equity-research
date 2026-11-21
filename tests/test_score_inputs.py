"""Financial report dates must not masquerade as refreshed source observations."""
import copy
import unittest
from datetime import timedelta

from equity_research.score_inputs import score_input_provenance
from equity_research.scoring import render_score_markdown
from equity_research.score_html import render_score_html
from test_scoring import financial,comparisons,score,ASOF,NOW


class ScoreInputTests(unittest.TestCase):
    def test_score_exposes_original_selected_dates_and_batch_digests(self):
        r=score();p=r['input_provenance']
        self.assertFalse(p['report_generation_is_source_refresh'])
        self.assertFalse(p['all_100_financials_freshly_collected'])
        self.assertFalse(p['full_live_acceptance'])
        self.assertTrue(p['original_per_fact_times_preserved'])
        self.assertEqual(set(p['batches']),{'financial','current_comparison','prior_comparison'})
        for b in p['batches'].values():
            self.assertEqual(b['oldest_selected_observation'],NOW.isoformat())
            self.assertEqual(len(b['sha256']),64)
            self.assertEqual(b['missing_financial_identities'],[])
        self.assertIsNotNone(r['companies'][0]['total_score'])

    def test_canonical_hash_preserves_order_independence_and_detects_value_change(self):
        import json
        b=financial();c,p=comparisons()
        first=score_input_provenance(b,c,p,as_of=ASOF)
        reordered=json.loads(json.dumps(b,sort_keys=True))
        self.assertEqual(first,score_input_provenance(reordered,c,p,as_of=ASOF))
        b['companies'][0]['fields'][0]['fact']['value']='999'
        self.assertNotEqual(first['batches']['financial']['sha256'],score_input_provenance(b,c,p,as_of=ASOF)['batches']['financial']['sha256'])

    def test_each_future_or_naive_batch_rejected_at_explicit_cutoff(self):
        for index in range(3):
            for stamp in ((ASOF+timedelta(seconds=1)).isoformat(),ASOF.replace(tzinfo=None).isoformat()):
                batches=[financial(),*comparisons()];batches[index]['generated_at']=stamp
                with self.assertRaises(ValueError):score_input_provenance(*batches,as_of=ASOF)
        b=financial();b['generated_at']=(ASOF+timedelta(seconds=1)).isoformat()
        with self.assertRaises(ValueError):score(b=b)

    def test_partial_comparison_universe_is_visible_and_not_invented(self):
        b=financial();c,p=comparisons()
        c['companies']=[];p['companies']=[]
        audit=score_input_provenance(b,c,p,as_of=ASOF)
        for name in ('current_comparison','prior_comparison'):
            self.assertEqual(audit['batches'][name]['selected_facts'],0)
            self.assertIsNone(audit['batches'][name]['oldest_selected_observation'])
            self.assertEqual(audit['batches'][name]['missing_financial_identities'],[dict(symbol='AAPL',issuer_id='0000320193')])

    def test_future_observation_and_naive_cutoff_rejected(self):
        b=financial();c,p=comparisons()
        b['companies'][0]['fields'][0]['fact']['retrieved_at']=(ASOF+timedelta(seconds=1)).isoformat()
        with self.assertRaises(ValueError):score_input_provenance(b,c,p,as_of=ASOF)
        with self.assertRaises(ValueError):score_input_provenance(financial(),c,p,as_of=ASOF.replace(tzinfo=None))

    def test_no_caller_freshness_approval_is_adopted_or_input_mutated(self):
        b=financial();b['input_provenance']=dict(full_live_acceptance=True)
        before=copy.deepcopy(b);c,p=comparisons()
        audit=score_input_provenance(b,c,p,as_of=ASOF)
        self.assertFalse(audit['full_live_acceptance']);self.assertEqual(before,b)

    def test_human_reports_show_source_dates_without_html_or_markdown_injection(self):
        report=score();md=render_score_markdown(report);html=render_score_html(report)
        self.assertIn('tüm finansal girdilerinin güncellendiği anlamına gelmez',md)
        self.assertIn('yeniden toplandığı anlamına gelmez',html)
        report['input_provenance']['batches']['financial']['oldest_selected_observation']='<script>alert(1)</script>|x'
        self.assertNotIn('<script>alert(1)</script>',render_score_html(report))
        self.assertIn('&lt;script&gt;',render_score_markdown(report))

    def test_rejected_confirmation_identifies_safe_field_stage(self):
        from test_scoring import companyfacts
        c=score(cf_response=companyfacts(assets=1001))['companies'][0]
        self.assertIsNone(c['total_score'])
        self.assertEqual(c['failed_validation_stage'],'financial_confirmation.assets')
        r=score(cf_response=companyfacts(assets=1001))
        self.assertIn('financial_confirmation.assets',render_score_html(r))
        self.assertIn('financial_confirmation.assets',render_score_markdown(r))
