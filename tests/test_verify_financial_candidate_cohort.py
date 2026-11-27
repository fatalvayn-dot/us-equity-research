import unittest

from scripts.verify_financial_candidate_cohort import verify


def rows(pairs):
    return {"companies": [{"issuer_id": cik, "symbol": symbol}
                          for cik, symbol in pairs]}


class FinancialCandidateCohortTests(unittest.TestCase):
    def test_exact_cohort_ignores_row_order_and_returns_hashes(self):
        financial = rows([("0000000001", "AAA"), ("0000000002", "BBB")])
        candidates = rows([("0000000002", "BBB"), ("0000000001", "AAA")])
        result = verify(financial, candidates, financial_bytes=b"batch", candidate_bytes=b"list")
        self.assertEqual(result["companies"], 2)
        self.assertTrue(result["cohort_match"])
        self.assertEqual(len(result["financial_sha256"]), 64)
        self.assertEqual(len(result["candidate_sha256"]), 64)

    def test_same_size_but_disjoint_cohort_fails_with_actionable_symbols(self):
        financial = rows([("0000000001", "AAA"), ("0000000002", "BBB")])
        candidates = rows([("0000000003", "CCC"), ("0000000004", "DDD")])
        with self.assertRaisesRegex(
            ValueError,
            r"finansal=2, aday=2, finansalda_fazla=2, adayda_eksik=2",
        ) as raised:
            verify(financial, candidates)
        self.assertIn("AAA,BBB", str(raised.exception))
        self.assertIn("CCC,DDD", str(raised.exception))

    def test_empty_candidate_cohort_fails_closed(self):
        with self.assertRaisesRegex(ValueError, "kohortu uyuşmuyor"):
            verify(rows([("0000000001", "AAA")]), rows([]))


if __name__ == "__main__":
    unittest.main()
