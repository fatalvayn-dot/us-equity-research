"""No network, no inferred periods, and exact current-candidate coverage."""
import copy
import gzip
import json
import unittest
from dataclasses import replace
from datetime import timedelta
from pathlib import Path
from unittest.mock import patch

from equity_research.cache import encode
from equity_research.comparative_replay import replay_comparisons
from test_comparative import CIK, NOW, ANNUAL, document, financial, row, PS, PE

PLAN = dict(companies=[dict(symbol='AAPL', issuer_id=CIK)])


def documents():
    doc = document()
    return [dict(companies=[dict(**PLAN['companies'][0], annual=ANNUAL, period={'caller':'ignored'},
        source_evidence=dict(url=doc.url,sha256=doc.sha256,retrieved_at=doc.retrieved_at.isoformat()))])]


def run(docs=None, responses=None, plan=None, cutoff=NOW):
    return replay_comparisons(plan or PLAN, documents() if docs is None else docs,
                              [document(),financial()] if responses is None else responses, as_of=cutoff)


class ComparativeReplayTests(unittest.TestCase):
    def test_reproducible_current_prior_operands_and_zero_network(self):
        with patch('urllib.request.OpenerDirector.open', side_effect=AssertionError('network forbidden')):
            first=run(); second=run()
        self.assertEqual(json.dumps(first,default=encode,sort_keys=True),json.dumps(second,default=encode,sort_keys=True))
        self.assertEqual(first['audit']['current_facts'],1);self.assertEqual(first['audit']['prior_facts'],1)
        calculation=first['report']['companies'][0]['calculations'][0]
        self.assertEqual(str(calculation['value']),'0.2')
        for side in ('current','prior'):
            field=first[side+'_batch']['companies'][0]['fields'][0]
            self.assertEqual([(a['source'],a['status']) for a in field['attempts']], [('Yahoo','unsupported_field'),('SEC','valid')])
            self.assertEqual(field['fact']['retrieved_at'],NOW.isoformat())
            self.assertEqual(field['fact']['raw_sha256'],financial().sha256)
        self.assertFalse(first['report']['mvp_accepted']);self.assertFalse(first['audit']['freshness_accepted'])
        self.assertEqual(first['audit']['new_http_requests'],0)

    def test_missing_and_unready_candidates_stay_visible_on_both_sides(self):
        plan=copy.deepcopy(PLAN);plan['companies'].append(dict(symbol='MSFT',issuer_id='0000789019'))
        result=run(plan=plan)
        self.assertEqual(result['report']['summary']['companies'],2)
        for side in ('current','prior'):
            missing=result[side+'_batch']['companies'][1]
            self.assertEqual(missing['fields'],[])
            self.assertEqual(missing['pending_reason'],'annual_period_unresolved')
        self.assertIsNone(result['report']['companies'][1]['total_score'])
        self.assertEqual(result['audit']['deferred'][0]['status'],'verified_annual_period_unavailable')

    def test_no_comparable_rows_means_no_fabricated_or_empty_batch_crash(self):
        result=run(responses=[document(),financial([row()])])
        self.assertEqual(result['audit']['current_facts'],0)
        self.assertEqual(result['audit']['plan_states'],{'prior_period_unresolved':1})
        self.assertEqual(result['report']['summary']['arithmetic_results'],0)

    def test_duplicate_document_cohorts_and_wrong_symbols_rejected(self):
        with self.assertRaises(ValueError):run(docs=documents()+documents())
        docs=documents();docs[0]['companies'][0]['symbol']='WRONG'
        with self.assertRaises(ValueError):run(docs=docs)

    def test_conflicting_same_url_timestamp_rejected_and_identical_duplicates_allowed(self):
        with self.assertRaises(ValueError):run(responses=[document(),financial(),financial([row(value=121)])])
        self.assertEqual(run(responses=[document(),financial(),financial()])['audit']['prior_facts'],1)

    def test_exact_original_hash_time_required_and_future_not_used(self):
        for change in ('hash','time'):
            docs=documents();e=docs[0]['companies'][0]['source_evidence']
            e['sha256']='0'*64 if change=='hash' else e['sha256']
            if change=='time':e['retrieved_at']=(NOW-timedelta(seconds=1)).isoformat()
            result=run(docs=docs)
            self.assertEqual(result['audit']['current_facts'],0)
            self.assertEqual(result['audit']['deferred'][0]['status'],'original_source_unavailable_at_cutoff')
        result=run(responses=[document(),replace(financial(),retrieved_at=NOW+timedelta(seconds=1))])
        self.assertEqual(result['audit']['current_facts'],0)

    def test_latest_asof_snapshot_used_not_later_observation(self):
        future=replace(financial([row(value=999),row(PS,PE,100)]),retrieved_at=NOW+timedelta(seconds=1))
        self.assertEqual(str(run(responses=[document(),future,financial()])['report']['companies'][0]['calculations'][0]['value']),'0.2')

    def test_wrong_issuer_in_body_and_currency_cannot_produce_comparison(self):
        bad=replace(financial(),body=financial().body.replace(b'320193',b'789019'))
        result=run(responses=[document(),bad])
        self.assertEqual(result['audit']['deferred'][0]['status'],'symbol_mismatch')
        usd=financial();bad=replace(usd,body=usd.body.replace(b'USD',b'EUR'))
        self.assertEqual(run(responses=[document(),bad])['audit']['current_facts'],0)

    def test_naive_cutoff_rejected(self):
        with self.assertRaises(ValueError):run(cutoff=NOW.replace(tzinfo=None))

    def test_absent_digest_or_naive_document_timestamp_cannot_wildcard_match(self):
        for change in ('hash','time'):
            docs=documents();e=docs[0]['companies'][0]['source_evidence']
            if change=='hash':e['sha256']=None
            else:e['retrieved_at']=NOW.replace(tzinfo=None).isoformat()
            with self.assertRaises(ValueError):run(docs=docs)

    def test_old_recordings_replay_without_becoming_live_fresh_data(self):
        result=run(cutoff=NOW+timedelta(days=2))
        self.assertEqual(result['audit']['prior_facts'],1)
        self.assertFalse(result['audit']['freshness_accepted'])
        self.assertEqual(result['current_batch']['companies'][0]['fields'][0]['fact']['retrieved_at'],NOW.isoformat())

    def test_cli_refuses_output_inside_source_bundle_before_writing(self):
        import os,subprocess,sys,tempfile
        root=Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as td:
            folder=Path(td);bundle=folder/'bundle';bundle.mkdir()
            p=folder/'candidates.json';p.write_text(json.dumps(PLAN))
            doc=folder/'documents.json';doc.write_text('{}')
            command=[sys.executable,str(root/'scripts/replay_common_comparisons.py'),
                '--candidates',str(p),'--documents',str(doc),'--sources',str(bundle),
                '--as-of',NOW.isoformat(),'--output',str(bundle/'overwrite')]
            r=subprocess.run(command,env={**os.environ,'PYTHONPATH':str(root/'src')},capture_output=True,text=True)
            self.assertEqual(r.returncode,2);self.assertIn('separate',r.stderr)
            self.assertFalse((bundle/'overwrite').exists())


class RecordedCommonComparisonTests(unittest.TestCase):
    def test_exact_100_plan_and_all_paired_operands_reproduce_growth(self):
        from equity_research.comparative import build_comparative_report
        root=Path(__file__).resolve().parents[1]
        folder=root/'docs/evidence/common-comparative100'
        def read(name):
            b=(folder/name).read_bytes();return json.loads(gzip.decompress(b) if name.endswith('.gz') else b)
        current,prior=read('current-batch.json.gz'),read('prior-batch.json.gz')
        report=build_comparative_report(current,prior);audit=read('audit.json')
        candidates=json.loads((root/'docs/evidence/common100/candidates.json').read_text())['companies']
        wanted=[(r['symbol'],r['issuer_id']) for r in candidates]
        for side in (current,prior):
            self.assertEqual([(r['symbol'],r['issuer_id']) for r in side['companies']],wanted)
        self.assertEqual(report['summary'],dict(companies=100,arithmetic_results=514,scored_companies=0))
        self.assertEqual(audit['current_facts'],534);self.assertEqual(audit['prior_facts'],534)
        self.assertEqual(audit['calculation_states'],{'calculated_arithmetic_only':514,'nonpositive_base':20})
        self.assertEqual(json.loads(json.dumps(report['companies'],default=encode)),read('report.json.gz')['companies'])
        self.assertEqual(audit['plan_states'],{'ready_for_ordered_collection':96,'prior_period_unresolved':1})
        self.assertEqual({r['symbol'] for r in audit['deferred']},{'GEV','SNDK','BLK'})
        originals=read('original-checks.json')
        self.assertEqual(originals['summary'],{'matched':202});self.assertEqual(originals['companies'],17)
        self.assertEqual(len(originals['checks']),202)
        self.assertFalse(report['mvp_accepted'])

    def test_actual_new_annual_bodies_reproduce_both_period_values(self):
        from datetime import date
        from decimal import Decimal
        from equity_research.concept_diagnostics import inspect_concepts
        from equity_research.evidence_bundle import read_bundle
        root=Path(__file__).resolve().parents[1]
        folder=root/'docs/evidence/common-comparative100'
        checks=json.loads((folder/'original-checks.json').read_text())['checks']
        selected=[c for c in checks if c['symbol'] in ('ADBE','INTU','TYL')]
        needed={c['original_source_url'] for c in selected};bodies={}
        for response in read_bundle(root/'tests/fixtures/common-extra-sources'):
            if response.url in needed:bodies[response.url]=response
        count=0
        for symbol in ('ADBE','INTU','TYL'):
            for side in ('current','prior'):
                group=[c for c in selected if c['symbol']==symbol and c['side']==side]
                self.assertTrue(group);first=group[0];source=bodies[first['original_source_url']]
                self.assertEqual(source.sha256,first['original_sha256'])
                original=inspect_concepts(source.body,cik=first['issuer_id'],
                    concepts=[c['original']['concept'] for c in group],
                    period_start=date.fromisoformat(first['period_start']),period_end=date.fromisoformat(first['period_end']))
                for check,raw in zip(group,original['concepts']):
                    self.assertEqual(raw['status'],'exact_original_value')
                    self.assertEqual(Decimal(raw['value']),Decimal(check['selected_value']))
                    count+=1
        self.assertEqual(count,36)
