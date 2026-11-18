"""Offline contract tests for optional XBRL diagnostic probe."""
import importlib.util
from pathlib import Path
import unittest
from unittest.mock import MagicMock


PATH = Path(__file__).resolve().parents[1] / "scripts/probe_edgartools_xbrl.py"
spec = importlib.util.spec_from_file_location("probe_edgartools_xbrl", PATH)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class ProbeTests(unittest.TestCase):
    def make_company(self, matches):
        company = MagicMock()
        filing = company.get_filings.return_value.latest.return_value
        filing.accession_no = "0000000000-26-000001"
        filing.filing_date = "2026-11-10"
        query = filing.xbrl.return_value.facts.query.return_value
        query.by_concept.side_effect = lambda name: MagicMock(
            to_dataframe=lambda: [object()] * matches.get(name, 0))
        return lambda ticker: company

    def test_reports_only_observed_rows_not_scores(self):
        result = module.probe("AAPL", ["Assets", "Liabilities"],
                              company_factory=self.make_company({"Assets": 2}))
        self.assertEqual(result["results"][0]["matching_rows"], 2)
        self.assertEqual(result["results"][1]["state"], "not_found_in_probe")
        self.assertEqual(result["decision"], "manual_review_only")
        self.assertNotIn("score", result)
        self.assertEqual(result["accession"], "0000000000-26-000001")

    def test_missing_filing_fails_closed(self):
        company = MagicMock()
        company.get_filings.return_value.latest.return_value = None
        with self.assertRaisesRegex(ValueError, "No 10-K"):
            module.probe("AAPL", ["Assets"], company_factory=lambda _: company)

    def test_missing_xbrl_fails_closed(self):
        company = MagicMock()
        company.get_filings.return_value.latest.return_value.xbrl.return_value = None
        with self.assertRaisesRegex(ValueError, "no readable XBRL"):
            module.probe("AAPL", ["Assets"], company_factory=lambda _: company)


if __name__ == "__main__":
    unittest.main()
