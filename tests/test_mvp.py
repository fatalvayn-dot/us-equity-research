import gzip
import json
import tempfile
import unittest
import sqlite3
import io
from contextlib import redirect_stdout
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

from equity_research.batch import BatchStore, RunBusy
from equity_research.mvp import run_mvp, financial_plan, validate_candidates, archive_coverage
from equity_research.providers import ProviderFailure, Status
from equity_research.reporting import build_report
from equity_research.response_archive import ResponseArchive
from equity_research.transport import Response

ROOT=Path(__file__).resolve().parents[1]
CIK='0000320193'
CANDIDATES=dict(companies=[dict(symbol='AAPL',issuer_id=CIK)])


def metadata():
    rows=json.loads((ROOT/'docs/evidence/sample100-submissions-live.json').read_text())['companies']
    return [next(r for r in rows if r['issuer_id']==CIK)]


def recorded_http(transport,url):
    mapping={f'https://data.sec.gov/submissions/CIK{CIK}.json':ROOT/f'tests/fixtures/submissions/CIK{CIK}.json.gz',
        f'https://data.sec.gov/api/xbrl/companyfacts/CIK{CIK}.json':ROOT/'tests/fixtures/companyfacts-aapl.json.gz',
        'https://www.sec.gov/files/company_tickers_exchange.json':ROOT/'tests/fixtures/sec-directory-recorded.json'}
    row=next(r for r in json.loads((ROOT/'docs/evidence/annual-document-batch.json').read_text())['companies'] if r['issuer_id']==CIK)
    mapping[row['source_evidence']['url']]=ROOT/row['source_evidence']['fixture']
    if 'nasdaqtrader.com' in url:
        from test_nasdaq import response
        name='nasdaqlisted' if 'nasdaqlisted.txt' in url else 'otherlisted'
        now=datetime.now(timezone.utc)
        source=response(name,footer='File Creation Time: '+now.strftime('%m%d%Y%H:%M'))
        result=Response(url,source.body,now);transport.archive.record(result);return result
    if url not in mapping:raise ProviderFailure(Status.API_ERROR)
    p=mapping[url];body=gzip.decompress(p.read_bytes()) if p.suffix=='.gz' else p.read_bytes()
    response=Response(url,body,datetime.now(timezone.utc));transport.archive.record(response)
    return response


def metadata_http(transport,url):
    cik=url.removeprefix('https://data.sec.gov/submissions/CIK').removesuffix('.json')
    symbol={'0000320193':'AAPL','0000789019':'MSFT'}[cik]
    recent={key:[] for key in ('accessionNumber','form','filingDate','reportDate',
                               'primaryDocument','acceptanceDateTime')}
    body=json.dumps(dict(cik=int(cik),name=symbol,tickers=[symbol],
        entityType='operating',sic='0000',sicDescription='Test',fiscalYearEnd='1231',
        filings=dict(recent=recent,files=[]))).encode()
    response=Response(url,body,datetime.now(timezone.utc));transport.archive.record(response)
    return response


class MvpTests(unittest.TestCase):
    def test_cli_sqlite_failure_is_safe_and_not_acceptance(self):
        from equity_research.__main__ import main
        with tempfile.TemporaryDirectory() as tmp:
            candidates=Path(tmp)/'candidates.json';candidates.write_text(json.dumps(CANDIDATES))
            argv=['equity-research','mvp-run','--candidates',str(candidates),'--user-agent','Synthetic fixture','--state-dir',tmp]
            output=io.StringIO()
            with patch('sys.argv',argv),patch('equity_research.mvp.run_mvp',side_effect=sqlite3.OperationalError('private-error-detail')),redirect_stdout(output):
                with self.assertRaises(SystemExit) as exit_info:main()
            self.assertEqual(exit_info.exception.code,2)
            result=json.loads(output.getvalue());self.assertEqual(result['error_type'],'OperationalError')
            self.assertFalse(result['mvp_accepted']);self.assertNotIn('private-error-detail',output.getvalue())

    def test_recorded_end_to_end_pipeline_archives_and_reports(self):
        with tempfile.TemporaryDirectory() as tmp, patch('equity_research.response_archive.ArchivedTransport.get',new=recorded_http):
            report=run_mvp(CANDIDATES,state_dir=tmp,user_agent='Synthetic offline fixture replay')
            self.assertEqual(report['summary']['companies'],1)
            self.assertIn('common_share_evidence',report['companies'][0])
            self.assertIn('common_share_summary',report['pipeline'])
            self.assertTrue((Path(tmp)/'common-share-evidence.json').exists())
            self.assertIn('Adi hisse kanıtı:',(Path(tmp)/'report.md').read_text())
            self.assertGreater(report['summary']['accepted_facts'],0)
            self.assertTrue(report['pipeline']['all_financial_references_archived'])
            self.assertEqual(report['summary']['scored_companies'],0)
            self.assertEqual(report['report_generation_network_requests'],0)
            self.assertNotIn('new_network_requests',report)
            self.assertFalse(report['companies'][0]['sector_profile']['sector_model_supported'])
            for name in ('metadata.json','documents.json','plan.json','batch.json','report.json','report.md','archive-coverage.json'):
                self.assertTrue((Path(tmp)/name).exists())

    def test_immediate_resume_has_zero_public_transport_calls(self):
        with tempfile.TemporaryDirectory() as tmp, patch('equity_research.response_archive.ArchivedTransport.get',new=recorded_http):
            first=run_mvp(CANDIDATES,state_dir=tmp,user_agent='Synthetic offline fixture replay')
            with patch('equity_research.response_archive.ArchivedTransport.get',side_effect=AssertionError('unexpected network')):
                second=run_mvp(CANDIDATES,state_dir=tmp,user_agent='Synthetic offline fixture replay')
            self.assertEqual(second['pipeline']['public_transport_get_calls'],0)
            self.assertEqual(first['summary']['accepted_facts'],second['summary']['accepted_facts'])

    def test_old_exact_document_keeps_period_with_zero_download_budget(self):
        with tempfile.TemporaryDirectory() as tmp, patch('equity_research.response_archive.ArchivedTransport.get',new=recorded_http):
            run_mvp(CANDIDATES,state_dir=tmp,user_agent='Synthetic offline fixture replay')
            old=(datetime.now(timezone.utc)-timedelta(days=30)).isoformat()
            with sqlite3.connect(Path(tmp)/'documents.sqlite') as db:
                db.execute('UPDATE filing_documents_v1 SET retrieved_at=?',(old,))
            with patch('equity_research.response_archive.ArchivedTransport.get',side_effect=AssertionError('unexpected network')):
                result=run_mvp(CANDIDATES,state_dir=tmp,user_agent='Synthetic offline fixture replay',max_new_documents=0,max_new_fields=0)
            docs=json.loads((Path(tmp)/'documents.json').read_text())
            self.assertEqual(docs['summary']['reused_documents'],1)
            self.assertIn('period',docs['companies'][0])
            self.assertEqual(docs['companies'][0]['source_evidence']['retrieved_at'],old)
            self.assertFalse(docs['scope_approved'])
            self.assertEqual(result['summary']['scored_companies'],0)
            self.assertEqual(result['pipeline']['public_transport_get_calls'],0)

    def test_duplicate_candidates_rejected_before_network(self):
        with self.assertRaises(ValueError):validate_candidates(dict(companies=CANDIDATES['companies']*2))

    def test_invalid_identity_or_outside_mvp_count_rejected(self):
        for value in (dict(companies=[]),dict(companies=[dict(symbol='AAPL',issuer_id='320193')]),dict(companies=[dict(symbol=' AAPL',issuer_id=CIK)])):
            with self.assertRaises(ValueError):validate_candidates(value)

    def test_all_work_bounds_checked_before_network(self):
        for changes in (dict(max_new_metadata=-1),dict(max_new_metadata=101),
                        dict(max_new_documents=-1),dict(max_new_documents=101),dict(max_new_fields=-1)):
            with tempfile.TemporaryDirectory() as tmp, self.assertRaises(ValueError):
                run_mvp(CANDIDATES,state_dir=tmp,user_agent='Synthetic',**changes)

    def test_metadata_request_budget_pauses_cleanly_and_resumes_from_cache(self):
        candidates=dict(companies=[dict(symbol='AAPL',issuer_id='0000320193'),
                                   dict(symbol='MSFT',issuer_id='0000789019')])
        with tempfile.TemporaryDirectory() as tmp, patch(
                'equity_research.response_archive.ArchivedTransport.get',new=metadata_http):
            first=run_mvp(candidates,state_dir=tmp,user_agent='Synthetic fixture',
                          max_new_metadata=1,max_new_documents=0,max_new_fields=0)
            self.assertEqual(first['status'],'metadata_collection_paused')
            self.assertEqual(first['metadata_processed'],1)
            self.assertEqual(first['new_metadata_requests'],1)
            self.assertFalse(first['mvp_accepted'])
            self.assertTrue((Path(tmp)/'metadata-progress.json').is_file())
            self.assertFalse((Path(tmp)/'report.json').exists())
            second=run_mvp(candidates,state_dir=tmp,user_agent='Synthetic fixture',
                           max_new_metadata=1,max_new_documents=0,max_new_fields=0)
            self.assertEqual(second['pipeline']['requested_candidates'],2)
            self.assertEqual(second['pipeline']['public_transport_get_calls'],1)
            self.assertFalse((Path(tmp)/'metadata-progress.json').exists())
            lock=BatchStore(Path(tmp)/'run-lock.sqlite')
            owner=lock.acquire(datetime.now(timezone.utc),timedelta(minutes=15))
            lock.release(owner);lock.close()

    def test_no_document_start_only_queries_instants(self):
        plan,missing,deferred=financial_plan(metadata(),dict(companies=[]))
        self.assertEqual(plan['companies'][0]['fields'],['assets','liabilities','current_assets','current_liabilities','cash_equivalents'])
        self.assertIsNone(plan['companies'][0]['period_start']);self.assertEqual(len(deferred[CIK]),9)
        self.assertEqual(missing,[])

    def test_exact_document_start_enables_duration_queries(self):
        row=metadata()[0];end=row['annual']['report_end']
        docs=dict(companies=[dict(issuer_id=CIK,period=dict(issuer_id=CIK,period_start='2024-09-29',period_end=end))])
        plan,_,deferred=financial_plan([row],docs)
        self.assertEqual(len(plan['companies'][0]['fields']),14)
        self.assertTrue({'revenue','revenue_total','net_income','profit_loss','capital_expenditure','productive_asset_cash_payments'}.issubset(plan['companies'][0]['fields']))
        self.assertEqual(deferred,{})

    def test_mismatched_document_end_rejected(self):
        docs=dict(companies=[dict(issuer_id=CIK,period=dict(issuer_id=CIK,period_start='2024-09-29',period_end='2020-01-01'))])
        with self.assertRaises(ValueError):financial_plan(metadata(),docs)

    def test_missing_metadata_and_annual_are_unattempted_not_zeros(self):
        for status,annual,reason in [('api_error',None,'metadata_unavailable'),('symbol_mismatch',None,'symbol_mismatch'),('metadata_available_legal_type_pending',None,'no_annual_in_recent_window')]:
            row=metadata()[0];row.update(status=status,annual=annual)
            plan,missing,_=financial_plan([row],dict(companies=[]))
            self.assertEqual(plan['companies'],[]);self.assertEqual(missing[0]['pending_reason'],reason)
            r=build_report(dict(schema_version=1,generated_at=datetime.now(timezone.utc).isoformat(),companies=missing))
            self.assertEqual(r['summary']['accepted_facts'],0);self.assertEqual(r['companies'][0]['status'],'period_unresolved')
            self.assertIsNone(r['companies'][0]['total_score'])

    def test_full_metadata_failure_still_writes_a_report_and_releases_lock(self):
        with tempfile.TemporaryDirectory() as tmp, patch('equity_research.response_archive.ArchivedTransport.get',side_effect=ProviderFailure(Status.API_ERROR)):
            r=run_mvp(CANDIDATES,state_dir=tmp,user_agent='Synthetic offline error')
            self.assertEqual(r['pipeline']['period_unresolved_companies'],1)
            self.assertEqual(r['summary']['accepted_facts'],0)
            self.assertFalse(r['pipeline']['all_financial_references_archived'])
            lock=BatchStore(Path(tmp)/'run-lock.sqlite');owner=lock.acquire(datetime.now(timezone.utc),timedelta(minutes=15));lock.release(owner);lock.close()

    def test_parallel_run_cannot_overwrite_active_state(self):
        with tempfile.TemporaryDirectory() as tmp:
            lock=BatchStore(Path(tmp)/'run-lock.sqlite');owner=lock.acquire(datetime.now(timezone.utc),timedelta(minutes=15))
            try:
                with self.assertRaises(RunBusy):run_mvp(CANDIDATES,state_dir=tmp,user_agent='Synthetic')
            finally:lock.release(owner);lock.close()

    def test_zero_work_bound_never_infers_duration(self):
        with tempfile.TemporaryDirectory() as tmp, patch('equity_research.response_archive.ArchivedTransport.get',new=recorded_http):
            r=run_mvp(CANDIDATES,state_dir=tmp,user_agent='Synthetic fixture replay',max_new_documents=0,max_new_fields=0)
            self.assertEqual(r['pipeline']['deferred_duration_fields'],9)
            self.assertEqual(r['summary']['accepted_facts'],0)

    def test_archive_coverage_requires_actual_matching_observation(self):
        b=json.loads((ROOT/'docs/evidence/archived-eight-financial.json').read_text())
        with tempfile.TemporaryDirectory() as tmp:
            archive=ResponseArchive(Path(tmp)/'archive.sqlite')
            try:
                coverage=archive_coverage(b,archive)
                self.assertEqual(coverage['financial_facts'],43);self.assertFalse(coverage['all_references_archived'])
            finally:archive.close()
