"""Dated-cohort assembly is source preservation, not a new live scan."""
import copy,gzip,json,os,subprocess,sys,tempfile,unittest
from datetime import timedelta
from pathlib import Path

from equity_research.financial_cohort import assemble_financial_cohort
from test_valuation import batch,NOW,CIK


def source(cik=CIK,symbol='AAPL',hours=0,**values):
    b=batch(**values);b['generated_at']=(NOW+timedelta(hours=hours)).isoformat()
    c=b['companies'][0];c.update(symbol=symbol,issuer_id=cik)
    for f in c['fields']:
        f['query']['issuer_id']=cik;f['fact']['issuer_id']=cik
    return b

PLAN=dict(companies=[dict(symbol='AAPL',issuer_id=CIK),dict(symbol='MSFT',issuer_id='0000789019')])


class FinancialCohortTests(unittest.TestCase):
    def test_exact_identity_subset_and_original_time_value_period_trails_preserved(self):
        old=source();new=source('0000789019','MSFT',hours=1)
        original=copy.deepcopy([old,new]);merged,report=assemble_financial_cohort(PLAN,[old,new])
        self.assertEqual([c['fields'] for c in merged['companies']],[old['companies'][0]['fields'],new['companies'][0]['fields']])
        self.assertEqual([old,new],original)
        self.assertEqual(merged['generated_at'],new['generated_at'])
        self.assertEqual(report['financial_cohort']['selected_by_source'],{'1':1,'2':1})
        self.assertFalse(report['financial_cohort']['all_new_100_live_run'])
        self.assertEqual(report['financial_cohort']['mode'],'mixed_dated_inputs_no_network')
        self.assertTrue(all(c['total_score'] is None for c in report['companies']))

    def test_unrequested_old_identities_are_not_admitted(self):
        old=source('0000000001','OTHER');new=source()
        merged,report=assemble_financial_cohort(dict(companies=PLAN['companies'][:1]),[old,new])
        self.assertEqual(len(merged['companies']),1);self.assertEqual(merged['companies'][0]['symbol'],'AAPL')
        self.assertEqual(report['financial_cohort']['selected_by_source'],{'2':1})

    def test_duplicate_overlapping_inputs_and_wrong_symbols_rejected(self):
        for inputs in ([source(),source()],[source(symbol='WRONG')]):
            with self.assertRaises(ValueError):assemble_financial_cohort(PLAN,inputs)

    def test_missing_company_stays_unresolved_without_zero_fields(self):
        merged,report=assemble_financial_cohort(PLAN,[source()])
        self.assertEqual(merged['companies'][1]['fields'],[])
        self.assertEqual(merged['companies'][1]['pending_reason'],'financial_cohort_missing')
        self.assertIsNone(report['companies'][1]['total_score'])
        self.assertEqual(report['financial_cohort']['selected_by_source'],{'1':1,'missing':1})

    def test_input_approvals_points_and_rank_cannot_grant_output_approval(self):
        old=source();old['companies'][0].update(total_score=100,rank=1,investment_approved=True)
        merged,report=assemble_financial_cohort(dict(companies=PLAN['companies'][:1]),[old])
        self.assertNotIn('total_score',merged['companies'][0]);self.assertNotIn('rank',merged['companies'][0])
        self.assertIsNone(report['companies'][0]['total_score']);self.assertFalse(report['mvp_accepted'])

    def test_source_digest_changes_with_input_but_not_ordered_serialization(self):
        a=source();b=source(net_income='0');plan=dict(companies=PLAN['companies'][:1])
        _,r1=assemble_financial_cohort(plan,[a]);_,r2=assemble_financial_cohort(plan,[b])
        self.assertNotEqual(r1['financial_cohort']['sources'][0]['sha256'],r2['financial_cohort']['sources'][0]['sha256'])
        reordered=json.loads(json.dumps(a,sort_keys=True));_,r3=assemble_financial_cohort(plan,[reordered])
        self.assertEqual(r1['financial_cohort']['sources'][0]['sha256'],r3['financial_cohort']['sources'][0]['sha256'])

    def test_zero_negative_and_missing_are_preserved_as_distinct_data(self):
        for value in ('0','-100',None):
            original=source(net_income=value);merged,_=assemble_financial_cohort(dict(companies=PLAN['companies'][:1]),[original])
            rows=[f for f in merged['companies'][0]['fields'] if f['query']['field']=='net_income']
            self.assertEqual(rows[0]['fact']['value'],value) if value is not None else self.assertEqual(rows,[])

    def test_human_reports_expose_mixed_source_dates_and_escape_text(self):
        from equity_research.financial_cohort import render_cohort_markdown,render_cohort_html
        _,report=assemble_financial_cohort(PLAN,[source(),source('0000789019','MSFT',hours=1)])
        md=render_cohort_markdown(report);html=render_cohort_html(report)
        self.assertIn('Not a new live 100-company scan',md)
        self.assertIn('yeni bir canlı 100 şirket taraması değildir',html)
        report['financial_cohort']['sources'][0]['generated_at']='<script>alert(1)</script>'
        self.assertNotIn('<script>alert(1)</script>',render_cohort_html(report))

    def test_naive_source_generation_timestamp_is_not_current(self):
        b=source();b['generated_at']=NOW.replace(tzinfo=None).isoformat()
        with self.assertRaises(ValueError):assemble_financial_cohort(PLAN,[b])

    def test_cli_rebuilds_gzip_inputs_and_prevents_cohort_overwrite(self):
        root=Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as td:
            folder=Path(td);plan=folder/'candidates.json';plan.write_text(json.dumps(PLAN))
            old=folder/'old.json.gz';old.write_bytes(gzip.compress(json.dumps(source()).encode(),mtime=0))
            new=folder/'new.json';new.write_text(json.dumps(source('0000789019','MSFT',hours=1)))
            out=folder/'report.json';merged=folder/'batch.json'
            cmd=[sys.executable,'-m','equity_research','financial-cohort','--candidates',str(plan),
                '--cohort-input',str(old),'--cohort-input',str(new),'--output',str(out),'--batch-output',str(merged)]
            env={**os.environ,'PYTHONPATH':str(root/'src')}
            ran=subprocess.run(cmd,env=env,capture_output=True,text=True)
            self.assertEqual(ran.returncode,0,ran.stdout+ran.stderr)
            self.assertEqual(len(json.loads(merged.read_text())['companies']),2)
            self.assertFalse(json.loads(out.read_text())['financial_cohort']['all_new_100_live_run'])
            before=old.read_bytes();cmd[cmd.index('--batch-output')+1]=str(old)
            refused=subprocess.run(cmd,env=env,capture_output=True,text=True)
            self.assertEqual(refused.returncode,2);self.assertEqual(old.read_bytes(),before)


class RecordedFinancialCohortTests(unittest.TestCase):
    def test_mixed_hundred_rebuilds_without_modifying_source_facts_or_dates(self):
        from equity_research.cache import encode
        root=Path(__file__).resolve().parents[1]
        def read(path):return json.loads(gzip.decompress((root/path).read_bytes()))
        old=read('docs/evidence/liquidity100/batch.json.gz');new=read('docs/evidence/common-financial17/batch.json.gz')
        expected=read('docs/evidence/common-financial100/report.json.gz')
        plan=json.loads((root/'docs/evidence/common100/candidates.json').read_text())
        merged,report=assemble_financial_cohort(plan,[old,new])
        self.assertEqual(json.loads(json.dumps(report,default=encode)),expected)
        self.assertEqual(json.loads(json.dumps(merged,default=encode)),read('docs/evidence/common-financial100/batch.json.gz'))
        self.assertEqual(report['summary']['accepted_facts'],988);self.assertEqual(report['summary']['arithmetic_results'],704)
        self.assertEqual(report['financial_cohort']['selected_by_source'],{'1':83,'2':17})
        self.assertEqual(report['summary']['scored_companies'],0);self.assertFalse(report['mvp_accepted'])

    def test_all_new_accepted_facts_reextract_from_exact_three_provider_raw_sources(self):
        from dataclasses import asdict
        from datetime import datetime,date
        from equity_research.cache import encode
        from equity_research.companyfacts import SecCompanyFacts
        from equity_research.evidence_bundle import read_bundle
        from equity_research.fields import SPECS
        from equity_research.models import FactRequest
        from equity_research.nasdaq_financials import NasdaqFinancials
        from equity_research.sec import parse_directory
        from equity_research.yahoo import YahooAssets
        root=Path(__file__).resolve().parents[1]
        batch=json.loads(gzip.decompress((root/'docs/evidence/common-financial17/batch.json.gz').read_bytes()))
        all_raw=list(read_bundle(root/'tests/fixtures/common-extra-sources'))+list(read_bundle(root/'tests/fixtures/common-financial17-sources'))
        raw={(r.url,r.sha256,r.retrieved_at.isoformat()):r for r in all_raw};parsed={};counts={}
        for company in batch['companies']:
            for row in company['fields']:
                f=row['fact']
                if not f:continue
                as_of=datetime.fromisoformat(row['as_of']);query=dict(row['query']);query['period_end']=date.fromisoformat(query['period_end']);query['period_start']=date.fromisoformat(query['period_start']) if query['period_start'] else None;request=FactRequest(**query,as_of=as_of)
                source=raw[(f['source_url'],f['raw_sha256'],f.get('data_observed_at') or f['retrieved_at'])]
                if f['source']=='SEC':
                    if source.sha256 not in parsed:parsed[source.sha256]=SecCompanyFacts._parse(source,f['issuer_id'])[1]
                    actual=SecCompanyFacts(None)._extract(request,SPECS[f['field']].tag,source,parsed[source.sha256])
                else:
                    responses={source.url:source};identity=raw[(f['identity_evidence_url'],f['identity_evidence_sha256'],f['identity_observed_at'])]
                    if f['unit_evidence_url']:
                        unit=raw[(f['unit_evidence_url'],f['unit_evidence_sha256'],f['unit_observed_at'])];responses[unit.url]=unit
                    class Replay:
                        max_bytes=16000000
                        def get(self,url):return responses[url]
                    provider=(YahooAssets if f['source']=='Yahoo' else NasdaqFinancials)(Replay(),directory=parse_directory(identity),symbol=company['symbol'],clock=lambda:as_of)
                    actual=provider.fetch(request)
                self.assertEqual(json.loads(json.dumps(asdict(actual),default=encode)),f)
                counts[f['source']]=counts.get(f['source'],0)+1
        self.assertEqual(counts,{'SEC':168,'Yahoo':14,'Nasdaq':4})
        report=json.loads(gzip.decompress((root/'docs/evidence/common-financial17/report.json.gz').read_bytes()))
        self.assertTrue(report['pipeline']['all_financial_references_archived'])
        metadata=json.loads(gzip.decompress((root/'docs/evidence/common-financial17/metadata.json.gz').read_bytes()))
        self.assertEqual(len(metadata['companies']),17)

    def test_selected_new_fields_match_original_sec_documents_with_missing_input_separate(self):
        from datetime import date
        from equity_research.cache import encode
        from equity_research.concept_diagnostics import inspect_concepts
        from equity_research.evidence_bundle import read_bundle
        from equity_research.fields import SPECS
        root=Path(__file__).resolve().parents[1]
        proof=json.loads((root/'docs/evidence/common-financial17/original-checks.json').read_text())
        self.assertEqual(proof['summary'],{'matched':26,'selected_input_unavailable':1})
        raw={r.url:r for r in read_bundle(root/'tests/fixtures/common-extra-sources')}
        docs=json.loads(gzip.decompress((root/'docs/evidence/common-financial17/documents.json.gz').read_bytes()))['companies']
        by={d['symbol']:d for d in docs}
        for symbol in ('ADBE','INTU','TYL'):
            doc=by[symbol];body=raw[doc['source_evidence']['url']]
            self.assertEqual(body.sha256,doc['source_evidence']['sha256'])
            for instant in (True,False):
                rows=[c for c in proof['checks'] if c['symbol']==symbol and SPECS[c['field']].instant==instant]
                original=inspect_concepts(body.body,cik=doc['issuer_id'],concepts=[SPECS[c['field']].accounting_definition for c in rows],
                    period_start=None if instant else date.fromisoformat(doc['period']['period_start']),period_end=date.fromisoformat(doc['period']['period_end']))['concepts']
                for expected,actual in zip(rows,original):self.assertEqual(json.loads(json.dumps(actual,default=encode)),expected['original'])
