"""Archive cutoff, immutable source bindings and current-analysis separation."""
import gzip
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.replay_fresh100_archive import MODE, RecordedTransport, replay_basis, sha
from scripts.build_current_scores import build
from equity_research.cache import encode
from equity_research.evidence_bundle import write_bundle
from equity_research.providers import ProviderFailure, Status
from equity_research.response_archive import ResponseArchive
from test_scoring import ASOF, financial, comparisons, companyfacts, metadata, filing, identity, price, history


class ArchiveReplayTests(unittest.TestCase):
    def test_transport_has_no_network_fallback_and_preserves_response_time(self):
        response = companyfacts()
        transport = RecordedTransport({response.url: response})
        with patch('socket.socket', side_effect=AssertionError('network forbidden')):
            self.assertIs(transport.get(response.url), response)
            with self.assertRaises(ProviderFailure) as caught:
                transport.get('https://data.sec.gov/absent')
        self.assertEqual(caught.exception.status, Status.NOT_CONFIGURED)
        self.assertEqual(transport.get(response.url).retrieved_at, response.retrieved_at)

    def test_original_cutoff_and_hash_bindings_cannot_be_replaced(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            original = root / 'original'
            recovered = root / 'recovered'
            for path in ('scoring',):
                (original / path).mkdir(parents=True)
            files = ('financial/batch.json', 'financial/metadata.json', 'valuation/report.json',
                     'valuation/source-bundle/manifest.json', 'financial-evidence/live-sources/manifest.json')
            for name in files:
                target = recovered / name
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text('{}')
            report = dict(as_of=ASOF.isoformat(), summary={'scored_companies': 1})
            (original / 'scoring/report.json.gz').write_bytes(gzip.compress(json.dumps(report).encode()))
            manifest = dict(**report, files={'report.json.gz': sha(original / 'scoring/report.json.gz')},
                source_bundle_manifest_sha256=sha(recovered / files[3]),
                additional_financial_source_bundles=[dict(manifest_sha256=sha(recovered / files[4]))])
            (original / 'scoring/manifest.json').write_text(json.dumps(manifest))
            receipt = dict(purpose='fresh100_same_cohort_artifact_recovery', recovered_without_provider_requests=True,
                financial_batch_sha256=sha(recovered / files[0]), metadata_sha256=sha(recovered / files[1]),
                valuation_report_sha256=sha(recovered / files[2]))
            (recovered / 'valuation/cohort-handoff.json').write_text(json.dumps(receipt))
            cutoff, checked = replay_basis(original, recovered)
            self.assertEqual(cutoff, ASOF)
            self.assertEqual(checked, report)
            manifest['as_of'] = '2026-11-25T00:00:00+00:00'
            (original / 'scoring/manifest.json').write_text(json.dumps(manifest))
            with self.assertRaises(ValueError):
                replay_basis(original, recovered)
            manifest['as_of'] = ASOF.isoformat()
            (original / 'scoring/manifest.json').write_text(json.dumps(manifest))
            (recovered / files[0]).write_text('{"tampered":true}')
            with self.assertRaises(ValueError):
                replay_basis(original, recovered)

    def test_archived_report_is_labeled_and_current_ttl_stays_enforced(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            archive = ResponseArchive(':memory:')
            try:
                for response in (companyfacts(), metadata(), filing(), identity(), price(), history()):
                    archive.record(response)
                write_bundle(archive, root / 'sources')
            finally:
                archive.close()
            for name, batch in zip(('financial', 'current', 'prior'), [financial(), *comparisons()]):
                (root / (name + '.json')).write_text(json.dumps(batch, default=encode))
            args = dict(financial=root / 'financial.json', current=root / 'current.json',
                prior=root / 'prior.json', sources=root / 'sources')
            archived = build(**args, output=root / 'archived', as_of=ASOF, mode=MODE)
            self.assertEqual(archived['summary']['scored_companies'], 1)
            self.assertEqual(archived['analysis_mode'], MODE)
            for name in ('report.md', 'report.html'):
                self.assertIn('Arşiv doğrulaması', (root / 'archived' / name).read_text())
            self.assertEqual(json.loads((root / 'archived/manifest.json').read_text())['mode'], MODE)
            from datetime import timedelta
            current = build(**args, output=root / 'current-report', as_of=ASOF + timedelta(days=2))
            self.assertEqual(current['summary']['scored_companies'], 0)
            self.assertNotIn('analysis_mode', current)
            self.assertEqual(current['companies'][0]['valuation_diagnostics']['failure_detail'],
                             'stale_share_companyfacts')


if __name__ == '__main__':
    unittest.main()
