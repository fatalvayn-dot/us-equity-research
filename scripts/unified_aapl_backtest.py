"""Walk-forward 5-session AAPL baseline audit using EXISTING momentum and outcome functions.

Historical evaluation is NOT a trained predictor, causal backtest, live forecast
or independent samples. Each signal sees only bars available on its as_of date.
"""
from scripts import market_radar_pilot as radar


def audit(rows, symbol="AAPL", max_signals=200):
    if symbol != "AAPL":
        raise ValueError("AAPL-only prototype")
    if type(max_signals) is not int or not 1 <= max_signals <= 250:
        raise ValueError("bounded backtest size required")
    if not isinstance(rows, list) or len(rows) < 27:
        return {"status": "insufficient_completed_bars", "symbol": symbol,
                "horizon_sessions": 5, "eligible_samples": 0,
                "performance_gate": "insufficient_completed_bars", "predictive_approved": False,
                "direction_hit_rate": None, "benchmark_up_hit_rate": None,
                "nonoverlapping": {"eligible_samples": 0, "direction_hit_rate": None,
                                   "benchmark_up_hit_rate": None, "status": "insufficient_data"},
                "investment_approved": False}
    historical_indices = list(range(21, len(rows) - 5))[-max_signals:]
    forecasts = []
    for i in historical_indices:
        # Critical anti-lookahead invariant: never feed the future outcome.
        signal = radar.signal(rows[:i + 1])
        forecasts.append({"symbol": symbol, "as_of": signal["as_of"],
                          "direction": signal["direction"]})
    evaluated = radar.evaluate(forecasts, {symbol: rows})
    valid = [e for e in evaluated if e.get("status") == "evaluated"
             and isinstance(e.get("hit"), bool)]
    directional_hits = sum(e["hit"] for e in valid)
    benchmark_hits = sum(e["actual"] == "yukari" for e in valid)
    count = len(valid)
    # Five-session forward outcomes must never share target bars in the
    # independent benchmark. We sample forecast origins five bars apart,
    # BEFORE filtering neutral/unavailable outcomes.
    independent = [
        e for e in evaluated[::5]
        if e.get("status") == "evaluated" and isinstance(e.get("hit"), bool)
    ]
    independent_count = len(independent)
    independent_hits = sum(e["hit"] for e in independent)
    independent_up_hits = sum(e["actual"] == "yukari" for e in independent)
    independent_check = {
        "eligible_samples": independent_count,
        "direction_hit_rate": (round(independent_hits / independent_count, 4)
                               if independent_count else None),
        "benchmark_up_hit_rate": (round(independent_up_hits / independent_count, 4)
                                 if independent_count else None),
        "status": ("insufficient_independent_samples" if independent_count < 40
                   else "not_better_than_naive_up"
                   if independent_hits <= independent_up_hits
                   else "historical_unvalidated_edge"),
        "origin_spacing_sessions": 5,
        "price_lookahead_used": False,
    }
    return {
        "status": "historical_uncalibrated_backtest",
        "symbol": symbol, "horizon_sessions": 5,
        "first_as_of": forecasts[0]["as_of"],
        "last_as_of": forecasts[-1]["as_of"],
        "total_signals": len(evaluated),
        "eligible_samples": count,
        "performance_gate": ("insufficient_directional_sample" if count < 30
                             else "not_better_than_naive_up" if directional_hits <= benchmark_hits
                             else "historical_better_than_naive_unvalidated"),
        "predictive_approved": False,
        "neutral_signals": len(evaluated) - count,
        "direction_hit_rate": round(directional_hits / count, 4) if count else None,
        "benchmark_up_hit_rate": round(benchmark_hits / count, 4) if count else None,
        "statistical_caveat": "overlapping_5_session_outcomes_not_independent",
        "nonoverlapping": independent_check,
        "trained_model": False,
        "adaptive_optimization_verified": False,
        "investment_approved": False,
    }
