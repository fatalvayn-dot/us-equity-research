# US Equity Research

Independent Python system for active NYSE, Nasdaq and NYSE American common
shares. Version 0.8.0 adds live-tested Nasdaq Assets/Liabilities and a lazy ordered
research command. Finnhub live acceptance, broad financial models, scoring,
rankings and full-universe acceptance remain pending.

## Run

Python 3.11+; runtime and tests use only the standard library. From this folder:

```bash
PYTHONPATH=src python3 -m unittest discover -s tests -v
PYTHONPATH=src python3 -m equity_research status
```

Optional installation: `python3 -m pip install -e .` (requires setuptools).

## Implemented offline

- Canonical SEC CIK identity, separate listing model, active/common-share scope.
- Decimal facts with accounting definition, reporting period, currency, units,
  availability/retrieval dates and provenance URL.
- Yahoo → SEC → Nasdaq → Finnhub first-valid resolver and separate API, quota,
  symbol, missing, unconfigured and invalid-data statuses. SEC companyfacts is implemented; other financial adapters remain pending.
- SQLite accepted-fact cache with semantic keys, TTL and persistence. Live
  incremental orchestration remains pending.
- Immutable 20/20/20/15/15/10 scoring specification, with no score fabrication.
- Unit/regression tests, resolver-to-SQLite integration and real-response SEC replay.
- SEC directory adapter with HTTPS host restrictions, timeouts, bounded retries,
  rate limiting, response checksums and exact symbol/CIK checks. This directory
  does not prove active/common-share status. See docs/evidence/sec-directory-live.json.
- CI definition for Python 3.11/3.12/3.13, not yet run remotely.

Fixture values are synthetic. True zero is retained; unknown is never zero.
core.py is deprecated starter compatibility; new code uses models/providers.

No ETFs, funds, warrants, bonds, preferred shares, unknown types, other markets,
crypto, portfolios or trades. ADRs are conservatively outside direct common
shares in v1. Financial institutions, insurers and REITs need dedicated models;
unsupported models must not be described as data exclusions.

Both availability and retrieval must precede the analysis cutoff. A current
response cannot establish historical knowledge. Validated vintages,
restatements and survivorship controls remain necessary before backtesting.
An as_of cutoff refers to a completed evidence snapshot, not the instant before
starting a fetch.

Read docs/PROJECT_BRIEF.md, docs/ARCHITECTURE.md and docs/DEVELOPMENT_STATUS.md
to resume. Legacy fatalvayn-dot/radar-agent is unchanged.

## SEC identity lookup

Provide an identifying User-Agent with your actual contact, via SEC_USER_AGENT
or the --user-agent option. No API key is required for the directory.

```bash
PYTHONPATH=src python3 -m equity_research sec-directory --symbol AAPL --symbol MSFT
```

Default pacing is two requests/second per shared in-process limiter. Do not
launch independent collectors against the SEC without sharing a rate limiter.
Timeout limits each socket operation; an overall budget is checked between
requests and buffered reads, so an in-flight read can exceed the budget by up
to its socket timeout. Redirects, authentication failures and access blocks
are not bypassed. Long Retry-After delays stop the attempt rather than retrying
early. Original directory bytes are recorded as a fixture with their checksum;
this fixture is dated evidence, not a continuously current universe.

## SEC financial diagnostics

Six exact US-GAAP mappings are implemented: revenue excluding assessed tax,
assets, liabilities, net income, operating cash flow and cash paid to acquire
property/plant/equipment. No alternative tag is silently substituted.

```bash
PYTHONPATH=src python3 -m equity_research sec-fact --cik 0000320193 --field assets --period-end 2025-09-27
```

Set SEC_USER_AGENT with actual identifying contact first. The command prefetches
one company snapshot before setting the analysis cutoff, then resolves the
requested field. Unconfigured Yahoo is reported explicitly; this diagnostic is
not the complete production source chain. Snapshot memory and atomic disk cache
reuse the original retrieval time and SHA256, with a default six-hour TTL.
Use a controlled refresh after new filings; filing-triggered invalidation and
conditional HTTP refresh are not implemented yet.

Filing provenance retains accession, filing date and raw checksum. Companyfacts
only supplies a filing date; availability is conservatively delayed to 05:00 UTC
on the following day. This is not an exact SEC acceptance timestamp. Historical
cutoffs still reject current retrievals, and backtests remain unaccepted.

On 2026-11-01, three company snapshots yielded 16 of 18 requested annual/instant
fields. Two NVDA fields lacked the exact selected annual accounting definition.
Assets for all three matched original iXBRL filings, including comparative
balance-sheet contexts in subsequent quarterly filings. This check covers three
asset values, not the accuracy of every collected field or 100-company acceptance.
See docs/evidence/companyfacts-live.json and compressed real-response fixtures.

## Live source ordering

`Resolver.resolve_current(FactQuery(...))` prepares only the next required
provider and fixes a cutoff after that response arrives. It returns the chosen
cutoff in Resolution.as_of. A valid Yahoo field prevents any SEC financial
prepare/fetch. A fixed `resolve(FactRequest(...))` never advances its historical
cutoff; do not use live mode to relax historical tests.

YahooAssets currently supports **assets only**, using annualTotalAssets with an
exact period-end, currency and vendor-symbol check plus a fresh SEC symbol/CIK
binding. The binding source URL, timestamp and hash, vendor field, raw response
hash and first-observed public timestamp travel with the Fact and through SQLite.
Yahoo does not supply a filing timestamp here; retrieval time is used
conservatively, with no claim that it is the original publication date.

The Yahoo timeseries endpoint is undocumented and may change or deny access.
No cookie/crumb acquisition, login, proxy rotation or access-block bypass is
implemented. Its use was evaluated against the upstream yfinance source; no
external runtime package was added. Memory caches valid response snapshots;
cross-session Yahoo disk caching is still pending.

On 2026-11-01, MSFT Assets matched the exact requested date and prior original
filing value and stopped before SEC collection. AAPL and NVDA had Yahoo dates
differing from requested filing dates; period_mismatch was preserved and SEC
provided the field. Equal values never justify changing a period date. See
docs/evidence/yahoo-sec-live.json and the recorded Yahoo fixtures. No revenue,
profit, cash-flow duration or IFRS mapping is inferred from a Yahoo label.

Programmatic use requires a fresh SEC DirectorySnapshot and separate source
transports (query1.finance.yahoo.com for Yahoo, data.sec.gov for SEC):

```python
from equity_research.models import FactQuery
from equity_research.providers import Resolver
from equity_research.yahoo import YahooAssets
from equity_research.companyfacts import SecCompanyFacts

# directory is a fresh SecDirectory.fetch() result; transports use explicit hosts.
resolver = Resolver([
    YahooAssets(yahoo_transport, directory=directory, symbol="MSFT"),
    SecCompanyFacts(sec_transport, cache_dir="data/cache/companyfacts"),
])
# Supply exact period_end as a datetime.date, not a calendar-quarter guess.
result = resolver.resolve_current(FactQuery(
    "0000789019", "assets", None, period_end, "USD", "currency", "us-gaap:Assets"
))
```

## Nasdaq discovery and universe boundaries

```bash
PYTHONPATH=src python3 -m equity_research nasdaq-discovery --user-agent 'Your project and actual contact'
```

The bounded screener collector verifies pagination totals, unique symbols and
stable source labels. It retains raw/source symbols and strips only surrounding
ASCII padding. It does not guess class punctuation. On 2026-11-01 it collected
6,954 records, with 6,560 exact SEC symbol matches. The source's last-price label
was October 29; this is not a verified listing date or current price assertion.
The JSON lacks exchange, ETF/test flags and explicit active/security-type evidence.
These records are discovery inputs, not the accepted active-common-share universe.

Nasdaq Trader nasdaqlisted/otherlisted parsers are implemented separately, with
schema/footer checks, fresh source evidence and exhaustive row partitioning.
Known ETF, NextShares, depositary, preferred, warrant, unit and debt indicators
stay out of common-share candidates. Unknown types, flags, identities, class
aliases and exchange conflicts remain pending. Name-based candidates still
require legal-type/current-listing corroboration; no Security.active=True is
created from this evidence alone. Financial warning flags are retained for
analysis rather than deleting a listed company from the source universe.

Both text directories were unavailable in this environment; a diagnostic HTTPS
request to the documented file host returned HTTP 503. The screener API worked
as a separate discovery fallback, without supplying the missing metadata. Live
Trader-directory parsing remains unaccepted. See docs/evidence/nasdaq-*.json.

Transport errors now retain safe enumerated reason/HTTP code, never server error
bodies or credential-bearing exception messages. This distinguishes transient
HTTP 503 from a true empty universe. No access block bypass is implemented.

## Finnhub reported-financial contracts (live acceptance pending)

Set an existing key through FINNHUB_API_KEY (or FINNHUB_TOKEN, with no conflicting
second value). No key is stored in this repository. .env.example documents the
variable names; environment files are not auto-loaded. Do not put actual values
in source, report URLs or test fixtures.

```bash
PYTHONPATH=src python3 -m equity_research finnhub-fact --cik 0000320193 --field assets --period-end 2025-09-27
```

Without configuration, this returns not_configured and network_attempted=false.
With a key, the client uses a Finnhub-only X-Finnhub-Token header, bounded HTTP
transport and annual reported financials by exact CIK/end-date. A 403 or premium
entitlement error stays access_denied; the client does not purchase or upgrade.

The adapter contract covers six exact US-GAAP concepts with explicit per-row
currency/unit, period, filing accession/date and checksum. It rejects legacy
unitless maps, incompatible scale, segment context, conflicting values and
unverified historical retrieval. Unit-bearing statement arrays are a strict
supported contract, not a claim that the current live account response has been
validated. Empty/failed/auth-blocked responses are not invented financial zeros.
Date-only filing evidence uses conservative next-day availability, as with SEC.

At this checkpoint neither supported environment variable was configured in the
execution environment. Finnhub made zero network calls and is not live accepted.
Synthetic tests do not replace that missing evidence. See finnhub-preflight.json.
Nasdaq Trader files were retried and still returned HTTP 503.

The optional manual finnhub-smoke.yml workflow is prepared for the new GitHub
repository: it reads its existing FINNHUB_API_KEY Actions secret and collects
one Assets observation. Inputs are passed via quoted environment variables,
not shell interpolation. It saves only the sanitized diagnostic result. It has
not been executed remotely and passing it alone is not financial acceptance.

## Ordered financial collection

```bash
PYTHONPATH=src python3 -m equity_research research-fact --symbol AAPL --cik 0000320193 --field assets --period-end 2025-09-27
```

Set SEC_USER_AGENT with actual contact first. The command verifies a fresh SEC
symbol/CIK identity, then lazily collects Yahoo → SEC → Nasdaq → Finnhub. A valid
field prevents construction, environment inspection and queries of later source
clients. Invalid later configuration cannot break an earlier successful result.
The result records attempts, the chosen cutoff and provenance. Missing/unavailable
facts exit nonzero. This command is research infrastructure, not an investment score.

Nasdaq currently supports Total Assets and Total Liabilities only, with exact
balance-sheet dates. The API provides displayed monetary strings but no explicit
scale; the adapter separately fetches the same stock's official financial page
and requires one visible currency/scale caption. It does not infer USD from '$'.
On 2026-11-02 three pages explicitly stated In USD Thousands, so amounts were
multiplied by 1,000. All six selected values matched original SEC iXBRL documents.
Financial durations and EPS/ratio units are not mapped from this caption.

Facts retain separate data/units observation times, unit-page URL/SHA, multiplier,
API URL/SHA and SEC identity proof. The combined retrieval cutoff follows all
required evidence; first-observed availability is conservative because Nasdaq
publishes no filing timestamp in this payload. Both responses are memory-cached
for reuse; persistent Nasdaq caching is still pending. Exact source fixtures and
six comparisons are in docs/evidence/nasdaq-financial-live.json.

A live AAPL research-fact invocation used Yahoo period_mismatch → SEC valid and
stopped there. Its sanitized output is in docs/evidence/ordered-cli-live.json.
This does not validate all fields, all four providers or a 100-company universe.


Resumable evidence collection (v0.9.0):

```bash
PYTHONPATH=src python3 -m equity_research research-batch \
  --user-agent "$SEC_USER_AGENT" --plan docs/evidence/batch-three-plan.json \
  --checkpoint data/batch.sqlite --output data/batch-report.json --max-new-fields 3
# Re-run without --max-new-fields to finish remaining fields.
```

The plan fixes exact issuer, period and definitions; duration dates are never
inferred. This saved plan is a three-company diagnostic, not current-period
selection. The checkpoint commits every field atomically, reuses fresh original
observations for six hours, and delays missing/error retries for five minutes.
Policy version changes invalidate prior entries. A renewable SQLite lease blocks
simultaneous writers; an expired worker cannot overwrite a successor. The lease
covers only the same checkpoint file; use one checkpoint for a shared job.

Each output separates field completion from pending scope. No scope approval,
investment score or 100-company acceptance is implemented here. Exit 2 means
pending fields or a diagnostic error; successfully writing a report is not
financial acceptance. Reports are atomically replaced. On process interruption,
re-run with the same plan/checkpoint; previous fields survive. A hard process
termination may require waiting for the 15-minute lease to expire.

Opt-in live resume verification: `PYTHONPATH=src python3 scripts/verify_batch_resume.py
--user-agent "$SEC_USER_AGENT" --checkpoint data/new-diagnostic.sqlite` (single
shell line; requires a new checkpoint). It records actual transport calls and
source results. `python3 scripts/prepare_sample100.py` regenerates an offline
100-candidate audit queue. Name hints and SEC exchange labels are insufficient
for active common-share approval; 97 candidates lack verified financial periods.


Primary listing reconciliation (v0.10.0):

```bash
PYTHONPATH=src python3 scripts/audit_sample_scope.py --live --user-agent "$SEC_USER_AGENT"
# Deterministic offline replay at the original recorded observation time:
PYTHONPATH=src python3 scripts/audit_sample_scope.py
```

Both official directory files must parse completely. The adapter tries the
original FTP-host HTTPS endpoint, then the exact official Nasdaq Trader HTTPS
mirror, stopping at the first valid response. Transport now accepts explicit
JSON/text/HTML media types, with JSON remaining the default. Listing downloads
request text/plain. Unsupported media types and header injection are rejected.
Actual source URLs, hashes, retrieval times, creation-date labels and every
attempt remain in the evidence. A documented vendor discrepancy is handled
narrowly: otherlisted has eight data fields but an empty seven-field legacy
footer. Data row widths remain strict.

The 2026-11-02 verification parsed 13,286 primary directory records; 100 audit
candidates matched listing flags and SEC identity. The files were generated
2026-10-30, within the explicit four-calendar-day freshness policy; this is not
proof of intraday trading eligibility. None is legal-type/scope approved yet.
The classification is `listing_evidence_complete_legal_type_pending`. ETF/test
flags do not establish that a common share is not an investment fund. Fund-name
ambiguities, wrong CIKs, collisions, stale evidence and missing matches stay
quarantined. This audit does not change batch scope or generate investment scores.
Primary field definitions: https://www.nasdaqtrader.com/Trader.aspx?id=SymbolDirDefs

SEC submissions metadata and registered-share corroboration (v0.11.0):

```bash
PYTHONPATH=src python3 scripts/verify_submissions_sample.py --user-agent "$SEC_USER_AGENT"
PYTHONPATH=src python3 scripts/replay_registered_shares.py
```

Submissions retain exact SEC identity, raw entity/SIC/fiscal-year-end labels,
recent filing history, explicit annual report end, accession, filing date and
safe primary-document URL. A six-hour SQLite cache preserves original response
bytes/time/hash across restarts. Every column length is checked; an unsupported
legacy document format is labelled, never parsed as HTML. Older history pages
are not queried, so no annual in the recent window does not mean no annual exists.
A report end never supplies its beginning or currency. Submission acceptance
time is kept as a raw source label and is not historical availability evidence.

The narrow filing parser corroborates a registered common/ordinary title only
when symbol/title/exchange share an issuer/date context. Debt records with the
same ticker are kept out of common-share evidence. Supported inline English
date transformation is explicit; conflicting/missing context evidence fails.
Three existing quarterly filings are replayed with their original provenance;
this command makes no fresh filing downloads. Raw checkbox labels are not
converted to booleans. An operating label, SIC code or registered common title
alone does not prove fund exclusion or confer scope/investment approval.

SEC API documentation: https://www.sec.gov/search-filings/edgar-application-programming-interfaces

Explicit annual duration contexts (v0.12.0):

```bash
PYTHONPATH=src python3 scripts/verify_annual_filings.py --user-agent "$SEC_USER_AGENT" --limit 3
PYTHONPATH=src python3 scripts/verify_annual_filings.py --replay
```

The first command downloads a bounded original annual sample using submission
provenance. The replay validates saved bytes against their original URL/hash/time
and performs no HTTP request. Periods come only from non-dimensional CIK contexts
sharing DocumentType, DocumentFiscalPeriodFocus=FY and matching DocumentPeriodEndDate.
The start is explicit in the source; it is never calculated by subtracting a year.
Quarterly, conflicting, missing, reversed and over-550-day contexts stay unsupported.
The cover parser handles nested nonNumeric text without losing the parent's year;
unsupported continuations/exclusions fail rather than being silently guessed.

Three original annual filings supply exact periods: NVDA 2025-01-27–2026-01-25,
AAPL 2024-09-29–2025-09-27, MSFT 2025-07-01–2026-06-30. The corrected source replay
also corroborates each registered common class. The initial live parse failure
and corrected replay are separate evidence files. These documents do not prove
fund exclusion or investment suitability. The six-field three-company plan in
annual-three-plan.json remains scope-pending; no financial query was run here.

Resumable original filing collection (v0.13.0):

```bash
PYTHONPATH=src python3 scripts/collect_annual_documents.py --user-agent "$SEC_USER_AGENT" --max-new-documents 5
PYTHONPATH=src python3 scripts/collect_annual_documents.py --user-agent "$SEC_USER_AGENT" --max-new-documents 0 --output docs/evidence/annual-document-resume.json
```

The SQLite source checkpoint preserves raw bytes, exact filing identity, original
observation and SHA-256. Each document outcome is committed separately; parsing
is rerun from cached source bytes under the current code. A same-file renewable
lease blocks overlapping writers and rejects expired owners. Corrupt/expired
sources require new bounded requests. Missing annual metadata, unsupported file
formats, unstarted work and typed transport/parser failures remain separate.
Failures are persisted as outcomes but not reused as successful source bodies.
The six-hour source TTL never renews on read. `new_documents` counts attempted
transport GETs, including unsuccessful attempts; it excludes internal HTTP retries.

This verification reused 3 prior sources and downloaded 5 new ones, producing
8 exact period/common-share checks. Repeating with zero new work reused all 8
with zero HTTP requests. Ninety annual documents remain unstarted and two lack
annual metadata in the recent window. Legal-type approval is still pending.
An eight-company financial run collected 43/48 requested exact facts; 5 remain
unresolved. Missing SEC tags plus unsupported/unconfigured fallback sources are
not proof of global data absence. The immediate repeat reused all 48 outcomes;
no score, complete-company approval or real 100-company acceptance was generated.

Exact public response evidence (v0.14.0):

```bash
PYTHONPATH=src python3 scripts/verify_archived_financials.py --user-agent "$SEC_USER_AGENT"
PYTHONPATH=src python3 scripts/reconcile_annual_balances.py
```

The opt-in archive records exact public response bodies once per SHA-256 plus
separate URL/hash/original-time observations. It is wired lazily into the ordered
financial resolver through `response_archive=...`; SEC disk/memory snapshot hits
are archived at their original observation, without making a new source request.
Readback rechecks integrity and can require the exact observation time. Replay
never refreshes that time. No request headers are stored. Authenticated transports,
Finnhub origins and credential query parameters are rejected before archiving.
Archive writes fail with `evidence_error`, separately from provider API failure.
Finnhub live/archive acceptance is still pending; no key was used here.

A fresh eight-company collection again produced 43/48 facts. All main, identity
and unit references for these 43 observations have exact raw-response evidence;
this does not retroactively fill missing raw bytes in older runs. Original annual
Assets/Liabilities checks matched 15 of 16 amounts. AMZN Liabilities remains
unresolved by the narrow original-concept parser; it is not recorded as a match.
Income/cash-flow values, legal type and full-company acceptance remain unverified.

Original concept diagnostics (v0.15.0):

```bash
PYTHONPATH=src python3 scripts/diagnose_original_concepts.py
```

This offline original-filing replay checks explicit US GAAP concepts, exact CIK,
start/end or instant context and non-dimensional USD units. It separates absent
concepts, dimensional-only data, period/scope mismatches, unsupported numeric/unit
presentations and conflicting original values. Decimal scaling retains precision;
no dash, nil or unsupported transform becomes zero. Namespace/unit/transform
bindings and numeric grouping are checked. One parseable duplicate cannot hide
an unsupported duplicate in the requested context.

All 27 collected income/cash-flow values matched original annual facts. Five
uncollected fields remain pending: NVDA uses Revenues and PaymentsToAcquireProductiveAssets;
GOOGL's requested revenue concept occurs only in dimensional contexts, while its
consolidated disclosure uses Revenues; AMZN uses PaymentsToAcquireProductiveAssets;
AVGO uses ProfitLoss. These are distinct concept observations, not automatic
accounting-definition equivalents. No resolver mapping or accepted fact changed.

For AMZN, original LiabilitiesAndStockholdersEquity minus StockholdersEquity equals
406977000000 USD, the collected Nasdaq amount. This is an explicitly derived
candidate requiring scope/mezzanine review. It is not a direct disclosed
us-gaap:Liabilities fact and does not clear the pending original-total check.
The diagnostics make no HTTP request and grant no score, scope or financial-model
acceptance. The prior raw-response and instant-balance evidence stays unchanged.

Distinct accounting fields (v0.16.0):

The immutable field registry adds revenue_total (us-gaap:Revenues), profit_loss
(us-gaap:ProfitLoss) and productive_asset_cash_payments
(us-gaap:PaymentsToAcquireProductiveAssets). Existing revenue, net_income and
capital_expenditure definitions are unchanged. SEC queries and explicit batch
plans accept the new names. Yahoo/Nasdaq/Finnhub mark them unsupported until a
separate exact provider mapping is verified; no hidden aliases or guesses.

`PYTHONPATH=src python3 scripts/verify_distinct_fields.py` replays five separately
requested real SEC observations and compares their literal concepts with original
annual filings. Yahoo is unsupported, SEC succeeds, later providers stop. It makes
no financial HTTP request and does not fill the old five narrower missing fields.
Accounting readiness rejects wrong definitions, mixed company/period/currency
inputs and instant/duration confusion; complete data still needs semantic and
sector-model validation. No investment score or scope approval is generated.

Checkpoint packaging uses a unique output directory and full ZIP CRC verification:
`python3 scripts/build_checkpoint.py --test-evidence docs/evidence/distinct-fields-tests.json`.
The worktree must be committed. Preserve the printed immutable path during upload;
verify the saved copy against MANIFEST.json before updating a convenience link.

Traceable financial arithmetic (v0.17.0):

```bash
PYTHONPATH=src python3 scripts/verify_calculations.py
```

Eight immutable formula variants distinguish NetIncomeLoss/ProfitLoss and
contract-revenue/total-Revenues margins, operating-cash-flow margins, and cash
after PP&E/ProductiveAssets payments. Every requested operand must match the
explicit CIK, start/end, currency, exact field definition and cutoff; each needs
a raw source hash. Full source facts are retained in the result. No alternate
field is selected automatically and no missing operand becomes zero.

Ratios are dimensionless (input currency retained separately); payment-subtraction
results retain currency. Zero/negative denominators, negative cash-payment signs,
future observation/publication, wrong periods and missing provenance do not yield
a number. Genuine zero payments and negative profits/cash results remain valid.
Decimal arithmetic uses a local precision context. These cash measures are not
labelled owner earnings or a universally complete free-cash-flow definition.

Recorded sample: 24 arithmetic results and 40 pending formula variants across
eight companies, with no new HTTP request. Every result is arithmetic-only; sector
model, scope and investment approval remain false. No valuation, risk rating or
100-point score is implemented by this module. Stage 3 acceptance remains pending.
