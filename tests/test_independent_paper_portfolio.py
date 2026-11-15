"""Independent virtual portfolio: no retroactive fills, allocation, thesis and compliance gates."""
import json
import unittest
from decimal import Decimal
from pathlib import Path

LEDGER = Path(__file__).resolve().parents[1] / "data/analyst/independent_paper_portfolio_eur10k.json"


class IndependentPaperPortfolioTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = json.loads(LEDGER.read_text(encoding="utf-8"))

    def test_cash_never_fake_filled(self):
        d = self.data
        self.assertFalse(d["real_money"])
        self.assertTrue(d["user_portfolio_independent"])
        self.assertTrue(d["public_no_user_holdings"])
        self.assertEqual(Decimal(d["starting_cash_eur"]), Decimal("10000.00"))
        self.assertEqual(d["cash_eur"], d["starting_cash_eur"])
        self.assertEqual(d["trades"], [])
        self.assertEqual(d["holdings"], [])
        self.assertEqual(d["pending_virtual_orders"], [])

    def test_canceled_original_orders_unfilled(self):
        d = self.data
        self.assertEqual({x["symbol"] for x in d["cancelled_virtual_orders"]},
                         {"SPUS", "SPWO", "SPRE"})
        self.assertTrue(all(not x["filled"] for x in d["cancelled_virtual_orders"]))

    def test_allocation_and_bounded_speculation(self):
        d = self.data
        allocation = d["target_allocation_percent"]
        self.assertEqual(sum(allocation.values()), 100)
        self.assertGreaterEqual(allocation["EUR_CASH"], 10)
        self.assertLessEqual(allocation["QS"], 3)
        self.assertEqual(set(allocation) - {"EUR_CASH"},
                         {x["symbol"] for x in d["researched_targets"]})
        self.assertTrue(all(0 < x <= 20 for k, x in allocation.items() if k != "EUR_CASH"))

    def test_every_target_has_thesis_risk_buy_sell_and_source(self):
        for t in self.data["researched_targets"]:
            for key in ("thesis", "risk", "buy_rule", "sell_rule", "source", "reference_date"):
                self.assertTrue(t[key], f'{t["symbol"]}: {key}')
            self.assertEqual(t["compliance"].startswith("unverified"), True)
            self.assertGreater(Decimal(str(t["reference_close_usd"])), 0)
            self.assertEqual(t["reference_date"], "2026-11-13")
            self.assertTrue(t["source"].startswith("https://"))


if __name__ == "__main__":
    unittest.main()
