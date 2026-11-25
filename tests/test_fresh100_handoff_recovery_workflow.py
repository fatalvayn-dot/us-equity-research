import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/fresh100-handoff-recovery.yml"
SCORE_WORKFLOW = ROOT / ".github/workflows/first-live-score.yml"


class Fresh100HandoffRecoveryWorkflowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = WORKFLOW.read_text()
        cls.score = SCORE_WORKFLOW.read_text()

    def test_recovery_is_manual_main_only_and_never_rerunnable(self):
        self.assertIn("workflow_dispatch:", self.text)
        self.assertNotIn("  push:", self.text)
        self.assertIn("github.ref == 'refs/heads/main' && github.run_attempt == 1", self.text)
        self.assertIn("cancel-in-progress: false", self.text)

    def test_only_pinned_existing_artifact_is_downloaded(self):
        self.assertIn("source_run_id')!=45187005935", self.text)
        self.assertIn("source_artifact_id')!=14825474340", self.text)
        self.assertIn("source_artifact_digest')!='sha256:42db775", self.text)
        self.assertIn("remote.get('workflow_run',{}).get('head_sha')", self.text)
        self.assertIn('gh run download "$SOURCE_RUN"', self.text)
        self.assertNotIn("SEC_USER_AGENT", self.text)
        self.assertNotIn("collect-valuation-sources", self.text)
        self.assertNotIn("mvp-run", self.text)

    def test_artifact_lookup_consumes_output_in_a_later_step(self):
        source = self.text.split("        id: source\n", 1)[1].split("\n      - name:", 1)[0]
        self.assertNotIn("steps.source.outputs", source)
        self.assertNotIn("gh api", source)
        self.assertIn("ARTIFACT_ID: ${{ steps.source.outputs.artifact_id }}", self.text)
        self.assertIn(': "${ARTIFACT_ID:?Kaynak artifact kimliği boş}"', self.text)
        self.assertIn('gh api "repos/$REPO/actions/artifacts/$ARTIFACT_ID"', self.text)

    def test_recovery_publishes_archived_replay_without_live_score_trigger(self):
        for name in ("live-acceptance-state", "live-acceptance-evidence",
                     "valuation-source-state"):
            self.assertIn(f"name: {name}", self.text)
        triggers = self.score.split('    workflows:', 1)[1].split('\n', 1)[0]
        self.assertNotIn('Fresh100 aynı-kohort artifact kurtarma', triggers)
        self.assertIn('python -m scripts.replay_fresh100_archive', self.text)
        self.assertIn('name: fresh100-archived-score-replay', self.text)
        self.assertIn('"Fresh100 aynı-kohort artifact kurtarma"', self.score)
        self.assertIn('if [ "$TRIGGER_ATTEMPT" != "1" ]; then', self.score)


if __name__ == "__main__":
    unittest.main()
