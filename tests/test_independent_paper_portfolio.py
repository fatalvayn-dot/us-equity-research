"""Three-month independent paper portfolio: final plan, no phantom fills."""
import json
import unittest
from decimal import Decimal
from pathlib import Path

LEDGER = Path(__file__).resolve().parents[1] / "data/analyst/independent_paper_portfolio_eur10k.json"


class IndependentPaperPortfolioTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.d = json.loads(LEDGER.read_text(encoding="utf-8"))

    def test_no_backfilled_orders_and_cash(self):
        d = self.d
        self.assertEqual(d["strategy_version"], 3)
        self.assertFalse(d["real_money"])
        self.assertTrue(d["user_portfolio_independent"])
        self.assertTrue(d["public_no_user_holdings"])
        self.assertEqual(Decimal(d["cash_eur"]), Decimal("10000.00"))
        self.assertEqual(d["holdings"], [])
        self.assertEqual(d["trades"], [])
        self.assertEqual(d["pending_virtual_orders"], [])

    def test_test_window_and_budget(self):
        d = self.d
        self.assertEqual(d["test_window"]["start"], "2026-11-15")
        self.assertEqual(d["test_window"]["end"], "2027-02-15")
        alloc = d["target_allocation_percent"]
        self.assertEqual(sum(alloc.values()), 100)
        self.assertEqual(alloc, d["third_plan"]["allocation"])
        self.assertEqual(set(alloc) - {"EUR_CASH"},
                         {c["symbol"] for c in d["third_plan"]["candidates"]})
        self.assertLessEqual(max(v for k, v in alloc.items() if k != "EUR_CASH"), 30)

    def test_canceled_all_previously_planned_etf_orders(self):
        self.assertEqual({x["symbol"] for x in self.d["cancelled_virtual_orders"]},
                         {"SPUS", "SPWO", "SPRE"})
        self.assertTrue(all(not x["filled"] for x in self.d["cancelled_virtual_orders"]))

    def test_every_candidate_has_risk_and_trade_gates(self):
        for candidate in self.d["third_plan"]["candidates"]:
            for key in ("thesis", "bear_case", "buy_gate", "exit_rule",
                        "participation_evidence", "source", "compliance_status"):
                self.assertTrue(candidate[key], f'{candidate["symbol"]}: {key}')
            self.assertGreater(Decimal(str(candidate["reference_price_usd"])), 0)
            self.assertEqual(candidate["reference_date"], "2026-11-13")
            self.assertTrue(candidate["source"].startswith("https://"))
            if candidate["classification"] == "equity":
                self.assertEqual(candidate["compliance_status"], "unverified_hold_cash")


if __name__ == "__main__":
    unittest.main()
