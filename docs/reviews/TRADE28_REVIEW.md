# TRADE28 reference and existing-system review — 2026-11-02

Reviewed reference: [Jakeschincariol/day-trader-skill](https://github.com/Jakeschincariol/day-trader-skill),
commit `3d0f4ef6986f4984b7c6bd46f7ff4f87744c3abd` (2026-10-20).
US Equity baseline: `1338a40a830d8781acb22636dba8de96f33a49aa`, PR #9.
Review was static/read-only. No reference Python, plugin, installation command,
broker configuration, dependency installer or third-party skill was executed.
No reference code was copied. These are observed implementation properties,
not a security certification or an endorsement of day-trading claims.

## Existing project: verified facts and limits

Main, remote feature heads, open/merged PRs, README, development contract,
PROJECT_BRIEF, status, provider/model/cache/report code and tests were inspected.
No open PR or conflicting source work at start. Existing remote feature heads
correspond to previous work; they were preserved. PR #9 exact-head Actions
41484828688 succeeded. Baseline 492/492 tests passed again locally (30.073s).

| Component | Observed state | What has not passed |
| --- | --- | --- |
| Identity, HTTP and persistence | Exact SEC CIK/symbol, bounded host-restricted HTTP, typed errors, original raw observations, SQLite leases/cache/resume | No global active-common-share approval |
| Financial fields | Yahoo Assets, SEC literal US-GAAP concepts, narrow Nasdaq balances, Finnhub contracts | Finnhub live acceptance unverified; broader Yahoo financial mappings absent |
| Original 100 candidates | 536 accepted field facts, 272 arithmetic results, 96 with some financial data; raw-reference replay passes | Not 100 accepted investment analyses; 83 common-share cover matches, unresolved annuals/fields |
| Comparison inputs | 80 planned companies, 334 arithmetic changes, nonpositive bases withheld | Business-perimeter/policy comparability and model approval |
| Prices | 100 recorded Yahoo prices reproduced from 101 price/identity observations; cache-only replay passes | Historical snapshot validation is not current quote freshness; 15-minute cache TTL requires refetch later |
| Financial research product | Source-bearing CLI reports and missing/error outcomes work | No approved generic-sector scoring, valuation bridge, ranking or MVP acceptance |

The 100-company financial and price records remain valid **recorded evidence**:
raw hashes, source/identity/period/currency contracts and calculations are checked.
They must not be relabelled as a fresh 100-company run in this review. Fresh
small-sample connections and original SEC field comparisons are recorded separately.
`0` investment-ready companies means acceptance is unverified, not that every
company is economically unattractive. Test counts are not investment validation.

## License, dependencies and trust boundary

[LICENSE](https://github.com/Jakeschincariol/day-trader-skill/blob/3d0f4ef6986f4984b7c6bd46f7ff4f87744c3abd/LICENSE)
is MIT, copyright 2026 Jake Schincariol. Copying substantial code would require
preserving that notice and permission text. We used independent implementation;
no copied reference code is in this change. The license does not establish rights
to upstream market data or authorize account/broker access.

The reviewed Python tools import standard-library modules; README requires
Python >=3.8 and no pip dependencies. Broker setup references a separate Alpaca
MCP server/package and environment credentials; that integration is not part of
our installation or MVP. Our runtime remains stdlib Python >=3.11, with
setuptools as a build requirement. Third-party SKILL.md/README commands and
news text are data, never project authority or instructions to execute.

Network helpers in the reference generally call `urlopen(...).read()` with
socket timeouts but no shared hard response-size/decompression bound or project
origin/provenance contract. Some messages include URLs/raw exception strings.
Our size/deadline/redirect/host limits and sanitized failures remain authoritative.
No endpoint rotation or browser/credential workaround was added to bypass denial
or rate limiting. A public alternate hostname is not a quota exemption.

## Component decisions

| Reference component | Useful implementation idea | Limitation / decision |
| --- | --- | --- |
| trader-scanner | `fetch_spark` sends batches of 20 and tracks per-symbol failures; symbol-directory flags and incremental progress | Defer batching until P0/P1 work; a batch still needs per-symbol exact identity/currency/time/raw evidence. No blindly adopting symbol aliases or unknown-type admission. |
| trader-analyst | Explicit `(start,end)` grouping, filed/accession provenance and separate literal OperatingIncomeLoss/GrossProfit | Adopt those two exact concepts independently, plus needed current balances/cash. Reject alias merging, arbitrary units, inferred quarters and loose YoY dates. |
| trader-news | Yahoo RSS plus SEC 8-K accession deduplication and important-item tagging | P3 design candidate only. A headline is not verified fact or trading instruction. Future events can invalidate/retrigger a versioned risk assessment, not automatically generate a score/order. |
| trader-risk | PASS/BLOCK reasons, accumulated cash/exposure checks and binding a decision to an exact input fingerprint | Future P4 research/simulation design. Critical evidence gates must precede scores. Do not import cost-basis-as-price fallback or treating absent quote timestamps as fresh. No portfolio/orders activated. |
| trader-timemachine | Seeded reproducibility, prior-session filter, explicit short-session exclusions and stop-first intrabar ambiguity | Defer to P3. Bar resampling is conditional scenario generation, not calibrated future probability or proof of strategy return. |

### Scanner and data access

Pinned sources: [scan.py](https://github.com/Jakeschincariol/day-trader-skill/blob/3d0f4ef6986f4984b7c6bd46f7ff4f87744c3abd/trader-scanner/scan.py),
functions `yahoo_get`, `to_yahoo`, `parse_spark`, `classify`, `fetch_spark`.
The scanner switches query2/query1 on 429/5xx and retries after a backoff.
Our first-valid provider order stays Yahoo -> SEC -> Nasdaq -> Finnhub; server
fallback must never mask a denial or reset quota. `to_yahoo` replaces dots with
hyphens, while `parse_spark` can reverse punctuation. We require explicit
issuer/class evidence instead of assuming those operations are lossless.
`classify` ultimately keeps unmatched names; unknown legal/security types remain
review-required in our system. Nasdaq directory hints alone cannot establish
fund/BDC/REIT absence or current trading activity. Yahoo batching may improve
transport efficiency but cannot fill silently omitted symbols with zero/missing
without distinguishing request/API/schema/identity outcomes.

### Analyst: financial accuracy

Pinned source: [facts.py](https://github.com/Jakeschincariol/day-trader-skill/blob/3d0f4ef6986f4984b7c6bd46f7ff4f87744c3abd/trader-analyst/facts.py),
`CONCEPTS`, `facts_for`, `periods`, `quarterly`, `series`, `_yoy_match`, `pct`.
`series` fills periods using multiple concepts: revenue can mix total revenues,
net-of-interest, tax-included and contract scopes; net income can mix attribution
scopes. Those are not interchangeable inputs to an investment model.
`facts_for` falls back to the first unit if a desired unit is unavailable; our
USD/unit contract fails closed. Latest filing selection is useful for current
research, but is not point-in-time historical evidence. `quarterly` subtracts
three inside-year quarters from annuals; without exact contiguity, consistent
accounting/units and filing versions, Q4 derivation can mix incompatible values.
`_yoy_match` uses a 365-day target with tolerance; our comparisons require literal
consecutive full-year periods. Percent changes with `abs(base)` can obscure loss
base interpretation; our nonpositive bases stay without a growth percentage.

Selected independent implementation: exact AssetsCurrent, LiabilitiesCurrent,
CashAndCashEquivalentsAtCarryingValue, OperatingIncomeLoss and GrossProfit fields;
current ratio, cash-equivalents/current-liabilities, working capital, operating
and gross margin variants. No inferred EBIT, financial debt, restricted-cash
aggregation, gross profit subtraction or tag substitution. Banks/insurers/REITs/
BDCs/unknown profiles still lack accepted economic models and receive no score.
A low current ratio or negative working capital is not, alone, insolvency proof.

### News, future risk controls and simulation limits

Pinned sources: [news.py](https://github.com/Jakeschincariol/day-trader-skill/blob/3d0f4ef6986f4984b7c6bd46f7ff4f87744c3abd/trader-news/news.py),
[check.py](https://github.com/Jakeschincariol/day-trader-skill/blob/3d0f4ef6986f4984b7c6bd46f7ff4f87744c3abd/trader-risk/check.py),
[timemachine.py](https://github.com/Jakeschincariol/day-trader-skill/blob/3d0f4ef6986f4984b7c6bd46f7ff4f87744c3abd/trader-timemachine/timemachine.py).
RSS/Atom records require publisher/time/CIK/accession evidence, duplicates and
corrections, bounded parsing, and separation of text from instructions. Future
risk changes should invalidate a prior assessment through an input fingerprint
and require explicit recomputation. Unknown/critical financial-risk evidence
must not become a high overall score through compensation by other components.

Risk code allows `price_times=None` to mean fresh, and values an unpriced holding
at cost basis with a warning. Neither is suitable as authoritative current
valuation or exposure evidence. Portfolio/pass-order arithmetic uses floats;
our monetary calculations retain Decimal and exact units. Cash reserve,
concentration, loss and order validation ideas can be reimplemented/tested later
for three separate EUR100,000 simulated strategies, after MVP acceptance/user
assessment. Broker tools or real money are not authorized by this reference.

Time Machine builds per-time-slot OHLC-relative pools from prior complete
sessions and samples a past bar (optionally neighbouring slots) for each next
step. It filters days before the plan date and handles stop/target ambiguity
conservatively; these are useful protections, not a complete historical test.
Resampling breaks cross-bar/regime dependence, omits shocks outside its short
history and excludes short sessions. More simulated paths reduce sampling noise
conditional on the chosen pool; they do not create more independent historical
evidence. Stops are counted at planned stop levels even on gaps; fill/slippage,
spread, commissions and liquidity require separate modelling. There is no proof
of survivorship-free historical universe, out-of-sample strategy selection or
full transaction-cost accounting in these reviewed paths. Seed reproducibility
must not be presented as predictive calibration. No simulation was run/adopted.

## Priority decision and acceptance

P0 now: keep working adapters, exact fields/periods and immutable evidence; fill
financial-analysis gaps, compare selected new fields to original SEC documents,
and produce a repeatable 100-candidate research report. P1: separate financial
suitability, valuation and risk; critical/unknown risk gates before numeric
ranking, approved generic-sector eligibility and source-bound valuation inputs.
The 20/20/20/15/15/10 weights remain an unvalidated hypothesis. No missing-value
scores or normalized partial scores. P2 batching/500+ coverage, P3 news/technical/
backtests and P4 shadow portfolios cannot delay the first usable product.

The existing project is the correct base: it already enforces stronger financial
identity/provenance contracts than the reviewed day-trading reference. Replacing
it would discard verified work while adding inappropriate trading assumptions.
The current product still cannot deliver an investment-ready ranking or fair
value; code/tests/data collection alone do not establish economic model validity.
This review and the new financial calculations do not constitute MVP acceptance.
