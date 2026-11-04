"""Actual public recordings; CI does not request live providers."""
import gzip
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime,timedelta
from decimal import Decimal,localcontext
from pathlib import Path

from equity_research.cache import encode
from equity_research.evidence_bundle import read_bundle
from equity_research.valuation import build_valuation_report

ROOT=Path(__file__).resolve().parents[1]
EVIDENCE=ROOT/'docs/evidence/valuation-sample'


def report():return json.loads(gzip.decompress((EVIDENCE/'report.json.gz').read_bytes()))
def batch():return json.loads(gzip.decompress((ROOT/'docs/evidence/liquidity100/batch.json.gz').read_bytes()))


class RecordedValuationTests(unittest.TestCase):
    def test_actual_three_counts_reconcile_to_original_quarterly_filings_and_current_sec_values(self):
        r=report();valuations=[c['valuation'] for c in r['companies'] if c['valuation']]
        self.assertEqual(r['summary'],dict(candidates=100,indicative_valuations=3,rejected=0,pending=97,scored_companies=0))
        self.assertEqual({v['symbol'] for v in valuations},{'AAPL','MSFT','NVDA'})
        self.assertEqual({v['symbol']:len(v['independent_financial_confirmations']) for v in valuations},{'AAPL':4,'MSFT':4,'NVDA':2})
        self.assertEqual(sum(m['value'] is not None for v in valuations for m in v['metrics']),7)
        for v in valuations:
            self.assertEqual(v['disclosed_shares']['companyfacts']['form'],'10-Q')
            self.assertFalse(v['corporate_actions_validated']);self.assertFalse(v['scope_approved'])
            self.assertIsNone(v['fair_value']);self.assertIsNone(v['total_score'])
            for check in v['independent_financial_confirmations']:
                self.assertEqual(Decimal(check['first_selected_fact']['value']),Decimal(check['sec_verification_fact']['value']))
        self.assertFalse(r['mvp_accepted'])

    def test_exact_13_original_observations_reproduce_every_report_value(self):
        sources=list(read_bundle(ROOT/'tests/fixtures/valuation-sources'))
        self.assertEqual(len(sources),13)
        expected=report()
        actual=build_valuation_report(batch(),sources,as_of=datetime.fromisoformat(expected['as_of']))
        self.assertEqual(json.loads(json.dumps(actual,default=encode)),expected)
        with localcontext() as ctx:
            ctx.prec=100
            for row in expected['companies']:
                v=row['valuation']
                if v:self.assertEqual(Decimal(v['indicated_capitalization']),Decimal(v['price']['value'])*Decimal(v['disclosed_shares']['value']))

    def test_expired_recordings_cannot_be_relabelled_as_current_quotes(self):
        r=build_valuation_report(batch(),read_bundle(ROOT/'tests/fixtures/valuation-sources'),
            as_of=datetime.fromisoformat(report()['as_of'])+timedelta(minutes=16))
        self.assertEqual(r['summary']['indicative_valuations'],0)
        self.assertEqual(r['summary']['rejected'],3);self.assertEqual(r['summary']['pending'],97)

    def test_artifact_integrity_and_zero_network_resume_evidence(self):
        manifest=json.loads((EVIDENCE/'manifest.json').read_text())
        self.assertEqual(manifest['input_sha256'],hashlib.sha256((ROOT/manifest['input_batch']).read_bytes()).hexdigest())
        for row in manifest['files']:
            data=(EVIDENCE/row['file']).read_bytes();self.assertEqual(len(data),row['bytes'])
            self.assertEqual(hashlib.sha256(data).hexdigest(),row['sha256'])
        resume=json.loads((EVIDENCE/'zero-work-resume.json').read_text())
        self.assertTrue(resume['original_prices_counts_sources_times_and_indications_unchanged'])
        self.assertEqual((resume['source_get_invocations'],resume['price_get_invocations'],resume['identity_get_invocations']),(0,0,0))
        audit=json.loads((EVIDENCE/'audit.json').read_text())
        self.assertEqual((audit['source_get_invocations'],audit['new_price_get_invocations'],audit['new_identity_get_invocations']),(9,3,1))

    def test_cli_replays_recorded_cutoff_and_protects_bundle(self):
        env={**os.environ,'PYTHONPATH':str(ROOT/'src')}
        with tempfile.TemporaryDirectory() as td:
            out=Path(td)/'report.json';md=Path(td)/'report.md'
            cmd=[sys.executable,'-m','equity_research','valuation-report','--input',str(ROOT/'docs/evidence/liquidity100/batch.json.gz'),
                '--source-bundle',str(ROOT/'tests/fixtures/valuation-sources'),'--as-of',report()['as_of'],
                '--output',str(out),'--markdown',str(md)]
            result=subprocess.run(cmd,env=env,capture_output=True,text=True)
            self.assertEqual(result.returncode,0,result.stdout+result.stderr)
            self.assertEqual(json.loads(out.read_text())['summary']['indicative_valuations'],3)
            self.assertIn('gözlenen güncel piyasa değeri veya adil değer değildir',md.read_text())
            cmd[cmd.index('--output')+1]=str(ROOT/'tests/fixtures/valuation-sources/manifest.json')
            refused=subprocess.run(cmd,env=env,capture_output=True,text=True)
            self.assertEqual(refused.returncode,2)
