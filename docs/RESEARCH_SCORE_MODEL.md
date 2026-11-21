# Technology research score v1

This versioned **research hypothesis** implements the 20/20/20/15/15/10 weights.
Thresholds are project choices, not historically calibrated return predictions.
A score does not constitute investment approval, fair value or full risk clearance.
The first 100-active-common-share MVP remains unaccepted.

## Eligibility and required evidence

Only SEC entityType `operating` and explicit SIC 3571 (electronic computers),
3674 (semiconductors) or 7372 (prepackaged software) have a model route. Codes:
[SEC official SIC list](https://www.sec.gov/search-filings/standard-industrial-classification-sic-code-list).
Other sectors, financial institutions, REITs, BDC/fund and unknown types remain
unscored. This limited whitelist is not broad financial-model coverage.

Eligibility also requires exact original-filing/DEI share-class corroboration,
one ticker and no class ambiguity, a current sourced USD US-equity quote, fresh
SEC metadata, the latest available annual end confirmed by that metadata, full
350–380-day annual periods, exact comparable prior annual contract revenue,
and all nine financial operands: Assets, Liabilities, AssetsCurrent,
LiabilitiesCurrent, NetIncomeLoss, OperatingIncomeLoss, operating cash flow,
PP&E payments and contract revenue excluding assessed tax. All are literal
concepts; no Revenues/ProductiveAssets/ProfitLoss substitutions. Nine current
facts plus prior revenue must agree with a recent SEC companyfacts snapshot.
First-selected sources and original timestamps are preserved.

Explicit tagged BDC, investment-company, registered closed-end fund or shell
disclosures override an apparently supported SIC. Unsupported/conflicting known
flags require review. Missing flags stay unknown; they are never changed to
false. Positive research-model eligibility comes from the combined operating
SIC, original common-share cover and current US quote, not absence of a tag.
This is not a legal opinion or a permanent fund-status certification.

Critical financial review, unresolved required review checks, invalid source
evidence, a split record since the disclosed count, missing full-year history
or median close-times-volume below USD 5 million withhold the **entire total**.
Higher other component points cannot offset these gates. Missing input yields
no score, not zero; genuine observed weak metrics may receive zero points.

## Published point rules

Each band uses the first matching threshold. Ratios are dimensionless.

| Component | Metric and bands | Maximum |
| --- | --- | ---: |
| Financial strength | Liabilities/Assets <=0.30:10, <=0.50:7.5, <=0.70:5, <=1.00:2.5, else:0; plus current ratio >=2:10, >=1.5:7.5, >=1:5, >=0.75:2.5, else:0 | 20 |
| Valuation | OCF less PP&E / stressed indicated capitalization >=8%:20, >=6%:15, >=4%:10, >=2%:5, else:0 | 20 |
| Growth | Exact comparable annual contract revenue growth >=20%:20, >=10%:15, >=5%:10, >=0%:5, else:0 | 20 |
| Profitability, hardware/semiconductors | Operating margin >=20%:15, >=10%:10, >=5%:5, >=0%:2, else:0 | 15 |
| Profitability, software | Operating margin >=30%:15, >=20%:10, >=10%:5, >=0%:2, else:0 | 15 |
| Cash flow | OCF less PP&E / contract revenue >=20%:15, >=10%:10, >=5%:5, >=0%:2, else:0 | 15 |
| Risk | Start 10; subtract 2 per financial watch signal, 2 for net loss, volatility >=60%:3 / >=40%:2 / >=25%:1, dollar volume >=50m:0 / >=10m:1 / >=5m:2; floor at zero | 10 |

Liabilities are not interest-bearing debt. OCF less PP&E is not complete owner
earnings. Negative book/working-capital signals require context rather than an
automatic insolvency diagnosis. Known critical signals remain mandatory reviews.
Financial suitability, valuation and risk components remain separately visible.

## Dated-share uncertainty policy

The source-verified disclosed count is at most 120 days old. The model does not
pretend it is a contemporaneous exchange market-cap observation. It requires
a one-year Yahoo daily window covering share date through quote day and no
split record in that returned window. Issuance, repurchases and all capital
changes are not thereby cleared.

Valuation therefore uses the explicit scenario:
`price * (disclosed shares + one reported precision quantum) * 1.25`.
For decimals=INF the precision allowance is zero. The 25% uplift is an assumed
stress, not an observed share count, statistical confidence interval or guarantee
that every actual capital change is bounded by it. Selected disclosed shares and
the unstressed indication remain separately recorded. Investment approval and
full capital-change clearance stay false even when a research score is produced.

## Observed market risk

Use 200–400 non-null ordered daily rows covering at least 300 calendar days.
Exclude the quote's day, including after the close, to avoid an unfinished bar.
Require >=200 completed sessions, recent coverage and no gap over ten days.
The latest raw daily close and the separate regular-session quote must agree
within 20%; larger discrepancies require review before any total is assigned.
Volatility is sample standard deviation of adjacent adjusted-close simple returns
times sqrt(252); liquidity is median Yahoo close times reported volume for the
last 63 completed sessions. They are historical proxies, not forecast volatility
or executable liquidity. [Yahoo adjusted-close definition](https://in.help.yahoo.com/kb/adjusted-close-sln28256.html).
The endpoint is public chart JSON; no subscription CSV download, credentials or
blocked authenticated endpoint is used.

## Pilot and limitations

At cutoff 2026-11-02T21:33:48.135379+00:00, the retained 100-candidate annual/
comparison batches and seven new market observations produced two numeric
research hypotheses: MSFT 66.5 and AAPL 53.0. Four critical financial reviews
remained unranked. NVIDIA lacked literal contract revenue and PP&E-payment
operands and remained unscored; no accounting aliases filled the gaps. The other
97 valuation source bundles were not queried in this bounded pilot. Financial
sources were recent retained snapshots, not a new 100-company financial refresh.

Qualitative filings/news, governance, all capital changes, wider sector coverage,
prospective validity, out-of-sample performance and 100 current active common
shares remain unaccepted. Do not call a 66.5-point company a buy or claim a
predictive completion percentage. Full per-component formulas, exact inputs,
confirmations and source hashes are retained in JSON. No total is normalized
over the available subset and no trading/portfolio functionality is activated.
