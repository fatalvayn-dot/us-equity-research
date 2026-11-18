"""Batch processing may outlast live quote caching without fabricating freshness."""
import json
import unittest
from dataclasses import replace
from datetime import timedelta

from equity_research.scoring import (build_score_report, ACTIVE_MODEL_VERSION,
    OPERATING_MODEL_V1, render_score_markdown)
from equity_research.score_html import render_score_html
from test_scoring import (ASOF, financial, comparisons, companyfacts, metadata,
    filing, identity, price, history)


class BatchMarketFreshnessTests(unittest.TestCase):
    def build(self, minutes, model=ACTIVE_MODEL_VERSION, change=None):
        responses=[companyfacts(),metadata(),filing(),identity(),price(),history()]
        if change:
            responses=change(responses)
        return build_score_report(financial(),*comparisons(),responses,
            as_of=ASOF+timedelta(minutes=minutes),model_version=model)

    def test_transfer_delay_preserves_scores_only_in_new_explicit_batch_model(self):
        original=self.build(0)
        delayed=self.build(35)
        self.assertEqual(delayed['ranking'],original['ranking'])
        self.assertEqual(delayed['summary']['scored_companies'],1)
        for model in ('technology-research-v1',OPERATING_MODEL_V1):
            self.assertEqual(self.build(35,model)['ranking'],[])
        policy=delayed['market_evidence_policy']
        self.assertEqual(policy['maximum_response_age_seconds'],3600)
        self.assertEqual(policy['live_price_ttl_seconds'],900)
        self.assertFalse(policy['live_price_service'])
        self.assertIn('60 dakika',render_score_markdown(delayed))
        self.assertIn('60 dakika',render_score_html(delayed))
        a=original['companies'][0]['valuation']['indication']['price']
        b=delayed['companies'][0]['valuation']['indication']['price']
        self.assertEqual(a,b)  # No rewritten observation, market time or hash.

    def test_one_hour_bound_applies_to_quote_and_history_independently(self):
        self.assertEqual(self.build(59)['ranking'],[])
        def stale_history(rows):
            return [replace(r,retrieved_at=ASOF-timedelta(hours=2))
                if 'range=1y' in r.url else r for r in rows]
        report=self.build(35,change=stale_history)
        self.assertEqual(report['ranking'],[])
        self.assertEqual(report['companies'][0]['failed_validation_stage'],'market_history')

    def test_future_observation_and_wrong_currency_still_rejected(self):
        def future(rows):
            return [replace(r,retrieved_at=ASOF+timedelta(hours=2))
                if 'range=5d' in r.url else r for r in rows]
        self.assertEqual(self.build(35,change=future)['ranking'],[])
        def currency(rows):
            result=[]
            for r in rows:
                if 'range=5d' in r.url:
                    payload=json.loads(r.body)
                    payload['chart']['result'][0]['meta']['currency']='EUR'
                    r=replace(r,body=json.dumps(payload).encode())
                result.append(r)
            return result
        self.assertEqual(self.build(35,change=currency)['ranking'],[])
