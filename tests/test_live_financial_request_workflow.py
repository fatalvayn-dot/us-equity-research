"""Only an explicit main-branch request triggers the reviewed SEC refresh."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
FILE = ROOT / ".github/workflows/live-acceptance.yml"


class FinancialRequestTriggerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.workflow = FILE.read_text(encoding="utf-8")

    def test_push_trigger_requires_exact_main_request_file(self):
        self.assertIn("  push:\n    branches: [main]\n    paths: ['docs/operations/financial-collection-request.json']", self.workflow)
        self.assertIn("  schedule:\n    - cron: '17 * * * *'", self.workflow)
        self.assertIn("  workflow_dispatch:", self.workflow)

    def test_live_collection_retains_checkpoint_verification(self):
        self.assertIn("scripts/live_checkpoint.py select", self.workflow)
        self.assertIn("scripts/live_checkpoint.py verify", self.workflow)
        self.assertIn("scripts/live_checkpoint.py seal", self.workflow)
        self.assertIn("github.event_name != 'pull_request' && steps.checkpoint.outputs.reviewed_idle != 'true'", self.workflow)
        self.assertIn("if: steps.source_gate.outcome == 'success'", self.workflow)
        self.assertIn("--max-new-fields", self.workflow)
        self.assertIn("secrets.SEC_USER_AGENT", self.workflow)
        self.assertIn("cancel-in-progress: false", self.workflow)
        self.assertNotIn("git push", self.workflow)


if __name__ == "__main__":
    unittest.main()
