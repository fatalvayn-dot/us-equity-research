"""Synthetic interruption/durability contracts; not company acceptance evidence."""
import json
import tempfile
import unittest
from dataclasses import replace
from datetime import date,datetime,timedelta,timezone
from decimal import Decimal
from pathlib import Path

from equity_research.batch import BatchRunner,BatchStore,CompanyTask,RunBusy,digest,packed
from equity_research.models import Fact,FactQuery,Source
from equity_research.providers import Resolver

NOW=datetime(2026,11,1,23,30,tzinfo=timezone.utc)


def company(cik='0000320193',symbol='AAPL',**changes):
    queries=tuple(FactQuery(cik,field,None,date(2026,9,30),'USD','currency','us-gaap:'+concept)
                  for field,concept in [('assets','Assets'),('liabilities','Liabilities')])
    return replace(CompanyTask(symbol,cik,queries),**changes)


class Clock:
    def __init__(self):self.now=NOW
    def __call__(self):return self.now


class Factory:
    def __init__(self,clock):self.clock=clock;self.calls=[];self.providers=0;self.interrupt_at=None;self.missing=False;self.observed=None
    def __call__(self,task):
        self.providers+=1;outer=self
        class Provider:
            source=Source.YAHOO
            def fetch(self,request):
                outer.calls.append((task.symbol,request.field))
                if outer.interrupt_at==len(outer.calls):raise KeyboardInterrupt()
                if outer.missing:return None
                stamp=outer.observed or outer.clock()
                return Fact(request.issuer_id,request.field,Decimal(123),Source.YAHOO,None,request.period_end,'USD','currency',stamp,stamp,request.accounting_definition,'https://example.org/synthetic')
        return Resolver([Provider()],clock=self.clock)


class BatchTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.path=Path(self.tmp.name)/'checkpoint.sqlite'
        self.store=BatchStore(self.path);self.clock=Clock();self.factory=Factory(self.clock)
        self.runner=BatchRunner(self.store,self.factory,clock=self.clock)
    def tearDown(self):self.store.close();self.tmp.cleanup()

    def test_bounded_run_restart_skips_saved_fields(self):
        tasks=(company(),company('0000789019','MSFT'))
        first=self.runner.run(tasks,max_new_fields=1)
        self.assertEqual(first['summary']['field_states'],{'collected':1,'not_started':3})
        self.store.close();self.store=BatchStore(self.path)
        runner=BatchRunner(self.store,self.factory,clock=self.clock)
        second=runner.run(tasks)
        self.assertEqual(second['summary']['new_fields'],3)
        self.assertEqual(second['summary']['reused_fields'],1)
        calls=len(self.factory.calls);providers=self.factory.providers
        third=runner.run(tasks)
        self.assertEqual(third['summary']['new_fields'],0)
        self.assertEqual(third['summary']['reused_fields'],4)
        self.assertEqual((len(self.factory.calls),self.factory.providers),(calls,providers))

    def test_keyboard_interruption_preserves_prior_field_and_releases_lease(self):
        self.factory.interrupt_at=2
        with self.assertRaises(KeyboardInterrupt):self.runner.run([company()])
        self.factory.interrupt_at=None
        result=self.runner.run([company()])
        self.assertEqual(result['summary']['reused_fields'],1)
        self.assertEqual(result['summary']['new_fields'],1)

    def test_scope_never_approved_by_complete_data_or_unit_tests(self):
        result=self.runner.run([company()])
        self.assertEqual(result['companies'][0]['readiness'],'data_complete_scope_pending')
        self.assertFalse(result['investment_approved'])
        self.assertFalse(result['hundred_company_accepted'])
        with self.assertRaises(ValueError):company(scope_status='verified')

    def test_out_of_scope_never_constructs_provider(self):
        result=self.runner.run([company(scope_status='out_of_scope',scope_reason='verified ETF')])
        self.assertEqual(self.factory.providers,0)
        self.assertEqual(result['summary']['field_states'],{'out_of_scope':2})

    def test_failed_sources_retry_only_after_delay(self):
        self.factory.missing=True
        first=self.runner.run([company()]);self.assertEqual(first['summary']['field_states'],{'pending_data':2})
        self.factory.missing=False
        second=self.runner.run([company()]);self.assertEqual(second['summary']['new_fields'],0)
        self.clock.now+=timedelta(minutes=5)
        third=self.runner.run([company()]);self.assertEqual(third['summary']['field_states'],{'collected':2})

    def test_bounded_retries_cannot_starve_unattempted_companies(self):
        tasks=(company(),company('0000789019','MSFT'))
        self.factory.missing=True
        for _ in range(4):
            result=self.runner.run(tasks,max_new_fields=1)
            self.assertEqual(result['summary']['new_fields'],1)
            self.assertEqual([c['symbol'] for c in result['companies']],['AAPL','MSFT'])
            self.clock.now+=timedelta(minutes=6)
        self.assertEqual(self.factory.calls,[('AAPL','assets'),('AAPL','liabilities'),
                                             ('MSFT','assets'),('MSFT','liabilities')])
        self.runner.run(tasks,max_new_fields=1)
        self.assertEqual(self.factory.calls[-1],('AAPL','assets'))
        self.clock.now+=timedelta(minutes=6)
        self.runner.run(tasks,max_new_fields=1)
        self.assertEqual(self.factory.calls[-1],('AAPL','liabilities'))

    def test_bounded_expired_facts_do_not_starve_never_attempted_fields(self):
        self.runner.run([company()],max_new_fields=1)
        self.clock.now+=timedelta(hours=7)
        result=self.runner.run([company()],max_new_fields=1)
        self.assertEqual(self.factory.calls,[('AAPL','assets'),('AAPL','liabilities')])
        self.assertEqual([f['state'] for f in result['companies'][0]['fields']],
                         ['not_started','collected'])

    def test_bounded_work_preserves_cooldown_and_skips_excluded_scope(self):
        self.factory.missing=True
        self.runner.run([company()])
        self.factory.calls.clear()
        result=self.runner.run([company(),company('0000789019','MSFT',
                               scope_status='out_of_scope',scope_reason='verified ETF')],max_new_fields=1)
        self.assertEqual(self.factory.calls,[])
        self.assertEqual(result['summary']['reused_fields'],2)
        self.assertEqual(result['summary']['new_fields'],0)

    def test_expiry_uses_original_evidence_not_checkpoint_time(self):
        self.factory.observed=NOW-timedelta(hours=5)
        self.runner.run([company()]);self.clock.now+=timedelta(hours=2);self.factory.observed=None
        result=self.runner.run([company()])
        self.assertEqual(result['summary']['new_fields'],2)
        self.assertEqual(result['summary']['reused_fields'],0)

    def test_newly_returned_stale_fact_does_not_count_as_complete(self):
        self.factory.observed=NOW-timedelta(hours=7)
        result=self.runner.run([company()])
        self.assertEqual(result['summary']['field_states'],{'stale_data':2})
        self.assertEqual(result['companies'][0]['readiness'],'pending_fields_and_scope')

    def test_checksum_corruption_is_detected_and_requeried(self):
        task=company();self.runner.run([task]);key=self.runner.key(task,task.queries[0])
        with self.store.db:self.store.db.execute("UPDATE batch_fields_v1 SET payload=payload||'broken' WHERE key=?",(key,))
        result=self.runner.run([task])
        self.assertEqual(result['summary']['new_fields'],1)
        self.assertEqual(result['checkpoint_events'][0]['event'],'invalid_checkpoint_checksum_or_json')

    def test_semantic_corruption_rejected_even_with_matching_checksum(self):
        task=company();self.runner.run([task]);key=self.runner.key(task,task.queries[0])
        data=self.store.read(key);data['fact']['issuer_id']='0000789019';payload=packed(data)
        with self.store.db:self.store.db.execute('UPDATE batch_fields_v1 SET payload=?,checksum=? WHERE key=?',(payload,digest(payload),key))
        result=self.runner.run([task])
        self.assertEqual(result['summary']['new_fields'],1)
        self.assertEqual(result['checkpoint_events'][0]['event'],'invalid_checkpoint_semantics')

    def test_policy_or_query_change_does_not_reuse_incompatible_fact(self):
        self.runner.run([company()])
        changed=BatchRunner(self.store,self.factory,clock=self.clock,policy_version='new-rules')
        self.assertEqual(changed.run([company()])['summary']['new_fields'],2)
        c=company();q=replace(c.queries[0],currency='EUR');c=replace(c,queries=(q,))
        self.assertNotEqual(self.runner.key(c,q),self.runner.key(company(),company().queries[0]))

    def test_company_failure_is_sanitized_and_does_not_stop_other_company(self):
        good=self.factory
        def factory(task):
            if task.symbol=='AAPL':raise RuntimeError('api_key=synthetic-secret')
            return good(task)
        runner=BatchRunner(self.store,factory,clock=self.clock)
        result=runner.run([company(),company('0000789019','MSFT')])
        self.assertEqual(result['summary']['field_states'],{'collection_error':2,'collected':2})
        self.assertNotIn('synthetic-secret',json.dumps(result))

    def test_live_fact_mismatching_query_is_not_checkpointed_as_success(self):
        class Bad:
            def resolve_current(self,q):
                from equity_research.providers import Resolution
                return Resolution(Fact(q.issuer_id,q.field,Decimal(1),Source.YAHOO,None,q.period_end,'EUR','currency',NOW,NOW,q.accounting_definition,'https://example.org/synthetic'),(),NOW)
        result=BatchRunner(self.store,lambda task:Bad(),clock=self.clock).run([company()])
        self.assertEqual(result['summary']['field_states'],{'collection_error':2})

    def test_concurrent_worker_cannot_issue_duplicate_queries(self):
        owner=self.store.acquire(NOW,timedelta(minutes=15));other=BatchStore(self.path)
        try:
            with self.assertRaises(RunBusy):BatchRunner(other,self.factory,clock=self.clock).run([company()])
            self.assertEqual(self.factory.providers,0)
        finally:other.close();self.store.release(owner)

    def test_expired_owner_cannot_overwrite_new_owner(self):
        owner=self.store.acquire(NOW,timedelta(minutes=1));other=BatchStore(self.path)
        try:
            replacement=other.acquire(NOW+timedelta(minutes=2),timedelta(minutes=15))
            with self.assertRaises(RunBusy):self.store.write('key',{},owner,NOW+timedelta(minutes=2),timedelta(minutes=15))
            other.release(replacement)
        finally:other.close()

    def test_duplicate_company_or_query_rejected_before_network(self):
        with self.assertRaises(ValueError):self.runner.run([company(),company()])
        with self.assertRaises(ValueError):company(queries=(company().queries[0],)*2)
        self.assertEqual(self.factory.providers,0)

    def test_hundred_synthetic_companies_are_not_acceptance(self):
        tasks=[company(str(i).zfill(10),'S'+str(i)) for i in range(1,101)]
        result=self.runner.run(tasks)
        self.assertEqual(result['summary']['field_states'],{'collected':200})
        self.assertFalse(result['hundred_company_accepted'])


class PlanAndCliTests(unittest.TestCase):
    def plan(self):
        return {"schema_version":1,"companies":[{"symbol":"AAPL","issuer_id":"0000320193",
            "period_end":"2025-09-27","fields":["assets","net_income"],"period_start":"2024-09-29"}]}

    def test_plan_exact_instant_duration_and_no_approval(self):
        from equity_research.batch import load_plan
        task=load_plan(self.plan())[0]
        self.assertIsNone(task.queries[0].period_start)
        self.assertEqual(task.queries[1].period_start,date(2024,9,29))
        self.assertEqual(task.scope_status,"pending_scope")

    def test_plan_rejects_missing_dates_unknown_fields_and_duplicates(self):
        from equity_research.batch import load_plan
        for change in ({"period_start":None},{"fields":["ebitda"]},{"fields":["assets","assets"]},{"scope_status":"verified"}):
            payload=self.plan();payload["companies"][0].update(change)
            with self.assertRaises((ValueError,KeyError,TypeError)):load_plan(payload)

    def test_cli_zero_budget_never_creates_http_and_persists_readable_report(self):
        import sys
        from unittest.mock import patch
        from equity_research.__main__ import main
        with tempfile.TemporaryDirectory() as tmp:
            plan=Path(tmp)/"plan.json";output=Path(tmp)/"report.json"
            plan.write_text(json.dumps(self.plan()))
            argv=["equity-research","research-batch","--user-agent","Synthetic test contact", "--plan",str(plan),
                  "--checkpoint",str(Path(tmp)/"db.sqlite"),"--output",str(output),"--max-new-fields","0"]
            with patch.object(sys,"argv",argv),patch("equity_research.__main__.HttpTransport",side_effect=AssertionError("no HTTP")):
                with self.assertRaises(SystemExit) as exit:main()
            self.assertEqual(exit.exception.code,2)
            report=json.loads(output.read_text())
            self.assertEqual(report["summary"]["field_states"],{"not_started":2})
            self.assertFalse(report["hundred_company_accepted"])

    def test_factory_identity_failure_retains_typed_status(self):
        from equity_research.providers import ProviderFailure,Status
        def bad(task):raise ProviderFailure(Status.SYMBOL_MISMATCH)
        with tempfile.TemporaryDirectory() as tmp:
            store=BatchStore(Path(tmp)/"db.sqlite")
            try:report=BatchRunner(store,bad,clock=lambda:NOW).run([company()])
            finally:store.close()
        self.assertEqual(report["companies"][0]["fields"][0]["failure_status"],"symbol_mismatch")
        self.assertEqual(report["companies"][0]["fields"][0]["attempts"],[])
