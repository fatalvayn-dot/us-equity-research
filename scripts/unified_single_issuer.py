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


def financial_provenance(report, symbol, cik, cutoff):
    """Gate existing SEC report to exactly one issuer; no fresh financial calculations."""
    if not isinstance(report, dict):
        raise ValueError("financial report must be an object")
    companies = report.get("companies")
    if not isinstance(companies, list) or len(companies) != 1:
        raise ValueError("financial report must contain exactly one company")
    record = companies[0]
    if not isinstance(record, dict) or record.get("symbol") != symbol or record.get("issuer_id") != cik:
        raise ValueError("financial report issuer identity mismatch")
    count = record.get("accepted_fact_count")
    if type(count) is not int or count < 0:
        raise ValueError("financial accepted fact count missing or invalid")
    timestamp = report.get("as_of")
    if not isinstance(timestamp, str):
        raise ValueError("financial report timestamp missing")
    observed = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
    if observed.tzinfo is None or observed > cutoff:
        raise ValueError("financial report generated in future or lacks timezone")
    pipeline = report.get("pipeline", {})
    if not isinstance(pipeline, dict):
        raise ValueError("financial pipeline evidence invalid")
    archived = pipeline.get("all_financial_references_archived") is True
    return {
        "status": "facts_observed_review_required" if count > 0 and archived else "incomplete_evidence",
        "symbol": symbol, "issuer_id": cik, "accepted_fact_count": count,
        "as_of": observed.isoformat(),
        "all_financial_references_archived": archived,
        "financial_valuation_complete": False,
        "investment_approved": False,
    }


def build(symbol="AAPL", fixture=None, agent_transport=None, enable_llm=False,
          participation_evidence=None, financial_report=None, financial_cik=None):
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
        "participation": "unknown",
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
    financial = {"status": "missing_sec_report", "investment_approved": False}
    if financial_report is not None:
        if symbol != "AAPL" or financial_cik != "0000320193":
            raise ValueError("verified AAPL financial identity required")
        financial = financial_provenance(
            financial_report, symbol, financial_cik,
            datetime.fromisoformat(raw["generated_at_utc"]))
        gates["fundamentals"] = financial["status"]
    envelope = {
        "schema_version": 1, "symbol": symbol, "as_of": signal["as_of"],
        "source": source, "forecast": forecast, "gates": gates,
        "participation_research": participation, "financial_research": financial,
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
    p.add_argument("--financial-report", help="Existing SEC MVP one-issuer report JSON, not a valuation approval")
    p.add_argument("--financial-cik", help="Exact SEC identity for --financial-report")
    args = p.parse_args()
    if len(args.symbol) > 16 or not args.symbol or any(
        ch not in "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789.-" for ch in args.symbol):
        p.error("invalid ticker; use an explicit verified ticker")
    evidence = (json.loads(Path(args.participation_evidence).read_text(encoding="utf-8"))
                if args.participation_evidence else None)
    financial = (json.loads(Path(args.financial_report).read_text(encoding="utf-8"))
                 if args.financial_report else None)
    report = build(args.symbol, args.fixture, enable_llm=args.llm,
                   participation_evidence=evidence, financial_report=financial,
                   financial_cik=args.financial_cik)
    Path(args.out).write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "symbol": report["symbol"], "source": report["source"],
        "price": report["gates"]["market_price"], "participation": report["gates"]["participation"],
        "decision": "prohibited", "llm": report["llm"]["status"]
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
