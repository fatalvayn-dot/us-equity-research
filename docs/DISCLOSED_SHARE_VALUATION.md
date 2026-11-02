# Disclosed-share valuation indications

Policy: `disclosed-share-indication-v1`. This is a traceable arithmetic stage
toward the MVP's valuation model; it does not provide a fair value, approved
investment score or observed current market capitalization.

Primary API contract checked on 2026-11-02:
[SEC EDGAR API documentation](https://www.sec.gov/search-filings/edgar-application-programming-interfaces).
Companyfacts supplies standard, whole-entity concepts and separate unit arrays;
it does not authorize arbitrary class aggregation, unit fallback or calendar
frame substitution. Original inline XBRL remains the share-class cross-check.

The indication multiplies a verified Yahoo regular-session USD quote by a dated
SEC `dei:EntityCommonStockSharesOutstanding` count. Disclosed shares must be
positive integral units of `shares`, no more than 120 days old, available before
the quote observation, and independently matched to the exact original filing.
120 days is a screening-policy choice, not an assertion that the capital
structure has remained unchanged. Reported precision/rounding is preserved.

The original 10-Q/10-K accession, filing date and primary document must match
fresh SEC submissions metadata. The filing must disclose one unambiguous
non-dimensional DEI shares fact, exact issuer/date and `xbrli:shares` unit. Its
registered common-share cover must match the exact symbol. Multiple tickers,
class-labeled covers, dimensional counts, preferred/depositary titles and
conflicting or unsupported evidence are withheld. A single listed ticker alone
does not grant security-scope or sector approval.

Source order remains Yahoo -> SEC -> Nasdaq -> Finnhub. The existing Yahoo
financial adapter has no disclosed-DEI-shares implementation, so that field is
locally unsupported; SEC is the first supported source and stops evaluation
when valid. These local source evaluations are not claimed HTTP requests.
Yahoo supplies the quote. The capitalization indication itself is a calculation,
not a provider's market-cap field. Original annual financial field trails retain
their first-valid source; independent SEC confirmation never overwrites them.

Three ratios use the indicated capitalization as denominator: literal contract
revenue, issuer-level NetIncomeLoss, and OCF less PP&E payments. No alternative
revenue, ProfitLoss or productive-asset-payment tags substitute missing operands.
Every selected numerator is independently checked against the freshly observed
SEC companyfacts response for the same exact annual definition/date/currency.
Conflicts block the indication. NetIncomeLoss is not declared common-share EPS;
OCF less PP&E payments is not a complete owner-earnings measure. These are annual
ratios, not TTM, forecasts, targets or return promises. JSON retains Decimal
precision and operand provenance; Markdown displays six-decimal ratios.

Corporate actions, issuance/buybacks since the share date, sector eligibility,
the latest financial-statement selection and a complete risk model remain
unverified. All scores and fair values stay absent. A future scoring model must
explicitly accept or reject this estimation method and its uncertainty; it must
not treat it as a contemporaneous provider market-cap observation.

Recorded sample cutoff: 2026-11-02T20:00:15.589376+00:00. AAPL/MSFT/NVDA:
three original 10-Q share disclosures reconciled, ten available annual values
confirmed against fresh SEC companyfacts, seven ratios calculated. Thirteen
public observations retain original source bytes, URLs, hashes and UTC times.
Collection used nine SEC source GET invocations, three Yahoo quote invocations
and one SEC directory invocation (transport-internal retries excluded). Separate
access probes are documented separately and are not part of those 13 calls.
The 100-candidate report has three indications and 97 pending source bundles;
those 97 were not queried by this bounded sample. Zero scores; no MVP acceptance.

An immediate repeat used zero source/quote/identity GETs and retained the exact
prices, counts, original times, sources, metrics and capitalization indications.
It is cached reproduction, not another live validation. The regular quote TTL
remains 15 minutes, SEC snapshot TTL six hours. Replaying the saved sample at
its recorded cutoff is not a historical-vintage or backtest claim.
