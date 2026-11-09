"""Canlı kabul iş akışının güvenlik ve devam sözleşmesi."""
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class LiveAcceptanceWorkflowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.body = (ROOT / '.github/workflows/live-acceptance.yml').read_text()

    def test_manual_collection_is_bounded_and_targets_exact_common100(self):
        self.assertIn('workflow_dispatch:',self.body)
        self.assertIn("cron: '17 * * * *'",self.body)
        self.assertIn('--candidates docs/evidence/common100/candidates.json',self.body)
        self.assertIn("options: ['25', '50', '100']",self.body)
        self.assertIn("options: ['250', '500', '900', '1400']",self.body)
        self.assertIn('timeout-minutes: 120',self.body)
        self.assertIn('cancel-in-progress: false',self.body)

    def test_pr_trial_uses_small_budgets_and_runs_only_in_the_same_repository(self):
        self.assertIn("github.event.pull_request.head.repo.full_name == github.repository", self.body)
        self.assertIn("github.event_name == 'pull_request' && '5' || '25'", self.body)
        self.assertIn("github.event_name == 'pull_request' && '30' || '1400'", self.body)

    def test_preflight_gates_collection_without_secrets_or_paid_provider(self):
        preflight = self.body.index('id: preflight')
        gate = self.body.index('id: source_gate')
        collection = self.body.index('id: mvp')
        self.assertLess(preflight, gate)
        self.assertLess(gate, collection)
        self.assertIn("steps.source_gate.outcome == 'success'",self.body)
        # SEC submissions suffice to try metadata. Other failed providers
        # remain explicitly unavailable in the underlying report.
        self.assertIn("required={'sec_submissions'}",self.body)
        self.assertIn("'unavailable_during_preflight':unavailable",self.body)
        self.assertNotIn("required={'sec_identity','sec_submissions','sec_companyfacts'}",self.body)
        self.assertNotIn("steps.preflight.outcome == 'success'",self.body)
        self.assertIn('live-source-preflight',self.body)
        self.assertIn("steps.preflight.outcome == 'failure'", self.body)
        self.assertIn('scripts/diagnose_sec_network.py', self.body)
        self.assertIn('sec-network-diagnostic', self.body)
        # The SEC user agent identifies the caller. Never expose it to PR jobs.
        self.assertIn("secrets.SEC_USER_AGENT",self.body)
        self.assertIn("github.event_name != 'pull_request'",self.body)
        self.assertIn("SEC_USER_AGENT GitHub Actions secret",self.body)
        self.assertNotIn('FINNHUB_API_KEY',self.body)

    def test_state_can_resume_by_exact_run_and_evidence_is_exported(self):
        for token in ('resume_run_id','actions/download-artifact@v4',
                      'run-id: ${{ steps.checkpoint.outputs.run_id }}','live-acceptance-state',
                      'scripts/export_mvp_evidence.py','live-acceptance-evidence'):
            self.assertIn(token,self.body)
        self.assertIn('actions: read',self.body)
        self.assertIn('contents: read',self.body)
        self.assertIn('retention-days: 14',self.body)

    def test_reviewed_idle_checkpoint_does_not_download_or_collect(self):
        self.assertNotIn('  push:', self.body)
        for step in ('Önceki durum dosyalarını indir', 'Dosya özetlerini SQLite kayıtlarını ve kiraları doğrula'):
            body = self.body.split(f'name: {step}', 1)[1].split('- name:', 1)[0]
            self.assertIn("steps.checkpoint.outputs.reviewed_idle != 'true'", body)
        self.assertIn("steps.verified.outputs.collect == 'true'", self.body)
