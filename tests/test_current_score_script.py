"""Portable score report export and source separation, using synthetic inputs."""
import gzip,json,os,subprocess,sys,tempfile,unittest
from pathlib import Path

from equity_research.cache import encode
from equity_research.evidence_bundle import write_bundle
from equity_research.response_archive import ResponseArchive
from test_scoring import financial,comparisons,companyfacts,metadata,filing,identity,price,history,ASOF

ROOT=Path(__file__).resolve().parents[1]


class CurrentScoreScriptTests(unittest.TestCase):
    def test_cli_creates_auditable_portable_reports_without_network(self):
        with tempfile.TemporaryDirectory() as td:
            folder=Path(td);sources=folder/'sources';archive=ResponseArchive(':memory:')
            try:
                for r in [companyfacts(),metadata(),filing(),identity(),price(),history()]:archive.record(r)
                write_bundle(archive,sources)
            finally:archive.close()
            batches=[financial(),*comparisons()]
            for name,batch in zip(('financial','current','prior'),batches):
                (folder/(name+'.json.gz')).write_bytes(gzip.compress(json.dumps(batch,default=encode).encode(),mtime=0))
            out=folder/'out';out.mkdir()
            original_manifest=(sources/'manifest.json').read_bytes()
            (out/'report.json.gz').symlink_to(sources/'manifest.json')
            cmd=[sys.executable,str(ROOT/'scripts/build_current_scores.py'),'--sources',str(sources),'--output',str(out),'--as-of',ASOF.isoformat()]
            for name in ('financial','current','prior'):cmd+=['--'+name,str(folder/(name+'.json.gz'))]
            result=subprocess.run(cmd,env={**os.environ,'PYTHONPATH':str(ROOT/'src')},capture_output=True,text=True)
            self.assertEqual(result.returncode,0,result.stdout+result.stderr)
            self.assertEqual((sources/'manifest.json').read_bytes(),original_manifest)
            self.assertFalse((out/'report.json.gz').is_symlink())
            report=json.loads(gzip.decompress((out/'report.json.gz').read_bytes()))
            self.assertEqual(report['summary']['scored_companies'],1)
            self.assertFalse(report['mvp_accepted']);self.assertEqual(report['new_network_requests'],0)
            self.assertIn('yeniden toplandığı anlamına gelmez',(out/'report.html').read_text())
            manifest=json.loads((out/'manifest.json').read_text());self.assertFalse(manifest['mvp_accepted'])
            self.assertEqual(manifest['input_provenance'],report['input_provenance'])
            import hashlib
            for name,digest in manifest['files'].items():self.assertEqual(hashlib.sha256((out/name).read_bytes()).hexdigest(),digest)

    def test_output_in_source_bundle_rejected_before_any_source_read(self):
        import importlib.util
        spec=importlib.util.spec_from_file_location('current_score_script',ROOT/'scripts/build_current_scores.py')
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        with tempfile.TemporaryDirectory() as td:
            sources=Path(td)/'sources';sources.mkdir()
            with self.assertRaises(ValueError):module.build(financial=Path(td)/'missing',current='x',prior='y',sources=sources,output=sources/'out',as_of=ASOF)
            self.assertFalse((sources/'out').exists())
