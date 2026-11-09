"""Gerçek veri üretmiş SEC işlerinden kontrollü değerleme devri."""
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from scripts.select_reviewed_valuation_priority import select

WORKFLOW = Path(__file__).resolve().parents[1] / ".github/workflows/valuation-live.yml"


class ValuationLiveWorkflowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = WORKFLOW.read_text(encoding="utf-8")

    def test_automatic_trigger_does_not_trust_pr_or_nonmain(self):
        self.assertNotIn("  push:", self.text)
        self.assertIn("workflow_run:", self.text)
        self.assertIn("workflows: ['Canlı 100 şirket kabulü']", self.text)
        self.assertIn("types: [completed]", self.text)
        self.assertIn("workflow_dispatch:", self.text)
        self.assertIn("  schedule:", self.text)
        self.assertIn("cron: '17 9 * * *'", self.text)
        self.assertIn('EVENT_NAME" = "schedule"', self.text)
        self.assertIn("github.ref == 'refs/heads/main'", self.text)
        self.assertIn("github.event.workflow_run.head_branch == 'main'", self.text)
        self.assertIn("github.event.workflow_run.conclusion == 'success'", self.text)
        self.assertIn("github.event.workflow_run.head_repository.full_name == github.repository", self.text)

    def test_source_artifact_presence_is_required_for_collection(self):
        self.assertIn("live-acceptance-evidence", self.text)
        self.assertIn('ARTIFACT_COUNT', self.text)
        self.assertIn("collect=false", self.text)
        self.assertIn("actions/workflows/live-acceptance.yml/runs?per_page=100", self.text)
        self.assertIn("collect=true", self.text)
        self.assertIn("docs/evidence/first-live-score-2026-11-08.json", self.text)
        self.assertIn("['financial_run_id']", self.text)
        self.assertIn("steps.select.outputs.collect == 'true'", self.text)
        self.assertIn("data/valuation-import/live-sources/manifest.json", self.text)
        self.assertIn("--seed-bundle data/valuation-import/live-sources", self.text)
        self.assertIn("run-id: ${{ steps.select.outputs.source_run }}", self.text)

    def test_recovers_prior_valuation_and_bounds_requests(self):
        self.assertIn("valuation-source-state", self.text)
        self.assertIn("steps.select.outputs.resume_run", self.text)
        self.assertIn("run-id: ${{ steps.select.outputs.resume_run }}", self.text)
        self.assertIn('select(.name == "valuation-source-state" and .expired == false)', self.text)
        self.assertIn("options: ['0', '51', '100', '250', '501']", self.text)
        self.assertIn("MAX_NEW_REQUESTS: ${{ inputs.max_new_requests || '100' }}", self.text)
        self.assertIn("cancel-in-progress: false", self.text)

    def test_priority_is_bound_to_both_run_ids_and_report_digest(self):
        with tempfile.TemporaryDirectory() as folder:
            plan = Path(folder) / 'plan.json'
            report = Path(folder) / 'report.json'
            report.write_bytes(b'reviewed report')
            plan.write_text(json.dumps(dict(financial_run_id=12, valuation_run_id=34,
                valuation_report_sha256=hashlib.sha256(report.read_bytes()).hexdigest())))
            self.assertEqual(select(plan, 12, 34, report), plan)
            self.assertIsNone(select(plan, 13, 34, report))
            self.assertIsNone(select(plan, 12, 35, report))
            self.assertIsNone(select(plan, 12, None, report))
            report.write_bytes(b'changed report')
            with self.assertRaisesRegex(ValueError, 'digest mismatch'):
                select(plan, 12, 34, report)

    def test_existing_collector_receives_only_the_bound_priority_option(self):
        self.assertIn('scripts/select_reviewed_valuation_priority.py', self.text)
        self.assertIn('--source-run "$SOURCE_RUN" "${resume_args[@]}"', self.text)
        self.assertIn('priority_args=(--priority-candidates "$priority")', self.text)
        self.assertEqual(self.text.count('python -m equity_research collect-valuation-sources'), 1)

    def test_priority_lineage_is_written_only_after_real_collection(self):
        self.assertIn('--lineage data/valuation-current/priority-lineage.json)', self.text)
        self.assertIn('select_reviewed_valuation_priority.py record', self.text)
        self.assertIn('if [ -n "$priority" ] && [ "$MAX_NEW_REQUESTS" -gt 0 ]; then', self.text)
        self.assertIn('--run-id "$GITHUB_RUN_ID"', self.text)
        self.assertIn('--report data/valuation-current/report.json', self.text)
        self.assertLess(self.text.index('collect-valuation-sources'),
                        self.text.index('select_reviewed_valuation_priority.py record'))

    def test_provenance_secrecy_and_no_score_bypass(self):
        self.assertIn("SEC_USER_AGENT", self.text)
        self.assertIn("permissions:", self.text)
        self.assertIn("contents: read", self.text)
        self.assertIn("actions: read", self.text)
        self.assertIn("--state-dir data/valuation-current", self.text)
        self.assertIn("retention-days: 90", self.text)
        self.assertNotIn("score-report", self.text)
        self.assertNotIn("git push", self.text)
        self.assertNotIn("mvp_accepted: true", self.text)
        self.assertNotIn("real-money", self.text)


if __name__ == "__main__":
    unittest.main()
