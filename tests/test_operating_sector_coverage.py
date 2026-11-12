"""Coverage and fail-closed checks for provisional operating-sector scoring."""
import json
import unittest
from pathlib import Path
from decimal import Decimal

from equity_research.scoring import build_score_report
from equity_research.sector_models import FAMILY_CODES, MODELS, PROFIT_BANDS
from equity_research.sector_policy import excluded_banking_or_insurance
from test_scoring import score, metadata, financial, comparisons, companyfacts, identity, ASOF

ROOT = Path(__file__).resolve().parents[1]


class OperatingSectorCoverageTests(unittest.TestCase):
    def test_all_recorded_pilot_sics_are_explicitly_modeled_or_excluded(self):
        recorded = json.loads((ROOT / "docs/evidence/sector-policy-replay.json").read_text())
        self.assertEqual(len(recorded["profiles"]), 100)
        for company in recorded["profiles"]:
            sic = company["evidence"]["sic_label"]
            with self.subTest(symbol=company["symbol"], sic=sic):
                self.assertTrue(sic in MODELS or excluded_banking_or_insurance(sic) or sic == "6798")
                self.assertFalse(sic in MODELS and excluded_banking_or_insurance(sic))

    def test_coverage_expands_without_approving_any_bank_insurer_or_reit(self):
        self.assertEqual(MODELS["3571"], "electronic_computers_v1")
        self.assertEqual(MODELS["3674"], "semiconductors_v1")
        self.assertEqual(MODELS["7372"], "prepackaged_software_v1")
        self.assertEqual(MODELS["7370"], "digital_services_v1")
        self.assertEqual(MODELS["2834"], "pharmaceuticals_biotech_v1")
        self.assertNotIn("6021", MODELS)
        self.assertNotIn("6331", MODELS)
        self.assertNotIn("6211", MODELS)
        self.assertNotIn("6798", MODELS)
        self.assertEqual(set(PROFIT_BANDS), set(FAMILY_CODES))
        self.assertEqual(len(MODELS), len(set(MODELS)))

    def test_software_original_threshold_is_unchanged(self):
        original = score(metadata_response=metadata(sic="7372"))["companies"][0]
        self.assertEqual(original["components"]["profitability"]["score"], Decimal(10))
        self.assertEqual(original["model_id"], "prepackaged_software_v1")

    def test_new_digital_and_pharma_hypotheses_need_all_original_evidence(self):
        for sic, family in (("7370", "digital_services_v1"), ("2834", "pharmaceuticals_biotech_v1"),
                            ("5331", "retail_and_distribution_v1")):
            with self.subTest(sic=sic):
                completed = score(metadata_response=metadata(sic=sic))["companies"][0]
                self.assertEqual(completed["model_id"], family)
                self.assertEqual(completed["status"], "scored_research_hypothesis")
                self.assertEqual(completed["components"]["profitability"]["score"],
                                 Decimal(15 if sic == "5331" else 10))
                self.assertFalse(completed["investment_approved"])

                missing_market = build_score_report(
                    financial(), *comparisons(),
                    [companyfacts(), metadata(sic=sic), identity()], as_of=ASOF
                )["companies"][0]
                self.assertIsNone(missing_market["total_score"])
                self.assertEqual(missing_market["blockers"], ["valuation_source_evidence_required"])

                missing_capex = score(
                    b=financial(capital_expenditure=None),
                    metadata_response=metadata(sic=sic)
                )["companies"][0]
                self.assertIsNone(missing_capex["total_score"])

    def test_new_registry_does_not_override_financial_sector_exclusion(self):
        for sic in ("6021", "6029", "6199", "6211", "6324", "6331"):
            c = score(metadata_response=metadata(sic=sic))["companies"][0]
            self.assertEqual(c["status"], "excluded_sector")
            self.assertIsNone(c["total_score"])
            self.assertFalse(c["investment_approved"])


if __name__ == "__main__":
    unittest.main()
