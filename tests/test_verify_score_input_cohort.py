import unittest

from scripts.verify_score_input_cohort import verify


def company(cik, symbol):
    return {"issuer_id": cik, "symbol": symbol}


class ScoreInputCohortTests(unittest.TestCase):
    def test_exact_cohort_passes_independent_of_order(self):
        financial = {"companies": [company("0000000001", "AAA"),
                                   company("0000000002", "BBB")]}
        valuation = {"companies": list(reversed(financial["companies"]))}
        self.assertEqual(verify(financial, valuation),
                         {"companies": 2, "cohort_match": True})

    def test_different_issuer_or_symbol_fails_closed(self):
        financial = {"companies": [company("0000000001", "AAA")]}
        for valuation in (
            {"companies": [company("0000000002", "AAA")]},
            {"companies": [company("0000000001", "AAB")]},
            {"companies": []},
        ):
            with self.subTest(valuation=valuation):
                with self.assertRaisesRegex(ValueError, "kohortu uyuşmuyor"):
                    verify(financial, valuation)

    def test_duplicate_and_invalid_identity_are_rejected(self):
        duplicate = company("0000000001", "AAA")
        with self.assertRaisesRegex(ValueError, "yinelenen"):
            verify({"companies": [duplicate, duplicate]},
                   {"companies": [duplicate]})
        with self.assertRaisesRegex(ValueError, "geçersiz CIK"):
            verify({"companies": [company("1", "AAA")]},
                   {"companies": [company("1", "AAA")]})


if __name__ == "__main__":
    unittest.main()
