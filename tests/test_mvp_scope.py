"""Evidence collection failures cannot grant membership or block financial collection."""
import tempfile, unittest
from pathlib import Path
from datetime import timedelta
from dataclasses import replace
from equity_research.mvp_scope import collect_common_evidence
from equity_research.response_archive import ResponseArchive
from equity_research.providers import ProviderFailure, Status
from test_common_sample import sources, PLAN, ASOF


class ScopePipelineTests(unittest.TestCase):
    def run_collection(self, evidence=None, fail=False):
        evidence = sources() if evidence is None else evidence
        with tempfile.TemporaryDirectory() as tmp:
            archive=ResponseArchive(Path(tmp)/'archive.sqlite')
            for r in evidence: archive.record(r)
            mapping={r.url:r for r in evidence}; calls=[]; pulses=[]
            class Transport:
                def get(self, url):
                    calls.append(url)
                    if fail or url not in mapping: raise ProviderFailure(Status.API_ERROR)
                    archive.record(mapping[url]);return mapping[url]
            meta=[dict(status='metadata_available_legal_type_pending', annual=dict(source_url=evidence[-1].url))] if evidence else []
            def factory(hosts, **kwargs):
                if 'www.nasdaqtrader.com' in hosts:
                    self.assertEqual(kwargs.get('accept'),'text/plain')
                return Transport()
            result=collect_common_evidence(PLAN['companies'], meta, archive, factory,
                                          clock=lambda:ASOF, pulse=lambda:pulses.append(True))
            archive.close()
            return result,calls,pulses

    def test_exact_originals_join_membership_without_granting_score(self):
        result,calls,pulses=self.run_collection()
        self.assertEqual(result['summary']['selected'],1)
        self.assertTrue(result['target_sample_verified'])
        self.assertFalse(result['hundred_common_share_sample_verified'])
        self.assertFalse(result['mvp_accepted'])
        self.assertIsNone(result['companies'][0]['total_score'])
        self.assertEqual(len(calls),3);self.assertTrue(pulses)

    def test_missing_annual_metadata_skips_network_and_stays_pending(self):
        result,calls,_=self.run_collection([],True)
        self.assertEqual(result['summary']['selected'],0)
        self.assertEqual(len(result['companies']),1)
        self.assertTrue(result['collection_attempts'])
        self.assertEqual(calls,[])
        self.assertFalse(result['target_sample_verified'])

    def test_failed_refresh_does_not_redate_valid_originals(self):
        result,_,_=self.run_collection(fail=True)
        self.assertEqual(result['summary']['selected'],1)
        self.assertEqual(result['companies'][0]['filing_source']['retrieved_at'],sources()[-1].retrieved_at)
        self.assertTrue(all(a['status']=='api_error' for a in result['collection_attempts']))

    def test_stale_listing_does_not_admit_on_failed_refresh(self):
        evidence=sources()
        evidence[0]=replace(evidence[0],retrieved_at=ASOF-timedelta(days=5))
        result,_,_=self.run_collection(evidence,True)
        self.assertEqual(result['summary']['selected'],0)

    def test_wrong_registered_class_stays_blocked(self):
        evidence=sources();evidence[-1]=replace(evidence[-1],body=evidence[-1].body.replace(b'>Common Stock<',b'>Preferred Stock<'))
        result,_,_=self.run_collection(evidence)
        self.assertEqual(result['summary']['selected'],0)

    def test_missing_directories_with_valid_annual_are_bounded_and_fail_closed(self):
        result,calls,_=self.run_collection(sources()[2:],True)
        self.assertEqual(result['summary']['selected'],0)
        self.assertLessEqual(len(calls),5)
        self.assertGreater(len(calls),0)
        self.assertFalse(result['target_sample_verified'])
        self.assertTrue(all(a['status']=='api_error' for a in result['collection_attempts']))
