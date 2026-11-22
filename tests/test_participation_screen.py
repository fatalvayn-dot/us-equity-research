"""Stage-six participation research gates: synthetic facts, no real certification."""
from copy import deepcopy
import unittest

from equity_research.participation_screen import RULES, assess_participation


AS_OF = "2026-11-19T12:00:00+00:00"
KEY = "SEC:0000320193"


def proof(issuer_key=KEY):
    return {
        "issuer_key": issuer_key, "url": "https://data.sec.gov/api/xbrl/companyfacts/CIK0000320193.json",
        "raw_sha256": "a" * 64,
        "published_at": "2026-11-10T14:00:00+00:00",
        "retrieved_at": "2026-11-11T09:00:00+00:00",
    }


def method():
    # Synthetic hypotheses only. These numbers have NOT been attributed to
    # an actual Islamic index/AAOIFI standard or made production defaults.
    names = {
        "interest_debt": ("interest_bearing_debt", "total_assets", "0.33"),
        "interest_cash_securities": ("cash_interest_securities", "total_assets", "0.33"),
        "impermissible_income": ("nonpermitted_income", "gross_revenue", "0.05"),
    }
    return {
        "standard_id": "SYNTHETIC_TEST_ONLY", "version": "fictional-v1",
        "reviewed": True, "effective_from": "2026-01-01",
        "max_statement_age_days": 365,
        "source": {**proof(), "url": "https://example.org/fictional-test-only"},
        "ratios": {name: {
            "numerator_definition": specs[0],
            "denominator_definition": specs[1],
            "max_ratio": specs[2],
        } for name, specs in names.items()},
    }


def candidate():
    rules = method()["ratios"]
    return {
        "issuer_key": KEY, "symbol": "SYNTH", "instrument_type": "common_share",
        "instrument_source": proof(),
        "sector": {"industry": "nonfinancial", "sec_sic": "3674", "source": proof()},
        "activities": {"conclusion": "permitted",
                       "all_reported_segments_reviewed": True,
                       "source": proof()},
        "ratios": {name: {
            "numerator": "1" if name == "impermissible_income" else "10",
            "denominator": "100",
            "currency": "USD", "period_end": "2026-09-30",
            "numerator_definition": rules[name]["numerator_definition"],
            "denominator_definition": rules[name]["denominator_definition"],
            "numerator_source": proof(), "denominator_source": proof(),
        } for name in RULES},
    }


class ParticipationScreenTests(unittest.TestCase):
    def test_all_synthetic_evidence_complete_grants_research_only(self):
        got = assess_participation(candidate(), method(), as_of=AS_OF)
        self.assertEqual(got["status"], "kosullu_esik_gecisi")
        self.assertEqual(set(got["ratios"]), set(RULES))
        self.assertEqual(got["review_reasons"], [])
        self.assertEqual(got["blockers"], [])
        for key in ("qualified_for_investment", "shariah_certified",
                    "investment_approved", "eligible_for_automatic_order"):
            self.assertIs(got[key], False)
        self.assertIs(got["no_live_source_verification"], True)

    def test_explicit_two_screen_method_can_pass_research_only(self):
        # This is a synthetic schema-compatibility test, NOT S&P approval.
        policy = method()
        policy["ratios"].pop("interest_cash_securities")
        policy["not_applicable_rules"] = {
            "interest_cash_securities": "not_applicable_in_reviewed_methodology"}
        row = candidate()
        result = assess_participation(row, policy, as_of=AS_OF)
        self.assertEqual(result["status"], "kosullu_esik_gecisi")
        self.assertEqual(result["applied_rules"],
                         ["impermissible_income", "interest_debt"])
        self.assertEqual(result["non_applicable_rules"],
                         ["interest_cash_securities"])
        self.assertFalse(result["investment_approved"])
        self.assertTrue(result["no_live_source_verification"])

    def test_missing_or_misdeclared_cash_exception_never_passes(self):
        policy = method()
        policy["ratios"].pop("interest_cash_securities")
        for change in (None, {}, {"interest_cash_securities": "review_pending"}):
            row = deepcopy(policy)
            if change is not None:
                row["not_applicable_rules"] = change
            result = assess_participation(candidate(), row, as_of=AS_OF)
            self.assertEqual(result["status"], "bilinmiyor")
            self.assertIn("reviewed_standard_evidence_missing",
                          result["review_reasons"])
            self.assertFalse(result["investment_approved"])

    def test_missing_policy_and_limits_never_grant_eligibility(self):
        for changed in (None, {}, {"standard_id": "SYNTHETIC_TEST_ONLY"}):
            with self.subTest(policy=changed):
                got = assess_participation(candidate(), changed, as_of=AS_OF)
                self.assertEqual(got["status"], "bilinmiyor")
                self.assertIn("reviewed_standard_evidence_missing", got["review_reasons"])
                self.assertFalse(got["investment_approved"])

    def test_banking_and_insurance_are_hard_veto_even_if_metrics_pass(self):
        for sector in ({"industry": "banking", "sec_sic": "6021"},
                       {"industry": "insurance", "sec_sic": "6331"},
                       {"industry": "nonfinancial", "sec_sic": "6411"}):
            row = candidate()
            row["sector"].update(sector)
            with self.subTest(sector=sector):
                got = assess_participation(row, method(), as_of=AS_OF)
                self.assertEqual(got["status"], "uygunsuz")
                self.assertIn("permanent_banking_insurance_exclusion", got["blockers"])

    def test_prohibited_business_activity_overrides_other_missing_values(self):
        row = candidate()
        row["activities"]["conclusion"] = "prohibited"
        row["ratios"].pop("interest_debt")
        got = assess_participation(row, method(), as_of=AS_OF)
        self.assertEqual(got["status"], "uygunsuz")
        self.assertIn("prohibited_business_activity", got["blockers"])
        self.assertIn("interest_debt_unverified_or_incompatible", got["review_reasons"])

    def test_threshold_excess_is_disqualifying_not_filled_with_missing_zero(self):
        for key in RULES:
            row = candidate()
            row["ratios"][key]["numerator"] = "80"
            with self.subTest(key=key):
                got = assess_participation(row, method(), as_of=AS_OF)
                self.assertEqual(got["status"], "uygunsuz")
                self.assertIn(key + "_exceeds_standard_threshold", got["blockers"])

    def test_published_after_cutoff_never_passes(self):
        for site in ("sector", "activities", "instrument_source"):
            row = candidate()
            if site == "sector":
                row["sector"]["source"]["retrieved_at"] = "2026-11-20T00:00:00+00:00"
            elif site == "activities":
                row["activities"]["source"]["published_at"] = "2026-11-20T00:00:00+00:00"
                row["activities"]["source"]["retrieved_at"] = "2026-11-20T01:00:00+00:00"
            else:
                row["instrument_source"]["retrieved_at"] = "2026-11-20T01:00:00+00:00"
            with self.subTest(source=site):
                got = assess_participation(row, method(), as_of=AS_OF)
                self.assertEqual(got["status"], "bilinmiyor")

    def test_missing_security_class_and_investment_vehicles_need_review(self):
        for cls in ("etf", "reit", "fund", "bdc", "unknown", None):
            row = candidate()
            row["instrument_type"] = cls
            with self.subTest(cls=cls):
                got = assess_participation(row, method(), as_of=AS_OF)
                self.assertEqual(got["status"], "bilinmiyor")
                self.assertIn("special_instrument_review_required", got["review_reasons"])
        row = candidate()
        row.pop("instrument_source")
        self.assertEqual(assess_participation(row, method(), as_of=AS_OF)["status"], "bilinmiyor")

    def test_business_coverage_is_required_even_when_activity_label_permitted(self):
        row = candidate()
        row["activities"]["all_reported_segments_reviewed"] = False
        got = assess_participation(row, method(), as_of=AS_OF)
        self.assertEqual(got["status"], "bilinmiyor")
        self.assertIn("business_segment_coverage_unverified", got["review_reasons"])

    def test_wrong_accounting_basis_currency_period_or_source_issuer_is_unknown(self):
        updates = (
            ("denominator_definition", "total_market_cap"),
            ("period_end", "2024-01-01"),
            ("currency", "US-D"),
            ("numerator", "NaN"),
            ("denominator", "0"),
            ("numerator", 0.1),
        )
        for key, value in updates:
            row = candidate()
            row["ratios"]["interest_debt"][key] = value
            with self.subTest(key=key, value=value):
                self.assertEqual(assess_participation(row, method(), as_of=AS_OF)["status"],
                                 "bilinmiyor")
        row = candidate()
        row["ratios"]["impermissible_income"]["numerator_source"]["issuer_key"] = "KAP:OTHER"
        self.assertEqual(assess_participation(row, method(), as_of=AS_OF)["status"], "bilinmiyor")

    def test_future_or_unreviewed_threshold_standard_never_passes(self):
        for key, value in (("reviewed", False),
                           ("effective_from", "2026-12-01"),
                           ("max_statement_age_days", 0)):
            r = method()
            r[key] = value
            with self.subTest(key=key):
                got = assess_participation(candidate(), r, as_of=AS_OF)
                self.assertEqual(got["status"], "bilinmiyor")
        r = method()
        r["ratios"]["interest_debt"]["max_ratio"] = "1.01"
        self.assertEqual(assess_participation(candidate(), r, as_of=AS_OF)["status"], "bilinmiyor")

    def test_wrong_issuer_or_naive_cutoff_is_refused(self):
        row = candidate()
        row["issuer_key"] = "noncanonical"
        with self.assertRaises(ValueError):
            assess_participation(row, method(), as_of=AS_OF)
        with self.assertRaises(ValueError):
            assess_participation(candidate(), method(), as_of="2026-11-19T12:00:00")


if __name__ == "__main__":
    unittest.main()
