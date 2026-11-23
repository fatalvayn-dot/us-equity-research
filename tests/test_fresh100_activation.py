"""Activation audit for the newly selected, disjoint 100 SEC issuer identities."""
import json
from pathlib import Path
import unittest

from equity_research.mvp import validate_candidates

ROOT = Path(__file__).resolve().parents[1]


class Fresh100ActivationTests(unittest.TestCase):
    def test_old_100_preserved_and_new_100_disjoint(self):
        old = validate_candidates(json.loads((ROOT / "docs/evidence/archived100/candidates-2026-11-19.json").read_text()))
        new = validate_candidates(json.loads((ROOT / "docs/evidence/common100/candidates.json").read_text()))
        self.assertEqual(len(old), 100)
        self.assertEqual(len(new), 100)
        self.assertFalse(set(x["issuer_id"] for x in old) & set(x["issuer_id"] for x in new))
        self.assertFalse(set(x["symbol"] for x in old) & set(x["symbol"] for x in new))

    def test_selection_grounded_in_real_sec_run_not_synthetic_mocks(self):
        r = json.loads((ROOT / "docs/evidence/fresh100/selection-receipt.json").read_text())
        self.assertEqual(r["run_id"], 44550896092)
        self.assertEqual(r["source_artifact_id"], 14543976278)
        self.assertEqual(r["source_artifact_digest"], "sha256:357a674b46bfcd5605e1ffd4dd2fee7ff5025edc317e7c8e68da84714f030306")
        self.assertEqual(r["overlap"], 0)
        self.assertFalse(r["participation_approved"])
        self.assertFalse(r["investment_approved"])

    def test_archived_old_checkpoint_cannot_resume_the_new_100(self):
        legacy = (ROOT / ".github/workflows/live-acceptance.yml").read_text()
        self.assertNotIn("cron: '17 * * * *'", legacy)
        self.assertIn("if: github.event_name == 'pull_request'", legacy)
        new_live = (ROOT / ".github/workflows/fresh100-isolated-live.yml").read_text()
        self.assertIn("docs/evidence/archived100/candidates-2026-11-19.json", new_live)
        self.assertIn("docs/operations/fresh100-live-request.json", new_live)
        self.assertIn("--state-dir data/fresh100/financial", new_live)
        self.assertIn("--state-dir data/fresh100/valuation", new_live)\n        self.assertIn("github.run_attempt == 1", new_live)\n        request = json.loads((ROOT / "docs/operations/fresh100-live-request.json").read_text())\n        self.assertEqual(request["requested_on"], "2026-11-23")\n        self.assertEqual(request["request_id"], "fresh100-score-handoff-20261123-1")


    def test_fresh100_publishes_minimal_same_run_score_handoff(self):
        workflow = (ROOT / ".github/workflows/fresh100-isolated-live.yml").read_text()
        self.assertIn("prepare_fresh100_score_handoff.py", workflow)
        self.assertIn("name: live-acceptance-state", workflow)
        self.assertIn("name: live-acceptance-evidence", workflow)
        self.assertIn("name: valuation-source-state", workflow)
        self.assertIn("--run-id \"$GITHUB_RUN_ID\"", workflow)
        self.assertNotIn("MAX_REVIEWED_SEQUENCE", workflow)


if __name__ == "__main__":
    unittest.main()
