import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from equity_research.evidence_bundle import write_bundle, read_bundle
from equity_research.response_archive import ResponseArchive
from equity_research.transport import Response


class EvidenceBundleTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
        self.archive=ResponseArchive(self.root/'archive.sqlite')
        self.response=Response('https://data.sec.gov/test.json',b'{"raw":"exact bytes"}',datetime(2026,11,2,tzinfo=timezone.utc))
        self.archive.record(self.response)

    def tearDown(self):
        self.archive.close();self.temp.cleanup()

    def test_raw_bytes_url_and_observation_round_trip(self):
        m=write_bundle(self.archive,self.root/'bundle')
        r=list(read_bundle(self.root/'bundle'))
        self.assertEqual(m['observations'],1);self.assertEqual(r,[self.response])
        self.assertFalse(m['headers_stored']);self.assertFalse(m['credentials_stored'])

    def test_corrupt_part_never_yields_a_response(self):
        m=write_bundle(self.archive,self.root/'bundle')
        p=self.root/'bundle'/m['parts'][0]['file'];p.write_bytes(p.read_bytes()+b'x')
        with self.assertRaises(ValueError):next(read_bundle(self.root/'bundle'))

    def test_manifest_count_and_whole_bundle_hash_checked(self):
        for key,value in [('observations',999),('compressed_sha256','0'*64)]:
            m=write_bundle(self.archive,self.root/'bundle');m[key]=value
            (self.root/'bundle/manifest.json').write_text(json.dumps(m))
            with self.assertRaises(ValueError):list(read_bundle(self.root/'bundle'))

    def test_manifest_paths_cannot_escape_bundle(self):
        m=write_bundle(self.archive,self.root/'bundle');m['parts'][0]['file']='../secret'
        (self.root/'bundle/manifest.json').write_text(json.dumps(m))
        with self.assertRaises(ValueError):list(read_bundle(self.root/'bundle'))

    def test_bundles_are_deterministic(self):
        a=write_bundle(self.archive,self.root/'a');b=write_bundle(self.archive,self.root/'b')
        self.assertEqual(a,b)

    def test_part_size_is_bounded(self):
        for size in (-1,0,1023,1048577):
            with self.assertRaises(ValueError):write_bundle(self.archive,self.root/'b',part_bytes=size)

    def test_empty_bundle_is_not_financial_evidence(self):
        empty=ResponseArchive(self.root/'empty.sqlite')
        try:
            m=write_bundle(empty,self.root/'empty')
            self.assertEqual(m['observations'],0);self.assertEqual(list(read_bundle(self.root/'empty')),[])
        finally:empty.close()
