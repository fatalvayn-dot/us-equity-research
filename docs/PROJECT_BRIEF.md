# Authoritative scope

New repository: fatalvayn-dot/us-equity-research. Legacy:
fatalvayn-dot/radar-agent, never delete; archive only through an authorized
repository management operation. Develop independently.

Goal: identify, analyze and rank attractive active NYSE, Nasdaq and NYSE American
common shares with real auditable financial data. Exclude ETFs, funds, warrants,
bonds and other non-common instruments. No other markets, crypto, shadow
portfolios or trades. No paid service, new access permission or real-money
operation. Technical and research-method decisions are delegated.

Field sources: Yahoo Finance, SEC EDGAR, Nasdaq, Finnhub in that order. Stop at
first valid value. Reliable free alternatives may be evaluated if needed.
Record issuer, source, period, currency, data date, accounting definition and
evidence. Never invent data or replace missing with zero. Distinguish API
failure, quota, symbol mismatch and true absence. Cache and update incrementally.

Score hypothesis: financial strength 20, valuation 20, growth 20,
profitability 15, cash flow 15, risk 10. Use sector-appropriate models including
financial institutions. Incomplete evidence must not receive an invented score.
Company reports need financial condition, valuation, risks, investment rationale
and sources. Validate hypotheses historically without lookahead or survivorship
bias before claiming predictive success.

Strictly gated stages:

1. Architecture, models and tests.
2. Real Yahoo/SEC/Nasdaq/Finnhub connections.
3. Calculations, valuation and risk.
4. 100-company real-data/financial validation.
5. Scoring and ranking.
6. Point-in-time historical testing.
7. Expand to 500, 1,000, then all active US common shares.
8. Full regression, integration, performance and real-data acceptance.

Complete only when active universe, live-verified sources, tested models,
scoring, trustworthy missing-data handling, full-universe scanning,
source-backed reporting, regressions/integrations, reproducibility and real-data
acceptance report all exist. Partial success is not full completion.

Each session: inspect main/PR/Actions and status; choose a concrete task, use
a feature branch, implement/test, open PR, merge validated changes and save
test evidence, failures, blockers and next task. Send brief Turkish updates
only for meaningful progress, real blockers or completed stages. Scheduled
runs are separate sessions, not continuous background execution.
