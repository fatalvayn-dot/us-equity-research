"""Real recorded response replay, not fresh live acceptance."""
import gzip
import json
import unittest
from collections import Counter
from pathlib import Path

from equity_research.batch import load_plan
from equity_research.cache import encode
from equity_research.comparative import build_comparative_report, comparable_periods

ROOT=Path(__file__).resolve().parents[1]/'docs/evidence/comparative100'

def recorded(name):
    raw=(ROOT/name).read_bytes()
    return json.loads(gzip.decompress(raw) if name.endswith('.gz') else raw)

class RecordedComparativeTests(unittest.TestCase):
    def test_recorded_counts_missing_bases_and_no_scores(self):
        audit=recorded('audit.json');report=recorded('report.json.gz')
        self.assertEqual(audit['candidates'],100)
        self.assertEqual(report['summary'],dict(companies=80,arithmetic_results=334,scored_companies=0))
        self.assertEqual(audit['current_facts'],347);self.assertEqual(audit['prior_facts'],347)
        states=Counter(c['status'] for row in report['companies'] for c in row['calculations'])
        self.assertEqual(states,dict(calculated_arithmetic_only=334,nonpositive_base=13))
        self.assertEqual(report['ranking'],[]);self.assertFalse(report['mvp_accepted'])
        self.assertEqual(audit['new_http_requests'],0);self.assertFalse(audit['freshness_accepted'])
        self.assertEqual(len(audit['deferred']),15)
        self.assertEqual(audit['plan_states'],dict(ready_for_ordered_collection=80,prior_period_unresolved=5))

    def test_original_ordered_batches_reproduce_all_growth(self):
        report=recorded('report.json.gz')
        replay=build_comparative_report(recorded('current-batch.json.gz'),recorded('prior-batch.json.gz'))
        self.assertEqual(json.loads(json.dumps(replay['companies'],default=encode)),report['companies'])
        for side in ('current','prior'):
            batch=recorded(side+'-batch.json.gz')
            for company in batch['companies']:
                for row in company['fields']:
                    self.assertEqual([(a['source'],a['status']) for a in row['attempts']],[('Yahoo','unsupported_field'),('SEC','valid')])
                    self.assertLessEqual(row['fact']['retrieved_at'],row['attempts'][-1]['attempted_at'])

    def test_plans_and_operand_source_vintages_remain_exact(self):
        from datetime import date
        audit=recorded('audit.json');sources={p['issuer_id']:p for p in audit['plans']}
        for side in ('current','prior'):
            self.assertEqual(len(load_plan(recorded(side+'-plan.json'))),80)
            batch=recorded(side+'-batch.json.gz')
            for row in batch['companies']:
                source=sources[row['issuer_id']]['discovery_source']
                for field in row['fields']:
                    fact=field['fact']
                    self.assertEqual((fact['source_url'],fact['raw_sha256'],fact['retrieved_at']),
                                     (source['url'],source['sha256'],source['retrieved_at']))
        for row in recorded('report.json.gz')['companies']:
            for c in row['calculations']:
                current,prior=c['inputs']
                self.assertTrue(comparable_periods(*(date.fromisoformat(f[k]) for f in (current,prior) for k in ('period_start','period_end'))))
                self.assertEqual(current['filing_accession'],prior['filing_accession'])
                self.assertFalse(c['sector_model_supported']);self.assertFalse(c['scope_approved'])
