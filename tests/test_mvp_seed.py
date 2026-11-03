"""Fresh original public bodies may seed a run; timestamps and lease safety remain."""
import json,tempfile,unittest
from dataclasses import replace
from datetime import datetime,timedelta,timezone
from pathlib import Path
from unittest.mock import patch

from equity_research.evidence_bundle import write_bundle
from equity_research.mvp import run_mvp
from equity_research.response_archive import ResponseArchive
from test_mvp import CANDIDATES,recorded_http


class MvpSeedTests(unittest.TestCase):
    def seed(self,root,age=None):
        first=root/'first'
        with patch('equity_research.response_archive.ArchivedTransport.get',new=recorded_http):
            run_mvp(CANDIDATES,state_dir=first,user_agent='Synthetic seed fixture',max_new_fields=0)
        original=ResponseArchive(first/'responses.sqlite');out=ResponseArchive(root/'seed.sqlite')
        try:
            for row in original.observations():
                response=original.get(row['url'],row['sha256'],datetime.fromisoformat(row['retrieved_at']))
                if age is not None:response=replace(response,retrieved_at=datetime.now(timezone.utc)+age)
                out.record(response)
            write_bundle(out,root/'bundle')
        finally:original.close();out.close()
        return first,root/'bundle'

    def test_fresh_seed_reuses_metadata_and_document_without_new_get_or_date_rewrite(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);first,bundle=self.seed(root)
            with patch('equity_research.response_archive.ArchivedTransport.get',side_effect=AssertionError('unexpected GET')):
                report=run_mvp(CANDIDATES,state_dir=root/'second',user_agent='Synthetic seed fixture',seed_bundles=[bundle],max_new_fields=0)
            self.assertEqual(report['pipeline']['public_transport_get_calls'],0)
            self.assertEqual(report['pipeline']['archived_transport_reuses'],2)
            self.assertEqual(report['pipeline']['seeded_public_observations'],2)
            a=json.loads((first/'metadata.json').read_text());b=json.loads((root/'second/metadata.json').read_text())
            self.assertEqual(a['companies'][0]['snapshot']['retrieved_at'],b['companies'][0]['snapshot']['retrieved_at'])
            self.assertFalse(report['mvp_accepted'])

    def test_stale_and_future_seed_bodies_do_not_suppress_real_refresh(self):
        for age in (timedelta(hours=-7),timedelta(hours=1)):
            with self.subTest(age=age),tempfile.TemporaryDirectory() as td:
                root=Path(td);_,bundle=self.seed(root,age)
                with patch('equity_research.response_archive.ArchivedTransport.get',new=recorded_http):
                    report=run_mvp(CANDIDATES,state_dir=root/'second',user_agent='Synthetic seed fixture',seed_bundles=[bundle],max_new_fields=0)
                self.assertEqual(report['pipeline']['seeded_public_observations'],0)
                self.assertEqual(report['pipeline']['seed_observations_outside_freshness'],2)
                self.assertEqual(report['pipeline']['public_transport_get_calls'],2)

    def test_seed_folder_cannot_be_used_as_writable_state_or_receive_created_files(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);_,bundle=self.seed(root);before=sorted(p.name for p in bundle.iterdir())
            for state in (bundle,bundle/'nested'):
                with self.subTest(state=state),self.assertRaises(ValueError):
                    run_mvp(CANDIDATES,state_dir=state,user_agent='Synthetic',seed_bundles=[bundle])
            self.assertEqual(sorted(p.name for p in bundle.iterdir()),before)
            self.assertFalse((bundle/'nested').exists())

    def test_invalid_bundle_checksum_fails_without_any_network(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);_,bundle=self.seed(root)
            part=bundle/'sources.jsonl.gz.part0000';part.write_bytes(part.read_bytes()+b'bad')
            with patch('equity_research.response_archive.ArchivedTransport.get',side_effect=AssertionError('unexpected GET')):
                with self.assertRaises(ValueError):run_mvp(CANDIDATES,state_dir=root/'second',user_agent='Synthetic',seed_bundles=[bundle])


    def test_cached_bodies_still_obey_transport_size_limits_without_network(self):
        from equity_research.response_archive import ArchivedTransport
        original=ArchivedTransport.__init__
        def small(self,**kwargs):
            original(self,**kwargs);self.max_bytes=10
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);_,bundle=self.seed(root)
            with patch.object(ArchivedTransport,'__init__',small),patch.object(ArchivedTransport,'get',side_effect=AssertionError('unexpected GET')):
                report=run_mvp(CANDIDATES,state_dir=root/'second',user_agent='Synthetic',seed_bundles=[bundle],max_new_fields=0)
            self.assertEqual(report['pipeline']['metadata_states'],{'invalid_data':1})
            self.assertEqual(report['pipeline']['public_transport_get_calls'],0)
            self.assertEqual(report['summary']['accepted_facts'],0)
            self.assertFalse(report['mvp_accepted'])
