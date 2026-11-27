import unittest
from pathlib import Path


class ValuationCohortGuardWorkflowTests(unittest.TestCase):
    def test_cohort_guard_runs_before_source_download_and_external_collection(self):
        workflow = Path(".github/workflows/valuation-live.yml").read_text()
        guard = workflow.index("python -m scripts.verify_financial_candidate_cohort")
        source_download = workflow.index("- name: Doğrulanmış finansal kaynak paketini indir")
        collection = workflow.index("python -m equity_research collect-valuation-sources")
        self.assertLess(guard, source_download)
        self.assertLess(guard, collection)
        self.assertIn("data/valuation-financial/batch.json", workflow)
        self.assertIn("docs/evidence/common100/candidates.json", workflow)


if __name__ == "__main__":
    unittest.main()
