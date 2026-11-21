"""Original-source provenance and fresh sample reconciliation; no live calls in CI."""
import gzip
import hashlib
import json
import unittest
from datetime import date,datetime
from decimal import Decimal
from pathlib import Path

from equity_research.cache import decode_fact
from equity_research.companyfacts import SecCompanyFacts
from equity_research.concept_diagnostics import inspect_concepts
from equity_research.evidence_bundle import read_bundle
from equity_research.fields import SPECS
from equity_research.models import FactRequest
from equity_research.reporting import build_report
from equity_research.prices import parse_price

ROOT=Path(__file__).resolve().parents[1]
EVIDENCE=ROOT/'docs/evidence/liquidity100'

def artifact(name):
    body=(EVIDENCE/name).read_bytes()
    return json.loads(gzip.decompress(body) if name.endswith('.gz') else body)

class RecordedLiquidityTests(unittest.TestCase):
    def test_replayed_100_candidate_counts_and_unaccepted_models(self):
        r=artifact('report.json.gz');extra=artifact('additional-batch.json.gz')
        self.assertEqual(r['summary'],dict(companies=100,company_states={'review_required':98,'period_unresolved':2},accepted_facts=843,arithmetic_results=576,scored_companies=0))
        self.assertEqual(extra['summary']['field_states'],dict(collected=307,pending_data=163))
        self.assertEqual(extra['summary']['new_fields'],470)
        self.assertEqual(sum(any(c['calculation']=='current_ratio' and c['value'] is not None for c in row['calculations']) for row in r['companies']),72)
        self.assertTrue(all(c['total_score'] is None and not c['scope_approved'] for c in r['companies']))
        self.assertFalse(r['fresh_live_acceptance']);self.assertFalse(r['mvp_accepted'])
        self.assertEqual(build_report(artifact('batch.json.gz'))['summary'],r['summary'])

    def test_all_307_new_facts_reextract_from_exact_original_companyfacts_bytes(self):
        extra=artifact('additional-batch.json.gz')
        rows=[f for c in extra['companies'] for f in c['fields'] if f['fact']]
        wanted={(f['fact']['source_url'],f['fact']['raw_sha256'],f['fact']['retrieved_at']) for f in rows}
        responses={}
        for r in read_bundle(ROOT/'tests/fixtures/mvp100-sources'):
            key=(r.url,r.sha256,r.retrieved_at.isoformat())
            if key in wanted:responses[key]=r
        self.assertEqual(set(responses),wanted)
        parsed={};provider=SecCompanyFacts(None)
        for row in rows:
            expected=decode_fact(row['fact']);key=(expected.source_url,expected.raw_sha256,expected.retrieved_at.isoformat())
            response=responses[key]
            if key not in parsed:parsed[key]=SecCompanyFacts._parse(response,expected.issuer_id)[1]
            q=row['query'];request=FactRequest(q['issuer_id'],q['field'],date.fromisoformat(q['period_start']) if q['period_start'] else None,
                date.fromisoformat(q['period_end']),q['currency'],q['unit'],q['accounting_definition'],datetime.fromisoformat(row['as_of']))
            actual=provider._extract(request,SPECS[q['field']].tag,response,parsed[key])
            self.assertEqual(actual,expected)
            self.assertEqual([(a['source'],a['status']) for a in row['attempts']],[('Yahoo','unsupported_field'),('SEC','valid')])

    def test_fifteen_fresh_fields_match_original_annual_ixbrl(self):
        audit=artifact('audit.json');sources={(r.url,r.sha256):r for r in read_bundle(ROOT/'tests/fixtures/liquidity-live-sources')}
        self.assertEqual(len(sources),6);self.assertEqual(audit['fresh_financial_get_invocations'],3)
        matches=0
        for c in audit['fresh_sample']:
            doc=sources[(c['annual_source']['url'],c['annual_source']['sha256'])]
            for instant in (True,False):
                observations=[o for o in c['observations'] if SPECS[o['field']].instant==instant]
                first=decode_fact(observations[0]['fact'])
                original=inspect_concepts(doc.body,cik=c['issuer_id'],concepts=[SPECS[o['field']].accounting_definition for o in observations],
                    period_start=first.period_start,period_end=first.period_end)
                for observation,proof in zip(observations,original['concepts']):
                    f=decode_fact(observation['fact']);raw=sources[(f.source_url,f.raw_sha256)]
                    self.assertEqual(raw.retrieved_at,f.retrieved_at)
                    self.assertEqual(proof['status'],'exact_original_value')
                    self.assertEqual(f.value,Decimal(proof['value']));self.assertTrue(observation['matches']);matches+=1
        self.assertEqual(matches,15)

    def test_artifact_hashes_cover_report_and_exact_batches(self):
        for r in artifact('manifest.json')['files']:
            body=(EVIDENCE/r['file']).read_bytes()
            self.assertEqual(len(body),r['bytes']);self.assertEqual(hashlib.sha256(body).hexdigest(),r['sha256'])

    def test_new_live_price_sample_is_separate_from_old_100_snapshot(self):
        p=ROOT/'docs/evidence/current-price-sample'
        report=json.loads(gzip.decompress((p/'report.json.gz').read_bytes()))
        sources={(r.url,r.sha256):r for r in read_bundle(ROOT/'tests/fixtures/current-price-sample')}
        self.assertEqual(report['summary']['candidates'],3);self.assertEqual(report['summary']['collected_prices'],3)
        self.assertEqual(len(sources),4);self.assertEqual(report['new_identity_get_invocations'],1)
        for row in report['companies']:
            f=row['price'];quote=sources[(f['source_url'],f['raw_sha256'])];identity=sources[(f['identity_evidence_url'],f['identity_evidence_sha256'])]
            replay=parse_price(quote,identity,cik=row['issuer_id'],symbol=row['symbol'],as_of=datetime.fromisoformat(report['generated_at']))
            self.assertEqual(replay.value,Decimal(f['value']));self.assertFalse(replay.scope_approved)
