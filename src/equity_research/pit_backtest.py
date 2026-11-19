"""Point-in-time EUR return audit for *supplied evidence*, not market data.

A comparison is only calculated when timestamps, universe membership and
corporate-action evidence are explicitly present. A successful calculation
does NOT establish bias-free performance of a real stock-selection strategy.
No network, orders, provider access, or personal holdings.
"""
from datetime import datetime
from decimal import Decimal, InvalidOperation


def _time(row, field):
    value = row.get(field)
    if not isinstance(value, str):
        raise ValueError(f"{field}: explicit timestamp required")
    try:
        stamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        raise ValueError(f"{field}: invalid timestamp") from None
    if stamp.tzinfo is None or stamp.utcoffset() is None:
        raise ValueError(f"{field}: timezone required")
    return stamp


def _money(row, field):
    value = row.get(field)
    if type(value) not in (str, int, Decimal):
        raise ValueError(f"{field}: exact decimal required (no float)")
    try:
        amount = Decimal(value)
    except (InvalidOperation, TypeError):
        raise ValueError(f"{field}: invalid decimal") from None
    if not amount.is_finite() or amount <= 0:
        raise ValueError(f"{field}: finite positive amount required")
    return amount


def audit_eur_roundtrip(row):
    """Check supplied transaction and source availability; return EUR results.

    Shares must be explicitly stated and unaffected by unmodeled splits.
    USD per EUR exchange rates represent the rates actually available at each
    transaction time, not retrospective/future data.
    """
    if not isinstance(row, dict) or not isinstance(row.get("symbol"), str) or not row["symbol"]:
        raise ValueError("exact company symbol required")
    if row.get("currency") != "USD":
        raise ValueError("only USD-denominated US-equity simulations supported")
    if row.get("universe_snapshot_verified") is not True:
        raise ValueError("historical universe membership evidence required")
    if row.get("corporate_actions_verified") is not True:
        raise ValueError("corporate actions and delistings must be reviewed")
    decision = _time(row, "decision_at")
    entry = _time(row, "entry_at")
    exit_at = _time(row, "exit_at")
    if not decision < entry < exit_at:
        raise ValueError("decision must precede entry and exit")

    for field in ("signal_public_at", "universe_snapshot_public_at"):
        if _time(row, field) > decision:
            raise ValueError(f"{field}: future information at decision")
    for field in ("entry_quote_public_at", "entry_fx_public_at", "benchmark_entry_public_at"):
        if _time(row, field) > entry:
            raise ValueError(f"{field}: information published after entry")
    for field in ("exit_quote_public_at", "exit_fx_public_at", "benchmark_exit_public_at"):
        if _time(row, field) > exit_at:
            raise ValueError(f"{field}: information published after exit")

    shares = _money(row, "shares")
    entry_px = _money(row, "entry_price_usd")
    exit_px = _money(row, "exit_price_usd")
    fx_start = _money(row, "entry_usd_per_eur")
    fx_end = _money(row, "exit_usd_per_eur")
    bench_start = _money(row, "benchmark_entry_usd")
    bench_end = _money(row, "benchmark_exit_usd")
    buy_fee = _money(row, "buy_fee_usd")
    sell_fee = _money(row, "sell_fee_usd")

    entry_notional = shares * entry_px
    exit_notional = shares * exit_px
    if sell_fee >= exit_notional:
        raise ValueError("sale proceeds do not cover exit fee")
    eur_cost = (entry_notional + buy_fee) / fx_start
    eur_proceeds = (exit_notional - sell_fee) / fx_end
    if eur_cost <= 0 or eur_proceeds <= 0:
        raise ValueError("invalid EUR cash flow")

    # Benchmark gets the same entry USD notional and per-order fees.
    units_benchmark = entry_notional / bench_start
    benchmark_exit_notional = units_benchmark * bench_end
    if sell_fee >= benchmark_exit_notional:
        raise ValueError("benchmark proceeds do not cover exit fee")
    benchmark_cost = (entry_notional + buy_fee) / fx_start
    benchmark_proceeds = (benchmark_exit_notional - sell_fee) / fx_end
    actual = eur_proceeds / eur_cost - 1
    benchmark = benchmark_proceeds / benchmark_cost - 1
    return {
        "symbol": row["symbol"],
        "currency": "EUR",
        "cost_eur": str(eur_cost),
        "proceeds_eur": str(eur_proceeds),
        "net_return_pct": str(actual * 100),
        "benchmark_net_return_pct": str(benchmark * 100),
        "active_return_percentage_points": str((actual - benchmark) * 100),
        "status": "supplied_evidence_calculation_only",
        "not_a_real_strategy_backtest": True,
        "limitations": [
            "No public data completeness, universe survival, or original filing verification performed",
            "Corporate-action and point-in-time assertions must be independently evidenced",
            "Only one USD equity round trip; not annualized; no dividends, taxes, slippage, or FX spread",
            "No Islamic participation eligibility or investment approval implied",
        ],
    }
