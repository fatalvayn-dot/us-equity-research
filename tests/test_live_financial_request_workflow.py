"""Live SEC collection remains dispatch-only; request workflow is narrowly triggered."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
LIVE = ROOT / ".github/workflows/live-acceptance.yml"
REQUEST = ROOT / ".github/workflows/financial-refresh-request.yml"


class FinancialRequestTriggerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.live = LIVE.read_text(encoding="utf-8")
        cls.request = REQUEST.read_text(encoding="utf-8")

    def test_push_only_triggers_protected_dispatcher(self):
        self.assertNotIn("  push:", self.live)
        self.assertIn("  push:\n    branches: [main]\n    paths: ['docs/operations/financial-collection-request.json']", self.request)
        self.assertIn("  workflow_dispatch:", self.live)
        self.assertNotIn("  schedule:\n    - cron: '17 * * * *'", self.live)
        self.assertIn("if: github.event_name == 'pull_request'", self.live)

    def test_dispatch_guard_binds_reviewed_financial_state(self):
        self.assertIn("expected_parent_run_id", self.request)
        self.assertIn("expected_parent_sha256", self.request)
        self.assertIn("single_reviewed_financial_refresh", self.request)
        self.assertIn("investment_orders", self.request)
        self.assertIn("MAX_REVIEWED_SEQUENCE", self.request)
        self.assertIn("gh workflow run live-acceptance.yml", self.request)
        self.assertIn("--field max_new_documents=25 --field max_new_fields=1400", self.request)
        self.assertIn("actions: write", self.request)
        self.assertIn("cancel-in-progress: false", self.request)

    def test_original_collection_still_enforces_checkpoint(self):
        for token in ("scripts/live_checkpoint.py select",
                      "scripts/live_checkpoint.py verify",
                      "scripts/live_checkpoint.py seal",
                      "secrets.SEC_USER_AGENT",
                      "steps.source_gate.outcome == 'success'"):
            self.assertIn(token, self.live)
        self.assertIn("github.event_name != 'pull_request' && steps.checkpoint.outputs.reviewed_idle != 'true'", self.live)
        self.assertIn("cancel-in-progress: false", self.live)
        self.assertNotIn("git push", self.live)


if __name__ == "__main__":
    unittest.main()
