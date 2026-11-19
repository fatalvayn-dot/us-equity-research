"""Smoke-test first-live-score wiring of signed raw SEC staging evidence."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


class SecScoreWorkflowWiringTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.workflow = (ROOT / ".github/workflows/first-live-score.yml").read_text()
        cls.pinning = (ROOT / "docs/operations/sec-stage1-accepted.json").read_text()

    def test_exact_immutable_sec_artifact_digest_pinned(self):
        self.assertIn("44543645240", self.workflow)
        self.assertIn("14539511083", self.workflow)
        self.assertIn("9e9221a0f4cd98faaa02508b28538f25f83d4baa9fe1982b58bfb9eaf3234576", self.workflow)
        self.assertIn("sec-stage1-original-raw-evidence", self.workflow)
        self.assertIn("640d99b08c00320f488a48cd60c75258d57ddf7d6fea86a6490b8cd718551c03", self.pinning)
        self.assertIn("999be6a1a9188eb8d085f48f1a1b25976926ca318384d0db2b0d79001cbba379", self.pinning)

    def test_no_new_network_provider_and_score_uses_sha_gate(self):
        self.assertIn("steps.financial.outputs.ready == 'true'", self.workflow)
        self.assertIn("gh run download 44543645240", self.workflow)
        self.assertIn("verify_stage1_artifact(m,raw,as_of=datetime.now(timezone.utc))", self.workflow)
        self.assertIn("STAGE1_READY: \${{ steps.sec_stage1.outputs.ready }}", self.workflow)
        self.assertIn("STAGE1_ARGS=(--sec-stage1 data/sec-stage1/verified-sec-stage1.json", self.workflow)
        self.assertIn("--sec-raw-dir data/sec-stage1", self.workflow)
        self.assertIn('--as-of "$AS_OF" "\${STAGE1_ARGS[@]}"', self.workflow)
        self.assertIn("scripts/build_current_scores.py", self.workflow)
        self.assertNotIn("query_rw", self.workflow)


if __name__ == "__main__":
    unittest.main()
