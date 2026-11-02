import unittest
from equity_research.quality import Observation, first_valid_field, validate_observation


class QualityTests(unittest.TestCase):
    def setUp(self):
        self.good = Observation("AAPL", "revenue", "100", "SEC", "2025-09-30", "USD", "2026-11-02")

    def test_valid(self):
        self.assertEqual(str(validate_observation(self.good, "AAPL")), "100")

    def test_other_ticker(self):
        self.assertIsNone(validate_observation(self.good, "MSFT"))

    def test_first_valid(self):
        bad = Observation("MSFT", "revenue", "999", "Yahoo", "2025-09-30", "USD", "2026-11-02")
        self.assertEqual(first_valid_field([bad, self.good], "AAPL", "revenue")[0].source, "SEC")

    def test_missing_is_not_zero(self):
        self.assertIsNone(first_valid_field([], "AAPL", "revenue"))

    def test_nonfinite(self):
        bad = Observation("AAPL", "revenue", "NaN", "SEC", "2025-09-30", "USD", "2026-11-02")
        self.assertIsNone(validate_observation(bad, "AAPL"))


if __name__ == "__main__":
    unittest.main()
