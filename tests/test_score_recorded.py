"""Actual pilot source replay and independent metric checks; no CI network calls."""
import gzip
import hashlib
import json
import math
import os
import statistics
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime,timedelta,timezone
from decimal import Decimal
from pathlib import Path

from equity_research.cache import encode
from equity_research.evidence_bundle import read_bundle
from equity_research.scoring import build_score_report
from equity_research.score_html import render_score_html

ROOT=Path(__file__).resolve().parents[1];EVIDENCE=ROOT/'docs/evidence/score-pilot'
INPUTS=['docs/evidence/liquidity100/batch.json.gz','docs/evidence/comparative100/current-batch.json.gz','docs/evidence/comparative100/prior-batch.json.gz']


def report():return json.loads(gzip.decompress((EVIDENCE/'report.json.gz').read_bytes()))
def batches():return [json.loads(gzip.decompress((ROOT/p).read_bytes())) for p in INPUTS]
def sources():return list(read_bundle(ROOT/'tests/fixtures/valuation-sources'))+list(read_bundle(ROOT/'tests/fixtures/score-market-sources'))


class RecordedScoreTests(unittest.TestCase):
    def test_two_ranked_pilot_hypotheses_four_critical_reviews_no_mvp_or_investment_approval(self):
        r=report();self.assertEqual(r['summary'],dict(candidates=100,scored_companies=2,critical_review=4,unscored=98))
        self.assertEqual([(x['symbol'],Decimal(x['score'])) for x in r['ranking']],[('MSFT',Decimal('66.5')),('AAPL',Decimal('53'))])
        self.assertFalse(r['mvp_accepted']);self.assertFalse(r['hundred_active_common_shares_accepted'])
        for c in r['companies']:
            self.assertFalse(c['investment_approved'])
            if c['total_score'] is not None:
                self.assertEqual(sum(Decimal(v['score']) for v in c['components'].values()),Decimal(c['total_score']))
                self.assertEqual(len(c['evidence']['financial_confirmations']),9)
                self.assertFalse(c['legal_disclosure_review']['legal_type_approved'])
        nvda=next(c for c in r['companies'] if c['symbol']=='NVDA')
        self.assertIsNone(nvda['total_score']);self.assertEqual(set(nvda['missing_fields']),{'revenue','capital_expenditure'})

    def test_every_point_and_evidence_reference_reproduces_from_raw_bundles(self):
        expected=report();actual=build_score_report(*batches(),sources(),as_of=datetime.fromisoformat(expected['as_of']))
        self.assertEqual(json.loads(json.dumps(actual,default=encode)),expected)
        self.assertEqual(len(list(read_bundle(ROOT/'tests/fixtures/score-market-sources'))),7)

    def test_volatility_and_liquidity_match_independent_statistical_reference(self):
        raw={(r.url,r.sha256):r for r in sources()}
        for c in report()['companies']:
            if c['total_score'] is None:continue
            market=c['market_risk'];body=raw[(market['source_url'],market['raw_sha256'])]
            item=json.loads(body.body)['chart']['result'][0];day=datetime.fromisoformat(market['quote_day_excluded']).date()
            indexes=[i for i,t in enumerate(item['timestamp']) if datetime.fromtimestamp(t,timezone.utc).date()<day]
            adjusted=[item['indicators']['adjclose'][0]['adjclose'][i] for i in indexes]
            returns=[adjusted[i]/adjusted[i-1]-1 for i in range(1,len(adjusted))]
            expected=statistics.stdev(returns)*math.sqrt(252)
            self.assertAlmostEqual(float(market['annualized_sample_volatility']),expected,places=12)
            q=item['indicators']['quote'][0]
            volume=statistics.median([q['close'][i]*q['volume'][i] for i in indexes[-63:]])
            self.assertAlmostEqual(float(market['median_63_session_close_times_volume']),volume,places=3)

    def test_stale_live_inputs_withhold_all_scores_instead_of_reusing_rank(self):
        r=build_score_report(*batches(),sources(),as_of=datetime.fromisoformat(report()['as_of'])+timedelta(minutes=16))
        self.assertEqual(r['ranking'],[]);self.assertEqual(r['summary']['scored_companies'],0)
        self.assertTrue(all(c['total_score'] is None for c in r['companies']))

    def test_live_helper_integration_and_zero_get_resume_are_separate_reproducible_cohort(self):
        proof=json.loads((EVIDENCE/'live-helper-validation.json').read_text())
        self.assertEqual(proof['initial_get_invocations'],dict(sec_source_get_invocations=0,quote_get_invocations=3,identity_get_invocations=0,history_get_invocations=3))
        self.assertTrue(all(value==0 for value in proof['resume_get_invocations'].values()))
        self.assertTrue(proof['original_sources_times_components_metrics_and_ranking_unchanged'])
        raw=list(read_bundle(ROOT/'tests/fixtures/valuation-sources'))+list(read_bundle(ROOT/'tests/fixtures/score-helper-market-sources'))
        r=build_score_report(*batches(),raw,as_of=datetime.fromisoformat(proof['after_cutoff']))
        self.assertEqual(json.loads(json.dumps(r['ranking'],default=encode)),proof['ranking'])

    def test_html_has_two_ranked_companies_and_escapes_unscored_names(self):
        r=report();r['companies'][-1]['symbol']='</h2><script>alert(1)</script>'
        html=render_score_html(r)
        self.assertNotIn('<script>alert(1)</script>',html);self.assertIn('&lt;script&gt;',html)
        self.assertEqual(html.count('<article '),100);self.assertEqual(html.count('data-scored="true"'),2)
        self.assertIn('66.5',html);self.assertIn('100 aktif adi hisselik MVP henüz kabul edilmedi',html)

    def test_artifact_hashes_and_cli_replay_with_protected_inputs(self):
        manifest=json.loads((EVIDENCE/'manifest.json').read_text())
        for row in manifest['files']:
            body=(EVIDENCE/row['file']).read_bytes();self.assertEqual(hashlib.sha256(body).hexdigest(),row['sha256'])
        for row in manifest['financial_inputs']:
            self.assertEqual(hashlib.sha256((ROOT/row['file']).read_bytes()).hexdigest(),row['sha256'])
        env={**os.environ,'PYTHONPATH':str(ROOT/'src')}
        with tempfile.TemporaryDirectory() as td:
            out=Path(td)/'report.json';page=Path(td)/'report.html'
            cmd=[sys.executable,'-m','equity_research','score-report','--input',str(ROOT/INPUTS[0]),
                '--comparison-input',str(ROOT/INPUTS[1]),'--prior-input',str(ROOT/INPUTS[2]),
                '--source-bundle',str(ROOT/'tests/fixtures/valuation-sources'),'--market-bundle',str(ROOT/'tests/fixtures/score-market-sources'),
                '--as-of',report()['as_of'],'--output',str(out),'--html',str(page)]
            result=subprocess.run(cmd,env=env,capture_output=True,text=True)
            self.assertEqual(result.returncode,0,result.stdout+result.stderr)
            self.assertEqual(json.loads(out.read_text())['summary']['scored_companies'],2)
            self.assertEqual(page.read_text().count('<article '),100)
            cmd[cmd.index('--output')+1]=str(ROOT/INPUTS[1]);before=(ROOT/INPUTS[1]).read_bytes()
            refused=subprocess.run(cmd,env=env,capture_output=True,text=True)
            self.assertEqual(refused.returncode,2);self.assertEqual((ROOT/INPUTS[1]).read_bytes(),before)
