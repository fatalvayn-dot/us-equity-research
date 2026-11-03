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


## MVP report command

Generate reproducible JSON and Markdown from an existing resumable collection:

```sh
PYTHONPATH=src python -m equity_research research-report \
  --input docs/evidence/archived-eight-financial.json \
  --output data/research-report.json --markdown data/research-report.md
```

This recorded eight-company example has 43 accepted input facts and 17 exact
arithmetic results, with zero ranked companies. It is not a fresh live run or
the 100-company acceptance report. Scope/sector approval, valuation prices,
comparable prior-period inputs and score models remain pending. JSON includes
full inputs/provenance and calculation operands; Markdown shows formulas,
values, actual source attempts and reasons scores remain unavailable. No
network call is made by research-report. An export success exit code means the
files were produced, not that MVP acceptance passed.

For a new collection use research-batch with an explicit issuer/period plan,
then supply its JSON to research-report. The batch command remains resumable;
unknown scope and missing data are carried into the report. See
`docs/PROJECT_BRIEF.md` for the approved 48-hour MVP acceptance scope.


## Live MVP collection and report

```sh
PYTHONPATH=src python -m equity_research mvp-run \
  --candidates docs/evidence/sample100-audit-queue.json \
  --state-dir data/mvp100 --user-agent "$SEC_USER_AGENT" \
  --max-new-documents 100 --max-new-fields 900
```

Set SEC_USER_AGENT to an identifying project/contact string. No paid service is
required. This command refreshes/caches SEC submissions, downloads bounded
original annual documents, verifies explicit fiscal starts, collects ordered
Yahoo/SEC/Nasdaq/Finnhub fields and writes `data/mvp100/report.json` and
`report.md`. Run it again with the same state directory to resume. Completed
facts retain their original observation times; pending failures retry after five
minutes. With both work bounds zero, cached metadata/documents/accepted fields
can be reported without new financial work; unresolved jobs remain explicit.
Metadata still refreshes when its six-hour cache expires.

No annual report means financial jobs are unattempted. An explicit annual end
without a verified start supports only Assets/Liabilities; requested duration fields
are deferred, never calendar-inferred. Scope and sector review remain separate
from arithmetic. Export/run success does not mean the MVP acceptance gates pass.
The pipeline records actual public GET invocations (excluding internal retries
and private Finnhub transport), and checks every selected fact's financial,
identity and unit evidence against exact archived response observations.

To make portable public source recordings after the run completes:

```sh
PYTHONPATH=src python scripts/export_mvp_evidence.py \
  --state-dir data/mvp100 --output docs/evidence/mvp100 \
  --sources tests/fixtures/mvp100-sources
```

The export contains gzip JSONL observations split into hash-checked parts, not
operational SQLite caches or headers. `read_bundle` reconstructs and validates
original bytes/URLs/timestamps for recorded replay; replay is not a new live run.


Recorded 2026-11-02 candidate-run evidence is in `docs/evidence/mvp100/report.md`.
It has 100 candidates, 98 with financial queries, 96 with accepted input facts,
536 facts, 272 exact arithmetic results and zero scores. It does not constitute
MVP acceptance: common-share coverage, eligible scoring and price/prior-period
inputs remain pending. Initial live run, expanded completion, recovery and
zero-work resume are recorded separately. Large JSON exports use gzip with a
`reports-manifest.json` of raw/stored hashes. Original 553 public observations
are reconstructed with `read_bundle('tests/fixtures/mvp100-sources')`.

### Annual comparison inputs (recorded-source replay)

```bash
PYTHONPATH=src python scripts/verify_comparative_inputs.py \
  --documents docs/evidence/mvp100/documents.json \
  --sources tests/fixtures/mvp100-sources \
  --output data/comparative-replay
PYTHONPATH=src python -m equity_research comparative-report \
  --input data/comparative-replay/current-batch.json.gz \
  --prior-input data/comparative-replay/prior-batch.json.gz \
  --output data/comparative-replay/research.json \
  --markdown data/comparative-replay/research.md
```

This command replays original public responses offline. It preserves source
observation timestamps, uses a current-session replay cutoff for adapter attempts and
makes no live freshness or historical-vintage claim. Both batches still use the
Yahoo -> SEC -> Nasdaq -> Finnhub first-valid resolver: the Yahoo duration-field
adapter returns its actual local unsupported-field outcome; accepted SEC values
stop fallback. No Yahoo financial HTTP request is invented. Discovery itself
selects periods, not financial field winners, and records no provider attempts.
The exported current/prior plans also work with `research-batch` for fresh ordered
collection using an identifying User-Agent and separate output/checkpoints.

Current periods are reparsed from original annual document contexts. Prior
start/end dates must be literal observations in the same annual accession and
same accounting concept, not inferred from `fy`, `fp` or a calendar frame. A
conservative full-year comparison policy requires consecutive 350–380 day
periods with at most seven days of duration difference. Stub/transition years,
ambiguous dates, conflicting values and mismatched definitions stay unresolved.
Separate literal accounting concepts remain separate fields.

The comparative report revalidates both source-attempt trails before calculating
`current / prior - 1`. SEC operands must share the same snapshot observation and
filing accession. Zero/negative bases do not produce percentages. Every result
retains full source-bound operands, and special/unknown sectors remain in
review. These are arithmetic changes, not proof of organic growth, stable
business perimeter, sector-model acceptance or numeric investment scores.
The recorded evidence is in `docs/evidence/comparative100/`; the MVP remains
unaccepted until all scope, price, scoring and real-acceptance gates pass.

### Source-bound market prices

```bash
export SEC_USER_AGENT='Your research application and existing contact'
PYTHONPATH=src python -m equity_research price-run \
  --candidates docs/evidence/sample100-audit-queue.json \
  --state-dir data/price100 --max-new-prices 100
# Immediate cache-only reproduction; no identity or price HTTP request allowed.
PYTHONPATH=src python -m equity_research price-run \
  --candidates docs/evidence/sample100-audit-queue.json \
  --state-dir data/price100 --max-new-prices 0
PYTHONPATH=src python scripts/export_price_evidence.py \
  --state-dir data/price100 --output docs/evidence/price100 \
  --sources tests/fixtures/price100-sources
```

The CLI writes JSON/Markdown price-input reports. Its default state directory is
`data/prices`, separate from `mvp-run`. A renewable lease prevents concurrent
writers. Original successful response bodies persist incrementally; a 15-minute
raw-response cache and one-day SEC-directory cache preserve original observation
times. A zero-work run uses only available cache entries; absent/expired entries
remain unattempted, never invented missing values. A missing identity cache makes
zero-work execution fail explicitly instead of issuing an HTTP request.

Only the literal Yahoo chart `meta.regularMarketPrice` is accepted: positive
Decimal USD per share, exact uppercase class symbol without punctuation aliases,
SEC symbol/CIK binding, matching explicit US exchange labels and EQUITY metadata.
EQUITY and SEC-directory membership do not establish active common shares or
sector/model eligibility. Nasdaq NMS/NGM/NCM, NYSE NYQ and the explicit ASE/NYSE
American label pair are supported; unknown/conflicting exchanges stay unresolved.
Every price retains market time, first-observed availability/retrieval time,
field definition and raw Yahoo/SEC URLs/hashes. Financial report periods are
never assigned to a market quote. There is no derived share count, market cap,
NAV, adjusted history, after-hours price or executable-quote assertion.

The default quote-age bound is four calendar days, allowing common market
closures while still rejecting stale/future market timestamps. The response-age
bound is separate. Yahoo's [data-provider information](https://help.yahoo.com/kb/SLN2310.html)
was checked on 2026-11-02; reported prices may be delayed. The chart payload is an
observed public-endpoint contract, not a guaranteed stable API. Bounded existing
HTTP transport supplies pacing, timeout/size/retry limits and sanitized access,
quota, network and malformed-data outcomes, without authentication workarounds.

Price selection follows the same first-valid source priority. Successful Yahoo
prices stop before fallback. On failure, SEC's unimplemented market-quote field
is locally unsupported and Nasdaq/Finnhub quote adapters are explicitly
unconfigured; those outcomes do not imply any HTTP request to those providers.
A SEC identity-directory request is reported separately from quote selection.
Recorded 100-candidate evidence and cache-only replay are in
`docs/evidence/price100/`; source bytes are in `tests/fixtures/price100-sources/`.
These inputs do not complete the generic-sector score model or MVP acceptance.

### Liquidity and operating profitability

The literal registry now also supports `current_assets` (AssetsCurrent),
`current_liabilities` (LiabilitiesCurrent), `cash_equivalents`
(CashAndCashEquivalentsAtCarryingValue), `operating_income` (OperatingIncomeLoss)
and `gross_profit` (GrossProfit). `mvp-run` requests all 14 exact fields; when only
an annual end is verified it requests five instant balances and defers all nine
duration fields. Original records are not rewritten or calendar-aligned.

Source-bound arithmetic adds current ratio, cash-equivalents/current-liabilities,
working capital, and operating/gross margin variants using each distinct revenue
concept. Total assets/liabilities never fill current balances. Cash is not
silently combined with investments/restricted cash; operating income is not
inferred EBIT/net income. Instant-only reports can calculate liquidity without
inventing a fiscal-year start. Negative working capital is retained; negative
balance inputs and nonpositive ratio denominators are withheld. These ratios do
not independently prove distress, debt-paying capacity or sector suitability.

```bash
# Offline replay of the immutable 100-candidate recordings.
PYTHONPATH=src python scripts/verify_liquidity_inputs.py \
  --output data/liquidity-verification
# Optional separate three-company fresh SEC/original-filing comparison.
PYTHONPATH=src python scripts/verify_liquidity_inputs.py \
  --output data/liquidity-verification --user-agent "$SEC_USER_AGENT"
PYTHONPATH=src python -m equity_research research-report \
  --input docs/evidence/liquidity100/batch.json.gz \
  --output data/liquidity-report.json --markdown data/liquidity-report.md
```

Recorded replay adds 307 exact fields: 843 total input facts and 576 arithmetic
results across 100 candidates, with 72 current ratios. The 470 additional field
jobs contain 307 collected and 163 unresolved outcomes; none are zero-filled.
This is **not** a fresh 100-company run. A separate fresh AAPL/MSFT/NVDA sample
matched 15/15 literal fields against original SEC annual documents; a separate
three-price sample checked current Yahoo/SEC identity access. Original 100-price
records remain auditable snapshots, not current quotes after their freshness TTL.
Evidence: `docs/evidence/liquidity100/`, `docs/evidence/current-price-sample/`, and
`tests/fixtures/liquidity-live-sources/`. Every new recorded fact re-extracts from
its exact original companyfacts bytes in regression tests. Ratios retain full
operands/periods/currency/definitions/raw hashes and all scope/model approvals
remain false. No complete financial research, valuation, score or MVP acceptance
is implied by these arithmetic counts.

The pinned [TRADE28 review](docs/reviews/TRADE28_REVIEW.md) covers license,
dependencies, scanner/analyst/news/risk/simulation methods and security limits.
The reference was not installed or executed; no third-party code was copied.
# Open the research prototype

The portable browser at `docs/evidence/risk100/report.html` contains the dated
100-candidate snapshot with searchable symbols/CIKs, financial review filters,
calculations, exact source links and hashes. Download/open that HTML file in a
browser. It needs no server or external scripts. It is an inspection prototype;
investment scores and MVP acceptance remain pending.

Rebuild the report from the retained input, without network requests:

```bash
PYTHONPATH=src python -m equity_research research-report \
  --input docs/evidence/liquidity100/batch.json.gz \
  --output data/prototype/report.json \
  --markdown data/prototype/report.md \
  --html data/prototype/report.html
```

Open `data/prototype/report.html`. Run `PYTHONPATH=src python -m unittest discover -s tests -q`
to test the implementation. This command reuses recorded financial observations;
it does not refresh live financial statements or quotes.

Financial review v1 flags reported liabilities above assets and combined annual
loss/operating cash outflow for mandatory review. Operating loss/current balance
shortfall are watch signals. Missing or rejected operands leave a check unresolved.
Favorable other figures cannot remove a mandatory review. These are versioned
screening hypotheses, not insolvency findings, accepted sector models or complete
risk clearance. See `docs/FINANCIAL_REVIEW.md` for definitions and limits.

## Disclosed-share valuation sample

Three companies now have original-filing-verified dated shares joined to sourced
USD quotes and exact annual financial operands. The readable result is
`docs/evidence/valuation-sample/report.md`. These are indicative calculations,
not current market-cap observations or fair values. Remaining 97 source bundles
were not queried in this bounded sample; scores remain unavailable.

Reproduce the exact recorded sample without network requests:

```bash
PYTHONPATH=src python -m equity_research valuation-report \
  --input docs/evidence/liquidity100/batch.json.gz \
  --source-bundle tests/fixtures/valuation-sources \
  --as-of 2026-11-02T20:00:15.589376+00:00 \
  --output data/valuation/report.json --markdown data/valuation/report.md
```

Collect/reuse the bounded AAPL/MSFT/NVDA live source sample with an identifying
User-Agent; retain ignored incremental state and public raw evidence locally:

```bash
PYTHONPATH=src python scripts/verify_valuation_inputs.py \
  --user-agent 'US Equity Research (https://github.com/fatalvayn-dot/us-equity-research)'
```

This checks shares/quotes and selected annual operands; it does not refresh the
entire 100-company annual input batch. Use a separate state directory for a new
sample, via `--state-dir`. Contracts and remaining model gates are documented in
`docs/DISCLOSED_SHARE_VALUATION.md`.

## Explained research-score prototype

Open `docs/evidence/score-pilot/report.html` directly in a browser. It contains
the 100-candidate pilot, two scored research hypotheses, per-component points,
financial definitions, source evidence and explicit unscored/critical-review
reasons. It is not an accepted 100-active-common-share MVP or an investment
approval. Model coverage is limited to SEC SIC 3571/3674/7372. Published rules,
required inputs and dated-share stress assumptions: `docs/RESEARCH_SCORE_MODEL.md`.

Reproduce the exact recorded pilot with no network calls:

```bash
PYTHONPATH=src python -m equity_research score-report \
  --input docs/evidence/liquidity100/batch.json.gz \
  --comparison-input docs/evidence/comparative100/current-batch.json.gz \
  --prior-input docs/evidence/comparative100/prior-batch.json.gz \
  --source-bundle tests/fixtures/valuation-sources \
  --market-bundle tests/fixtures/score-market-sources \
  --as-of 2026-11-02T21:33:48.135379+00:00 \
  --output data/research/report.json --markdown data/research/report.md \
  --html data/research/report.html
```

The fixed cutoff reproduces a dated record; old quotes cannot become current
scores by moving their observation times. The 15-minute quote/history TTL and
six-hour SEC snapshot TTL still apply. Live sample refresh:

```bash
PYTHONPATH=src python scripts/verify_research_score.py \
  --user-agent 'US Equity Research (https://github.com/fatalvayn-dot/us-equity-research)'
```

The bounded AAPL/MSFT/NVDA helper refreshes expired SEC/price inputs through the
existing collector, then fetches/reuses one-year public chart JSON. It maintains
ignored leased state, original response observations and reports under
`data/research-score/`. It does not refresh the retained full 100-company annual
or comparative batches. New annual periods/conflicts therefore require updated
financial inputs and correctly withhold affected scores. No subscription CSV,
API key, authentication workaround, portfolio or trade is used.

## Bounded candidate-driven valuation source collection

`collect-valuation-sources` accepts 1–100 explicit, unique symbol/CIK candidates,
without a hard-coded three-company limit. Candidate files contain
`{"companies":[{"symbol":"MSFT","issuer_id":"0000789019"}]}`.
The input file must be outside the output state directory.

```bash
PYTHONPATH=src python -m equity_research collect-valuation-sources \
  --candidates data/valuation-candidates.json --state-dir data/valuation-collection \
  --max-new-requests 51 \
  --user-agent 'US Equity Research (https://github.com/fatalvayn-dot/us-equity-research)'
```

Each invocation has a hard 0–501 GET-invocation budget (internal HTTP retries are
separately bounded at two attempts per GET, 10-second timeout/25-second budget).
501 covers one directory plus five sources per 100 companies on a successful
cold run. This is a maximum, not a request target. Re-run the same command to
resume partially collected sources; `--max-new-requests 0` is cache-only, including
identity. All public sources share a 0.6-second request interval. Checkpoint
leases exclude overlapping runs and renew before source steps. HTTP failures
are separately persisted with a five-minute cooldown; their status is not
changed to missing. Original dates, URLs and body hashes are retained.

The collector verifies exact US-exchange directory identities, current DEI share
count against the original filing/class, USD Yahoo quotes and one-year daily
history. Each leg has its own status; exhausted-budget and unqueried legs are
explicitly pending. An unrelated successful leg never clears another leg's
failure. Results: `<state-dir>/report.json`, operational SQLite checkpoints and
`<state-dir>/source-bundle/`. The bundle can feed the existing `valuation-report`
or `score-report` with a separately collected financial/comparative batch and
explicit cutoff. No annual financial batch is refreshed by this command, and
it does not alter first-valid Yahoo→SEC→Nasdaq→Finnhub financial field selection.

Dated-share reconciliation is not complete capital-action, fund/legal-type or
active-common-share clearance. This command supplies no scores, fair values,
sector approval or MVP acceptance. Failure and budget limits do not turn
unqueried sources into confirmed data absence. Existing fixed three-company
verification helpers remain compatible for their recorded pilots.

The disclosed-share parser chooses the latest available end/filing-date cohort
before validating its numeric count. A malformed latest count still rejects the
result; it cannot fall back to older shares. Invalid numeric values in unselected
historical rows are explicitly retained as `historical_numeric_review`, with
source accession/date/hash evidence, without correction or use as current data.
Structural/identity/unit/chronology checks and original-filing reconciliation
remain required. This addresses an observed Salesforce 2011 fraction (`133.9`
in a shares unit) without changing the literal 2026 current disclosure.

## Source-bound 100-common-share research sample

`docs/evidence/common100/candidates.json` contains the 100 selected identities.
The audit examined 101 candidates: 83 existing corroborated covers and 18
explicit replacement candidates. 100 passed the versioned listing/identity/
registered-class checks; TER remained under review because the current parser
rejects its original cover structure. `docs/evidence/common100/report.md` and
`report.json.gz` retain the reasons and original source URL/hash/date evidence.
The original 100-candidate financial/price reports are preserved; their 17
unresolved names were not silently reclassified as inactive or non-common.
The replacement set is a convenience development sample with technology bias,
not a representative market sample or historical strategy result.

Rebuild the exact sample from recorded primary bytes with no network calls:

```bash
PYTHONPATH=src python -m equity_research common-sample \
  --candidates docs/evidence/common100/pool.json \
  --base-bundle tests/fixtures/mvp100-sources \
  --source-bundle tests/fixtures/common-extra-sources \
  --as-of 2026-11-03T00:57:20.163470+00:00 \
  --output data/common-sample-replay/report.json \
  --plan-output data/common-sample-replay/candidates.json
```

The policy requires current directory membership/identity within four days,
exact SEC metadata and original latest-annual class/symbol/period corroboration,
a matching primary exchange, and rejection of known investment-company/shell
contraindications. Missing fund tags remain unknown, never false. This narrow
sample gate does not set `scope_approved`, legal-type, financial-model or
investment approval and does not guarantee immediate tradability. Bank,
insurance, REIT, BDC and other unsupported models cannot acquire a score through
sample membership. All sample scores remain unavailable.

The Nasdaq membership files are original 2026-11-02 recordings within the stated
four-day policy. A fresh retrieval attempt failed; they are not presented as new
live downloads. The extra bundle contains 37 newly obtained SEC directory/
metadata/filing observations plus those two dated Nasdaq files. Initial SEC
collection used 35 GET invocations; the TYL reserve added two; the final warm
repeat used zero with unchanged evidence. Headers and operational SQLite are
excluded. New official Nasdaq Trader archive origins are exact allowlisted
public HTTPS hosts, with credential-bearing URLs still rejected.

This does not accept the full MVP. Financial and comparative batches, fresh
prices, sourced valuation/history inputs and the end-to-end acceptance run must
now use this new candidate plan; old 100-company results do not establish its
financial/price coverage. Model scoring and critical-risk gates remain separate.

Observed date presentations now supported include four-digit month-first
numeric dates and full/abbreviated English month names in title/upper case.
Unknown transforms, invalid dates, two-digit numeric years and spoofed transform
namespaces remain rejected by sample admission. Primary definition references:
https://www.xbrl.org/Specification/inlineXBRL-transformationRegistry/REC-2020-02-12/inlineXBRL-transformationRegistry-REC-2020-02-12.html
and
https://www.xbrl.org/Specification/inlineXBRL-transformationRegistry/REC-2015-02-26%2Berrata-2019-04-17/inlineXBRL-transformationRegistry-REC-2015-02-26%2Bcorrected-errata-2019-04-17.html
Only explicit supported subsets are implemented; dates are not inferred from
calendar-year assumptions. Known exchange-name spellings are matched case-
insensitively; symbols/CIKs/classes retain exact matching.

### Prices for this exact common-share plan

`docs/evidence/common-price100/` contains a separate real run for the new plan:
100/100 USD regular-session prices, 100 quote GET invocations plus 1 fresh SEC
identity GET, all raw references archived. Immediate warm resume used zero GETs,
with identical values, source times and identity evidence. These are dated,
potentially delayed market observations, not perpetual current/executable prices.
Raw 101-observation bundle: `tests/fixtures/common-price100-sources/`.

```bash
PYTHONPATH=src python -m equity_research price-run \
  --candidates docs/evidence/common100/candidates.json \
  --state-dir data/common-prices --max-new-prices 100 \
  --user-agent 'US Equity Research (https://github.com/fatalvayn-dot/us-equity-research)'
```

Use `--max-new-prices 0` for cache-only resume; expired/missing entries remain
unstarted and are not fabricated. This price milestone and the exact byte-for-
byte common-sample CLI replay (`docs/evidence/common100/cli-reproduction.json`)
do not complete annual/comparative financial collection, valuation or scoring
for the 17 newly selected companies. Full MVP acceptance remains pending.

## Financial continuation for the new common-share sample

`financial-cohort` selects exact symbol/CIK identities from explicitly supplied
batches. It rejects overlapping source identities and wrong symbols, retains
original field queries/attempts/values/source dates without modification, and
keeps missing companies unresolved. It does not call a provider or manufacture
a current observation date. Company-level caller scores/approvals are discarded.

```bash
PYTHONPATH=src python -m equity_research financial-cohort \
  --candidates docs/evidence/common100/candidates.json \
  --cohort-input docs/evidence/liquidity100/batch.json.gz \
  --cohort-input docs/evidence/common-financial17/batch.json.gz \
  --batch-output data/common-financial100/batch.json \
  --output data/common-financial100/report.json \
  --markdown data/common-financial100/report.md \
  --html data/common-financial100/report.html
```

The committed 100-company continuation has 988 accepted facts and 704 arithmetic
results: 83 previously recorded issuers plus the 17 newly selected issuers. It
is a mixed-date report, not a new live full-100 scan. JSON retains each input's
canonical SHA-256 and generation time; HTML/Markdown display an explicit notice.
No score, rank, sector-model approval or MVP acceptance is granted by assembly.
Open `docs/evidence/common-financial100/report.html` for the portable report.

The separate 17-company collection attempted all 238 field jobs and accepted
186 facts (168 SEC, 14 Yahoo, 4 Nasdaq), producing 141 calculations; 52 jobs
remained pending, never zero-filled. All original financial/identity/unit
references are archived. All 186 values were re-extracted from exact raw bodies. A separate original-SEC
document check for ADBE/INTU/TYL matched 26 selected values; one literal revenue
input was unavailable in both selection and original tags, and remained missing.
Collection used 42 public GET invocations and 35 fresh-in-policy archived body
reuses; seeded observations retained original times. Immediate zero-work resume
used zero public GETs and preserved all accepted fact values/source dates.
This does not validate strategy performance or complete comparative/valuation
coverage for these companies.

MVP collection can now seed public raw bundles and reuse bodies only within
its six-hour freshness policy. Stale/future seed observations are skipped;
seeding never updates retrieval dates or changes first-valid provider order.
Cached responses still pass the transport origin/credential and byte-size guards.
Writable state must be outside source bundles. A completed run writes a final
complete metadata snapshot; exports reject incomplete metadata counts.

```bash
PYTHONPATH=src python -m equity_research mvp-run \
  --candidates docs/evidence/common-financial17/candidates.json \
  --state-dir data/common-financial17-refresh --max-new-documents 17 \
  --max-new-fields 238 \
  --seed-bundle tests/fixtures/common-extra-sources \
  --seed-bundle tests/fixtures/common-financial17-sources \
  --user-agent 'US Equity Research (https://github.com/fatalvayn-dot/us-equity-research)'
```

The delta bundle stores only new source observations; older reused bodies remain
in `common-extra-sources`. Operational SQLite files are not published. Source
attempt counts exclude bounded internal retries and private Finnhub transport.
Pending/unconfigured/unsupported providers are not presented as queried absences.
The next work is exact current/prior annual comparisons and sourced valuation/
history refresh for this precise 100-company plan, followed by explained scores
and a complete acceptance run. Current mixed financial and dated price coverage
do not by themselves complete that acceptance.
