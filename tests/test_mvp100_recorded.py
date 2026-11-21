"""Recorded real-run regression evidence; never fresh live acceptance in CI."""
import gzip
import hashlib
import json
import unittest
from datetime import datetime, timezone
from pathlib import Path

from equity_research.evidence_bundle import read_bundle
from equity_research.reporting import build_report

ROOT=Path(__file__).resolve().parents[1]
EVIDENCE=ROOT/'docs/evidence/mvp100'


def artifact(name):
    manifest=json.loads((EVIDENCE/'reports-manifest.json').read_text())
    row=next(r for r in manifest['files'] if r['logical_name']==name)
    stored=(EVIDENCE/row['file']).read_bytes()
    if hashlib.sha256(stored).hexdigest()!=row['stored_sha256']:raise ValueError('stored artifact hash')
    body=gzip.decompress(stored) if row['encoding']=='gzip' else stored
    if hashlib.sha256(body).hexdigest()!=row['raw_sha256']:raise ValueError('raw artifact hash')
    return body


class RecordedMvp100Tests(unittest.TestCase):
    def test_real_run_counts_and_missing_scores_are_not_full_acceptance(self):
        report=json.loads(artifact('report.json'))
        self.assertEqual(report['summary']['companies'],100)
        self.assertEqual(report['summary']['accepted_facts'],536)
        self.assertEqual(report['summary']['arithmetic_results'],272)
        self.assertEqual(report['pipeline']['companies_with_financial_facts'],96)
        self.assertEqual(report['pipeline']['financial_query_companies'],98)
        self.assertEqual(report['summary']['scored_companies'],0)
        self.assertFalse(report['mvp_accepted'])
        self.assertTrue(all(c['total_score'] is None and not c['investment_approved'] for c in report['companies']))

    def test_recorded_batch_reproduces_all_report_arithmetic_counts(self):
        report=json.loads(artifact('report.json'));batch=json.loads(artifact('batch.json'))
        replay=build_report(batch)
        self.assertEqual(replay['summary'],report['summary'])

    def test_all_stored_reports_pass_content_hash_checks(self):
        manifest=json.loads((EVIDENCE/'reports-manifest.json').read_text())
        for row in manifest['files']:
            self.assertEqual(len(artifact(row['logical_name'])),row['raw_bytes'])

    def test_original_raw_source_observations_cover_every_financial_reference(self):
        observations=set()
        for response in read_bundle(ROOT/'tests/fixtures/mvp100-sources'):
            observations.add((response.url,response.sha256,response.retrieved_at.astimezone(timezone.utc).isoformat()))
        coverage=json.loads(artifact('archive-coverage.json'))
        self.assertEqual(coverage['financial_facts'],536)
        self.assertTrue(coverage['all_references_archived'])
        for fact in coverage['facts']:
            for ref in fact['references']:
                key=(ref['url'],ref['sha256'],datetime.fromisoformat(ref['observed_at']).astimezone(timezone.utc).isoformat())
                self.assertIn(key,observations)

    def test_periods_are_explicit_and_unresolved_jobs_never_infer_start(self):
        report=json.loads(artifact('report.json'));plan=json.loads(artifact('plan.json'))
        docs=json.loads(artifact('documents.json'));periods={r['issuer_id']:r['period'] for r in docs['companies'] if 'period' in r}
        self.assertEqual(len(periods),88)
        for row in plan['companies']:
            if row['period_start']:
                self.assertEqual(row['period_start'],periods[row['issuer_id']]['period_start'])
                self.assertEqual(row['period_end'],periods[row['issuer_id']]['period_end'])
            else:self.assertEqual(row['fields'],['assets','liabilities'])
        unresolved={c['symbol'] for c in report['companies'] if c['status']=='period_unresolved'}
        self.assertEqual(unresolved,{'SPCX','XOM'})
