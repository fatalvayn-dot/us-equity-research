"""Live valuation workflow keeps the first MVP acceptance gate unchanged."""
import unittest
from pathlib import Path

WORKFLOW = Path(__file__).resolve().parents[1] / ".github/workflows/valuation-live.yml"


class ValuationLiveWorkflowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = WORKFLOW.read_text(encoding="utf-8")

    def test_manual_main_only_and_bounded_requests(self):
        self.assertIn("workflow_dispatch:", self.text)
        self.assertNotIn("  schedule:", self.text)
        self.assertIn("github.ref == 'refs/heads/main'", self.text)
        self.assertIn("options: ['0', '51', '100', '250', '501']", self.text)
        self.assertIn("cancel-in-progress: false", self.text)

    def test_requires_approved_source_artifact_and_secret(self):
        self.assertIn("live-acceptance-evidence", self.text)
        self.assertIn("SEC_USER_AGENT", self.text)
        self.assertIn("run-id: ${{ inputs.source_run_id }}", self.text)
        self.assertIn("run-id: ${{ inputs.valuation_resume_run_id }}", self.text)
        self.assertIn("name: valuation-source-state", self.text)
        self.assertIn("data/valuation-import/live-sources/manifest.json", self.text)
        self.assertIn("--seed-bundle data/valuation-import/live-sources", self.text)

    def test_writes_separate_evidence_without_score_or_trade(self):
        self.assertIn("--state-dir data/valuation-current", self.text)
        self.assertIn("name: valuation-source-state", self.text)
        self.assertIn("retention-days: 90", self.text)
        self.assertNotIn("score-report", self.text)
        self.assertNotIn("git push", self.text)
        self.assertNotIn("mvp_accepted: true", self.text)


if __name__ == "__main__":
    unittest.main()
