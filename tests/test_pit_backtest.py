"""Offline, synthetic-only tests: neither scores nor real historical returns."""
from copy import deepcopy
from decimal import Decimal
import unittest

from equity_research.pit_backtest import audit_eur_roundtrip


def example():
    # Invented numbers purely to verify timing and arithmetic.
    return dict(
        symbol="TEST", currency="USD", universe_snapshot_verified=True,
        corporate_actions_verified=True,
        decision_at="2024-01-03T12:00:00+00:00",
        signal_public_at="2024-01-02T23:00:00+00:00",
        universe_snapshot_public_at="2024-01-02T23:30:00+00:00",
        entry_at="2024-01-04T21:30:00+00:00",
        entry_quote_public_at="2024-01-04T21:00:00+00:00",
        entry_fx_public_at="2024-01-04T21:00:00+00:00",
        benchmark_entry_public_at="2024-01-04T21:00:00+00:00",
        exit_at="2024-03-04T21:30:00+00:00",
        exit_quote_public_at="2024-03-04T21:00:00+00:00",
        exit_fx_public_at="2024-03-04T21:00:00+00:00",
        benchmark_exit_public_at="2024-03-04T21:00:00+00:00",
        shares="5", entry_price_usd="100", exit_price_usd="110",
        entry_usd_per_eur="1.10", exit_usd_per_eur="1.05",
        benchmark_entry_usd="400", benchmark_exit_usd="430",
        buy_fee_usd="1.50", sell_fee_usd="1.50",
    )


class PitEurRoundtripTests(unittest.TestCase):
    def test_exact_eur_cash_flow_and_comparable_commission(self):
        report = audit_eur_roundtrip(example())
        start = (Decimal("500") + Decimal("1.5")) / Decimal("1.1")
        end = (Decimal("550") - Decimal("1.5")) / Decimal("1.05")
        self.assertEqual(Decimal(report["cost_eur"]), start)
        self.assertEqual(Decimal(report["proceeds_eur"]), end)
        net = (end / start - 1) * 100
        bench_end = (Decimal("500") / Decimal("400") * Decimal("430")
                     - Decimal("1.5")) / Decimal("1.05")
        bench = (bench_end / start - 1) * 100
        self.assertEqual(Decimal(report["net_return_pct"]), net)
        self.assertEqual(Decimal(report["benchmark_net_return_pct"]), bench)
        self.assertEqual(Decimal(report["active_return_percentage_points"]), net-bench)
        self.assertTrue(report["not_a_real_strategy_backtest"])

    def test_rejects_future_published_financial_and_13f_signals(self):
        for key in ("signal_public_at", "universe_snapshot_public_at"):
            row = example()
            row[key] = "2024-01-05T00:00:00+00:00"
            with self.subTest(field=key), self.assertRaisesRegex(ValueError, "future information"):
                audit_eur_roundtrip(row)

    def test_future_prices_and_fx_not_allowed(self):
        for key in ("entry_quote_public_at", "entry_fx_public_at",
                    "benchmark_entry_public_at"):
            row = example()
            row[key] = "2024-01-05T21:00:00+00:00"
            with self.subTest(field=key), self.assertRaisesRegex(ValueError, "after entry"):
                audit_eur_roundtrip(row)
        for key in ("exit_quote_public_at", "exit_fx_public_at",
                    "benchmark_exit_public_at"):
            row = example()
            row[key] = "2024-03-05T21:00:00+00:00"
            with self.subTest(field=key), self.assertRaisesRegex(ValueError, "after exit"):
                audit_eur_roundtrip(row)

    def test_rejects_missing_universe_and_corporate_action_confirmation(self):
        for key in ("universe_snapshot_verified", "corporate_actions_verified"):
            row = example()
            row[key] = False
            with self.subTest(field=key), self.assertRaises(ValueError):
                audit_eur_roundtrip(row)

    def test_rejects_lookahead_in_trade_sequence_and_timezone(self):
        row = example()
        row["entry_at"] = row["decision_at"]
        with self.assertRaisesRegex(ValueError, "decision must precede"):
            audit_eur_roundtrip(row)
        row = example()
        row["signal_public_at"] = "2024-01-02T23:00:00"
        with self.assertRaisesRegex(ValueError, "timezone required"):
            audit_eur_roundtrip(row)

    def test_rejects_float_nan_missing_fx_zero_and_unknown_currency(self):
        for key, val in (("shares", 2.5), ("entry_price_usd", "NaN"),
                         ("exit_price_usd", "0"), ("entry_usd_per_eur", None),
                         ("sell_fee_usd", "-1"), ("entry_price_usd", "Infinity")):
            row = example()
            row[key] = val
            with self.subTest(key=key,val=val), self.assertRaises(ValueError):
                audit_eur_roundtrip(row)
        row = example()
        row["currency"] = "TRY"
        with self.assertRaisesRegex(ValueError, "USD-denominated"):
            audit_eur_roundtrip(row)


if __name__ == "__main__":
    unittest.main()
