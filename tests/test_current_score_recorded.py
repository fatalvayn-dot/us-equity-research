"""Actual 22-market-source collection joined to the exact common100 inputs."""
import gzip,json,unittest
from datetime import datetime
from decimal import Decimal
from itertools import chain
from pathlib import Path

from equity_research.cache import encode
from equity_research.evidence_bundle import read_bundle
from equity_research.scoring import build_score_report

ROOT=Path(__file__).resolve().parents[1]


def read(path):
    b=(ROOT/path).read_bytes()
    return json.loads(gzip.decompress(b) if path.endswith('.gz') else b)


class CurrentScoreRecordedTests(unittest.TestCase):
    def test_all_18_scores_confirmations_reproduce_from_exact_public_bodies(self):
        expected=read('docs/evidence/current-score100/report.json.gz')
        actual=build_score_report(read('docs/evidence/common-financial100/batch.json.gz'),
            read('docs/evidence/common-comparative100/current-batch.json.gz'),
            read('docs/evidence/common-comparative100/prior-batch.json.gz'),
            chain(read_bundle(ROOT/'tests/fixtures/valuation22-sources'),
                  read_bundle(ROOT/'tests/fixtures/liability-equation5-sources')),
            as_of=datetime.fromisoformat(expected['as_of']))
        # The archived report predates additive blocker diagnostics. Preserve its
        # exact financial/score contract without rewriting historical evidence.
        comparable=json.loads(json.dumps(actual,default=encode))
        diagnostics=0
        for company in comparable['companies']:
            detail=company.pop('valuation_diagnostics',None)
            if detail is not None:
                diagnostics+=1
                self.assertIsNone(company['total_score'])
                self.assertEqual(company['blockers'],['valuation_source_evidence_required'])
                self.assertTrue(detail.get('missing_source_urls') or detail.get('missing_evidence') or detail.get('failed_validation_stage'))
        self.assertGreater(diagnostics,0)
        self.assertEqual(comparable,expected)
        self.assertEqual(actual['summary'],dict(candidates=100,scored_companies=18,critical_review=4,unscored=82))
        self.assertEqual([(r['symbol'],str(r['score'])) for r in actual['ranking']][:3],[('MU','87'),('INTU','78.0'),('MPWR','78')])
        self.assertEqual({r['symbol']:str(r['score']) for r in actual['ranking'] if r['symbol'] in {'AMD','INTC','ADI','CDNS','ADSK'}},
            {'ADI':'74','AMD':'67','CDNS':'65.5','ADSK':'57.0','INTC':'20.5'})
        for c in actual['companies']:
            self.assertFalse(c['investment_approved'])
            if c['total_score'] is not None:
                self.assertEqual(len(c['evidence']['financial_confirmations']),9)
                self.assertEqual(sum(v['score'] for v in c['components'].values()),c['total_score'])
            else:self.assertIsNone(c['rank'])
        self.assertFalse(actual['input_provenance']['report_generation_is_source_refresh'])
        self.assertEqual(actual['input_provenance']['batches']['financial']['selected_facts'],988)
        originals=read('docs/evidence/current-score100/original-annual-checks.json')
        self.assertEqual(originals['summary'],{'matched':180});self.assertEqual(originals['scored_companies'],18)
        for check in originals['checks']:
            self.assertEqual(Decimal(check['selected_value']),Decimal(check['original']['value']))
            if check.get('confirmation_method')=='original_filing_balance_equation':
                self.assertEqual(check['original']['formula'],'LiabilitiesAndStockholdersEquity - total_equity')
                self.assertFalse(check['original']['automatic_substitution'])
            else:self.assertEqual(check['original']['status'],'exact_original_value')

    def test_actual_collection_resume_keeps_evidence_and_zero_get_counts(self):
        cold=read('docs/evidence/valuation22/collection.json.gz')
        warm=read('docs/evidence/valuation22/resume.json.gz')
        self.assertEqual(cold['summary']['new_get_invocations'],103)
        self.assertEqual(cold['summary']['price_states'],{'valid':22})
        self.assertEqual(cold['summary']['history_states'],{'valid':20,'not_started':2})
        self.assertEqual(cold['summary']['share_states'],{'verified_dated_share_class':18,'missing_disclosed_shares':1,'symbol_mismatch':2,'invalid_data':1})
        self.assertEqual(warm['summary']['new_get_invocations'],0)
        for a,b in zip(cold['companies'],warm['companies']):
            for k in ('identity_status','share_check','price_check','history_check'):self.assertEqual(a[k],b[k])
        blocked={c['symbol']:c['share_check']['status'] for c in cold['companies'] if c['share_check']['status']!='verified_dated_share_class'}
        self.assertEqual(blocked,dict(PLTR='missing_disclosed_shares',ORCL='symbol_mismatch',MCHP='symbol_mismatch',ON='invalid_data'))
        self.assertFalse(warm['mvp_accepted'])
