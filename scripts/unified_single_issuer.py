"""Unified single-issuer research gate: reuse existing price, ledger and LLM modules.

No broker, position sizing, participation approval or paid API access.
A technical signal is NOT a fundamental valuation or investment recommendation.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from datetime import datetime, timezone

from scripts import market_radar_pilot as pilot
from scripts import market_radar_agents as ledger
from scripts import llm_team
from equity_research.participation_screen import assess_participation


def price_history(symbol, fixture=None):
    """Single fetch path; never re-fetch prices inside the LLM stage."""
    if fixture is not None:
        rows = pilot.load_fixture(fixture).get(symbol)
        if not rows:
            raise ValueError("fixture missing requested symbol")
        return rows, "fixture"
    candidates = [
        ("yfinance_daily", lambda: pilot.fetch_yfinance(symbol)),
        ("yahoo_chart_daily", lambda: pilot.fetch_yahoo_chart(symbol)),
    ]
    stooq = {"AAPL": "aapl.us", "MSFT": "msft.us", "ASELS.IS": None, "SAP.DE": None}.get(symbol)
    if stooq:
        candidates.append(("stooq_daily", lambda: pilot.fetch_prices(stooq)))
    failures = []
    for name, getter in candidates:
        try:
            return getter(), name
        except Exception as exc:
            failures.append(name + ":" + type(exc).__name__)
    raise RuntimeError("no verified price history: " + ", ".join(failures))


def build(symbol="AAPL", fixture=None, agent_transport=None, enable_llm=False, participation_evidence=None):
    """One entity, one market read, one evidence envelope.

    Fundamental, participation and news gates remain blocked until separately
    evidenced. Never synthesize missing financial values or grant trade approval.
    """
    rows, source = price_history(symbol, fixture)
    signal = pilot.signal(rows)
    forecast = dict(signal, symbol=symbol, source=source, asset_group="HISSE_ORNEK")
    raw = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "mode": "historical_fixture" if fixture else "live_attempt",
        "forecasts": [forecast], "evaluation": [], "errors": [],
        "news": {"status": "not_connected"},
        "coverage": {"requested": 1, "forecast_count": 1, "full_exchange": False},
    }
    summary, _, _ = ledger.process(raw, [], [])
    gates = {
        "identity": "sample_symbol_only",
        "market_price": "fixture" if fixture else "source_observed",
        "fundamentals": "blocked_missing_filing_evidence",
        "valuation": "blocked_missing_fundamentals",
        "participation": report["gates"]["participation"],
        "news_event_model": "not_connected",
        "prediction": "uncalibrated_baseline",
        "investment_decision": "prohibited",
    }
    participation = {"status": "bilinmiyor", "reason": "participation_source_evidence_missing",
                     "investment_approved": False, "no_live_source_verification": True}
    if participation_evidence is not None:
        if not isinstance(participation_evidence, dict):
            raise ValueError("participation evidence document must be an object")
        issuer = participation_evidence.get("company")
        if not isinstance(issuer, dict) or issuer.get("symbol") != symbol:
            raise ValueError("issuer symbol mismatch; refusing cross-issuer research")
        participation = assess_participation(
            issuer, participation_evidence.get("rulebook"),
            as_of=raw["generated_at_utc"])
        # Existing screen checks reference metadata, not original bytes.
        # Conditional pass is not index membership, certificate or order approval.
        gates["participation"] = participation["status"]
    envelope = {
        "schema_version": 1, "symbol": symbol, "as_of": signal["as_of"],
        "source": source, "forecast": forecast, "gates": gates,
        "participation_research": participation,
        "summary": summary, "research": raw, "llm": {"status": "disabled"},
        "investment_advice": False, "eligible_for_trade": False,
    }
    if enable_llm:
        if agent_transport is None and os.getenv("RADAR_FREE_LLM_ENABLED") != "true":
            raise RuntimeError("LLM explicit opt-in required")
        # Exactly the same evidence envelope: no second data/provider request.
        envelope["llm"] = llm_team.orchestrate(
            {"summary": summary, "research": raw}, transport=agent_transport)
    return envelope


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--symbol", default="AAPL")
    p.add_argument("--fixture")
    p.add_argument("--out", default="unified-single-issuer.json")
    p.add_argument("--llm", action="store_true")
    p.add_argument("--participation-evidence", help="Externally reviewed company/rulebook JSON; not index certification")
    args = p.parse_args()
    if len(args.symbol) > 16 or not args.symbol or any(
        ch not in "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789.-" for ch in args.symbol):
        p.error("invalid ticker; use an explicit verified ticker")
    evidence = (json.loads(Path(args.participation_evidence).read_text(encoding="utf-8"))
                if args.participation_evidence else None)
    report = build(args.symbol, args.fixture, enable_llm=args.llm,
                   participation_evidence=evidence)
    Path(args.out).write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "symbol": report["symbol"], "source": report["source"],
        "price": report["gates"]["market_price"], "participation": "unknown",
        "decision": "prohibited", "llm": report["llm"]["status"]
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
