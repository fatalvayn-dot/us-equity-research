"""Independent virtual portfolio ledger invariants (no real holdings or backdating)."""
import json
import unittest
from datetime import date
from decimal import Decimal
from pathlib import Path

LEDGER = Path(__file__).resolve().parents[1] / "data/analyst/independent_paper_portfolio_eur10k.json"


class IndependentPaperPortfolioTests(unittest.TestCase):
    def test_initial_cash_not_fake_fill(self):
        d = json.loads(LEDGER.read_text(encoding="utf-8"))
        self.assertFalse(d["real_money"])
        self.assertTrue(d["user_portfolio_independent"])
        self.assertTrue(d["public_no_user_holdings"])
        self.assertEqual(Decimal(d["starting_cash_eur"]), Decimal("10000"))
        self.assertEqual(d["cash_eur"], d["starting_cash_eur"])
        self.assertEqual(d["trades"], [])
        self.assertEqual(d["holdings"], [])

    def test_planned_orders_nonretroactive_and_bounded(self):
        d = json.loads(LEDGER.read_text(encoding="utf-8"))
        orders = d["pending_virtual_orders"]
        self.assertEqual(len(orders), 3)
        self.assertEqual(len({o["symbol"] for o in orders}), 3)
        reference = date.fromisoformat(d["last_reference"]["date"])
        budget_usd = Decimal(d["starting_cash_eur"]) * Decimal(d["last_reference"]["eur_usd"])
        proposed_usd = sum((Decimal(o["quantity"]) * Decimal(o["limit_price_usd"])
                           + Decimal(o["commission_usd"]) for o in orders), Decimal(0))
        self.assertLess(proposed_usd, budget_usd)
        for order in orders:
            self.assertEqual(order["state"], "planned_not_submitted")
            self.assertGreater(date.fromisoformat(order["valid_from"]), reference)
            self.assertGreaterEqual(date.fromisoformat(order["expiry"]), date.fromisoformat(order["valid_from"]))
            self.assertGreater(Decimal(order["quantity"]), 0)
            self.assertEqual(Decimal(order["commission_usd"]), Decimal("1.50"))


if __name__ == "__main__":
    unittest.main()
