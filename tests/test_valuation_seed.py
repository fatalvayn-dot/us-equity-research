"""Imported financial sources retain original evidence and stage-specific freshness."""
import tempfile,unittest,json,subprocess,sys,os
from pathlib import Path
from datetime import timedelta
from dataclasses import replace
from unittest.mock import patch
from equity_research.evidence_bundle import write_bundle
from equity_research.response_archive import ResponseArchive
from equity_research.valuation_collection import run_collection
from test_valuation_collection import PLAN, ASOF, identity,cf,meta,filing,price,history,ROOT


class ValuationSeedTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
        self.bundle=self.root/'input';self.state=self.root/'state'
    def tearDown(self):self.temp.cleanup()
    def seed(self,responses):
        archive=ResponseArchive(self.root/'input.sqlite')
        try:
            for r in responses:archive.record(r)
            write_bundle(archive,self.bundle)
        finally:archive.close()
    def run_seed(self,**kwargs):
        with patch('urllib.request.OpenerDirector.open',side_effect=AssertionError('network forbidden')):
            return run_collection(PLAN,state_dir=self.state,user_agent='Recorded seed verification',
                                  max_new_requests=0,seed_bundles=[self.bundle],clock=lambda:ASOF,**kwargs)
    def test_complete_bundle_reuses_exact_originals_without_network_or_score(self):
        originals=[identity(),cf(),meta(),filing(),price(),history()];self.seed(originals)
        report=self.run_seed();company=report['companies'][0]
        self.assertEqual(report['summary']['new_get_invocations'],0)
        self.assertEqual(report['seed_summary']['imported_observations'],6)
        self.assertEqual(company['share_check']['status'],'verified_dated_share_class')
        self.assertEqual(company['price_check']['status'],'valid')
        self.assertEqual(company['history_check']['status'],'valid')
        self.assertFalse(report['mvp_accepted']);self.assertIsNone(company['total_score'])
        archive=ResponseArchive(self.state/'sources.sqlite')
        try:
            for r in originals:
                got=archive.get(r.url,r.sha256,r.retrieved_at)
                self.assertEqual(got,r)
        finally:archive.close()
    def test_stale_and_future_observations_do_not_enable_collection(self):
        for age in (timedelta(hours=7),-timedelta(minutes=1)):
            with self.subTest(age=age):
                self.seed([replace(identity(),retrieved_at=ASOF-age)])
                r=self.run_seed()
                self.assertEqual(r['summary']['new_get_invocations'],0)
                self.assertNotEqual(r['identity_validation']['status'],'valid')
                self.assertGreater(r['seed_summary']['outside_seed_freshness'],0)
    def test_price_keeps_fifteen_minute_gate_after_six_hour_seed_import(self):
        self.seed([identity(),cf(),meta(),filing(),replace(price(),retrieved_at=ASOF-timedelta(minutes=16)),history()])
        r=self.run_seed();self.assertEqual(r['seed_summary']['imported_observations'],6)
        self.assertEqual(r['companies'][0]['price_check']['status'],'pending_source_collection')
        self.assertEqual(r['summary']['new_get_invocations'],0)
    def test_oversized_seed_cannot_bypass_transport_limit(self):
        self.seed([identity()])
        with patch('equity_research.valuation_collection.MAX_SOURCE_BYTES',1):r=self.run_seed()
        self.assertEqual(r['seed_summary']['oversized_observations'],1)
        self.assertNotEqual(r['identity_validation']['status'],'valid')
    def test_overlapping_paths_rejected_without_modifying_bundle(self):
        self.seed([identity()]);before={p.name:p.read_bytes() for p in self.bundle.iterdir()}
        for state in (self.bundle,self.bundle/'nested',self.root):
            with self.subTest(state=state),self.assertRaises(ValueError):
                run_collection(PLAN,state_dir=state,user_agent='Seed verification',max_new_requests=0,seed_bundles=[self.bundle])
        self.assertEqual(before,{p.name:p.read_bytes() for p in self.bundle.iterdir()})
    def test_corrupt_bundle_fails_and_releases_collection_lease(self):
        self.seed([identity()]);part=next(self.bundle.glob('*.part*'));part.write_bytes(b'corrupt')
        with self.assertRaises(ValueError):self.run_seed()
        import sqlite3
        with sqlite3.connect(self.state/'run-lock.sqlite') as db:
            self.assertEqual(db.execute('select count(*) from batch_lease_v1').fetchone()[0],0)
    def test_cli_seed_option_is_not_silently_ignored(self):
        plan=self.root/'plan.json';plan.write_text(json.dumps(PLAN))
        p=subprocess.run([sys.executable,'-m','equity_research','collect-valuation-sources',
                          '--candidates',str(plan),'--state-dir',str(self.state),
                          '--user-agent','Seed verification','--max-new-requests','0',
                          '--seed-bundle',str(self.root/'missing')],
                         env={**os.environ,'PYTHONPATH':str(ROOT/'src')},capture_output=True,text=True)
        self.assertEqual(p.returncode,2)
        self.assertFalse((self.state/'report.json').exists())
