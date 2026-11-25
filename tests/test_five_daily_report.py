import unittest

from scripts.five_daily_report import render


def company(symbol, score, close, alt=None, blockers=None):
    return {"symbol": symbol, "score": score, "latest_daily_close": close, "price_as_of": "2026-11-24",
            "score_status": "scored_research_hypothesis" if score else "pending_model_inputs",
            "alternate_definitions": alt or [], "blockers": blockers or []}


class DailyReportTests(unittest.TestCase):
    def test_table_shows_scores_prices_alternates_and_never_a_target(self):
        text = render({"companies": [
            company("AAPL", "66.5", "270.1"),
            company("NVDA", "83", "180.5", [{"required_field": "revenue", "used_field": "revenue_total"}]),
            company("AMZN", None, None, blockers=["complete_financial_review_required"])]})
        self.assertIn("Skorlu: 2/3", text);self.assertIn("| AAPL | 270.1 | 2026-11-24 | 66.5 |", text)
        self.assertIn("revenue→revenue_total", text);self.assertIn("| AMZN | — | 2026-11-24 | puansız |", text)
        self.assertGreaterEqual(text.count("hesaplanmadı"), 3)
        self.assertIn("AL görüşü verilemez", text);self.assertIn("Katılım ve alım onayı: YOK", text)

    def test_pipe_in_text_cannot_break_table_and_bad_input_is_rejected(self):
        c = company("X", None, None, blockers=["a|b"])
        self.assertIn("a/b", render({"companies": [c]}))
        for bad in (None, {}, {"companies": "x"}):
            with self.assertRaises(ValueError):render(bad)


if __name__ == "__main__":
    unittest.main()
