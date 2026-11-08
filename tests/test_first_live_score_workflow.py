"""Live score workflow must use real source artifacts and original score engine."""
import unittest
from pathlib import Path

FILE=Path(__file__).resolve().parents[1]/".github/workflows/first-live-score.yml"


class FirstLiveScoreWorkflowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text=FILE.read_text(encoding="utf-8")

    def test_live_source_handoff_and_main_guard(self):
        self.assertIn("workflow_run:",self.text)
        self.assertIn("workflows: ['Canlı değerleme kaynakları']",self.text)
        self.assertIn("types: [completed]",self.text)
        self.assertIn("head_branch == 'main'",self.text)
        self.assertIn("head_repository.full_name == github.repository",self.text)
        self.assertIn("conclusion == 'success'",self.text)
        self.assertIn("cancel-in-progress: false",self.text)
        self.assertIn("name: valuation-source-state",self.text)
        self.assertIn("name: live-acceptance-state",self.text)
        self.assertIn("name: live-acceptance-evidence",self.text)

    def test_financial_evidence_must_be_exactly_linked(self):
        self.assertIn("financial-source-run.json",self.text)
        self.assertIn("steps.financial.outputs.source_run",self.text)
        self.assertIn("prepare_first_score_plans.py",self.text)
        self.assertIn("--companyfacts-dir data/financial/companyfacts",self.text)
        self.assertIn("--cache-dir data/financial/companyfacts",self.text)

    def test_normal_resolver_and_official_scoring_are_used(self):
        self.assertIn("research-batch",self.text)
        self.assertIn("build_current_scores.py",self.text)
        self.assertIn("--current data/first-score-work/current.json",self.text)
        self.assertIn("--prior data/first-score-work/prior.json",self.text)
        self.assertIn("--financial-sources data/financial-evidence/live-sources",self.text)
        self.assertIn("name: first-live-score-evidence",self.text)
        self.assertIn("steps.score.outcome != 'success'",self.text)
        self.assertNotIn("git push",self.text)
        self.assertNotIn("mvp_accepted: true",self.text)


if __name__=="__main__":
    unittest.main()
