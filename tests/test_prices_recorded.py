"""Original 2026-11-02 public-price recordings, not a fresh live run in CI."""
import gzip
import hashlib
import json
import unittest
from dataclasses import asdict
from datetime import datetime
from pathlib import Path

from equity_research.cache import encode
from equity_research.evidence_bundle import read_bundle
from equity_research.prices import parse_price

ROOT=Path(__file__).resolve().parents[1]
EVIDENCE=ROOT/'docs/evidence/price100'

def recorded(name):
    raw=(EVIDENCE/name).read_bytes()
    return json.loads(gzip.decompress(raw) if name.endswith('.gz') else raw)

class RecordedPriceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.responses={(r.url,r.sha256,r.retrieved_at.isoformat()):r for r in read_bundle(ROOT/'tests/fixtures/price100-sources')}
        cls.report=recorded('report.json.gz')

    def test_100_real_candidate_prices_are_not_100_scope_or_model_approvals(self):
        r=self.report
        self.assertEqual(r['summary']['candidates'],100);self.assertEqual(r['summary']['collected_prices'],100)
        self.assertEqual(r['summary']['new_price_get_invocations'],100);self.assertEqual(r['new_identity_get_invocations'],1)
        self.assertEqual(r['ranking'],[]);self.assertFalse(r['mvp_accepted'])
        self.assertTrue(all(not c['scope_approved'] and c['total_score'] is None for c in r['companies']))
        self.assertEqual(len(self.responses),101)

    def test_every_price_reproduces_from_its_exact_original_body_and_identity(self):
        cutoff=datetime.fromisoformat(self.report['generated_at'])
        for row in self.report['companies']:
            p=row['price']
            raw=self.responses[(p['source_url'],p['raw_sha256'],p['retrieved_at'])]
            identity=self.responses[(p['identity_evidence_url'],p['identity_evidence_sha256'],p['identity_observed_at'])]
            replay=parse_price(raw,identity,cik=row['issuer_id'],symbol=row['symbol'],as_of=cutoff)
            self.assertEqual(json.loads(json.dumps(asdict(replay),default=encode)),p)
            self.assertEqual(p['available_at'],p['retrieved_at'])

    def test_first_valid_yahoo_stops_without_invented_fallback_http(self):
        for row in self.report['companies']:
            self.assertEqual(len(row['attempts']),1)
            self.assertEqual((row['attempts'][0]['source'],row['attempts'][0]['status']),('Yahoo','valid'))
            self.assertTrue(row['attempts'][0]['http_requested'])
        self.assertTrue(self.report['all_selected_price_references_archived'])

    def test_immediate_zero_work_resume_preserves_all_original_values_and_times(self):
        resume=recorded('cached-report.json.gz');summary=recorded('zero-work-resume.json')
        self.assertEqual(resume['summary']['collected_prices'],100)
        self.assertEqual(resume['summary']['new_price_get_invocations'],0);self.assertEqual(resume['new_identity_get_invocations'],0)
        self.assertTrue(summary['original_prices_and_observation_times_unchanged'])
        for first,last in zip(self.report['companies'],resume['companies']):
            self.assertEqual(first['price'],last['price'])
            self.assertTrue(last['cached']);self.assertFalse(last['attempts'][0]['http_requested'])
            self.assertEqual(last['source_evidence']['sha256'],last['price']['raw_sha256'])

    def test_published_report_hashes_and_source_count(self):
        manifest=recorded('manifest.json');stored=(EVIDENCE/'report.json.gz').read_bytes()
        self.assertEqual(hashlib.sha256(stored).hexdigest(),manifest['stored_report_sha256'])
        self.assertEqual(hashlib.sha256(gzip.decompress(stored)).hexdigest(),manifest['report_sha256'])
        self.assertEqual(hashlib.sha256((EVIDENCE/'report.md').read_bytes()).hexdigest(),manifest['markdown_sha256'])
        self.assertEqual(manifest['source_observations'],101)
