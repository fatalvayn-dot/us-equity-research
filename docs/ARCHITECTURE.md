# Architecture and evidence contracts

| Layer | Contract | Current implementation |
|---|---|---|
| Universe | Active US common shares with identity and timestamp evidence | Identity/scope models; live directory ingestion pending |
| Adapters | Yahoo, SEC, Nasdaq, Finnhub; successful absence returns None; failures are typed | Bounded HTTP, SEC identity and six companyfacts mappings; other sources pending |
| Resolution | Exact issuer, period, unit, currency and accounting meaning; first valid field wins | Resolver and timestamped attempt trail |
| Storage | Accepted facts separate from failures | SQLite cache; raw evidence and incremental collector pending |
| Analysis | Comparable periods and sector-specific valuations | Not implemented |
| Ranking | Complete evidence and validated model required | Weights/readiness specification only |
| Reporting | Conclusions traceable to sources and model version | CLI status only; company reports pending |
| Acceptance | 100, 500, 1,000, full universe with real reconciliation | No real-data gate passed |

Facts use Decimal to avoid float round-trip loss. Request matching requires
exact start/end dates to prevent quarterly values from serving as annual data.
period_start=None denotes an instant, not an unspecified duration. Monetary
units require currency. Accounting definitions are canonical semantics;
adapters must test each vendor mapping.

SEC identity does not prove current listing status or instrument type. Provider
attribution and HTTPS validation do not authenticate a filing: adapters must
enforce source-host allowlists, retain raw evidence and calculate checksums.

Unconfigured sources are not reported as queried. Four successful field absences
are not proof of financial distress or a permanent issuer exclusion. Exception
messages are not retained because they may contain credentials.

Cache keys include source, issuer, full accounting semantics and analysis cutoff.
Cross-run incremental refresh, revisions and large-universe performance remain
unimplemented. Negative results and transport errors are never cached as facts.

Point-in-time protection rejects facts available OR retrieved after the cutoff.
A current download cannot establish historical knowledge, even if its period
is old. Historical vintage validation, restatements, delistings and survivorship
controls remain required. An as_of cutoff refers to the completed evidence
snapshot, not the instant before a network fetch starts.

## Planned 100-company gate

Use a reproducible sector-stratified sample of actual active common shares.
Archive the universe timestamp, identities and corporate-action evidence.
For every metric retain raw-response digest, URL, reporting period, units,
mapping version and retrieval/publication time. Reconcile a documented sample
against filings and report coverage and failures separately. Set numeric
freshness/accuracy thresholds before testing; never tune them after the output.
No threshold or sector model has yet been accepted.

## SEC directory implementation (2026-11-01)

The official company_tickers_exchange.json endpoint is fetched directly with
an identifying User-Agent. Fields are resolved by name rather than position.
The parser rejects malformed rows, duplicate symbols and noncanonical CIKs;
multiple share classes can share one CIK. Symbol case is normalized but class
punctuation is preserved. Missing lookup is an identity lookup result, never
financial field absence. The adapter produces DirectoryEntry, not Security,
because this SEC file does not establish security type or active status.

Transport uses exact HTTPS host allowlists, no redirects, bounded payloads,
JSON duplicate-key/nonfinite rejection, capped attempts, rate pacing and
Retry-After handling. 401/403 are access_denied; 429 is rate_limit; timeout is
separate. HTTP 404 is not proof that a financial field is missing. Error bodies
and credential-containing exception messages are never persisted.

Source policy checked on 2026-11-01:
https://www.sec.gov/search-filings/edgar-search-assistance/accessing-edgar-data
The SEC explicitly does not guarantee the accuracy/scope of ticker associations.
Identity-directory success does not accept any financial-connection gate.

## Companyfacts adapter and original filing checks

Mappings in companyfacts.TAGS are deliberately exact, versioned in source and
limited to six monetary US-GAAP concepts. Instant versus duration, period bounds,
source currency and accounting definition must match the request. Eligible
10-K/10-Q records are selected by latest filing date; same-day conflicting values
fail closed. Unsupported fields/IFRS-only taxonomies are not data absence.
Decimal JSON parsing preserves fractional precision. Facts retain original
accession/date/checksum, including through SQLite round trips.

Snapshot cache stores the raw response and its retrieval time/hash atomically,
verifies integrity and refreshes stale/corrupt entries. Six-hour TTL limits repeat
requests; this is not yet filing-event incremental refresh. Source public date
is approximated conservatively at 05:00 UTC on the next date; do not use it as
an exact acceptance timestamp. Prefetch before fixing a new snapshot cutoff.

filingcheck is a narrow independent Assets verifier: match entity CIK, instant,
non-dimensional context, declared USD unit and numeric scale in original iXBRL.
It rejects ambiguous values and unsupported transforms. It is not a complete
XBRL processor and does not validate all financial concepts.

Official schema reviewed 2026-11-01:
https://www.sec.gov/search-filings/edgar-application-programming-interfaces

## Yahoo and live collection cutoff

Yahoo TotalAssets maps to total assets only; all other requested fields report
unsupported_field until period/definition evidence is implemented. SEC identity
snapshot binds exact symbol/CIK (one-day freshness), while Yahoo response metadata
must echo that symbol and annualTotalAssets. Class punctuation is never aliased.
Wrong-day observations in the requested year/month report period_mismatch rather
than being calendar-aligned. Missing exact observations, API errors, quota,
access blocks, malformed payloads and unsupported concepts remain distinct.

FactQuery expresses current collection without a preset historical cutoff.
resolve_current calls optional provider.prepare only in source order, then sets
that provider's cutoff and validates its returned Fact. No later provider is
prepared after success. This fixes fresh downloads being rejected merely because
a request cutoff was created milliseconds before the HTTP response. The fixed
FactRequest path retains its original cutoff and strict historical-vintage guard.

Yahoo identity evidence and raw/vendor field provenance are persisted in facts.
Publication is unknown; availability is conservatively first observed retrieval.
The Yahoo adapter is not a complete finance source and has no historical vintage
or disk cache yet. Confirmed source integration is limited to three Assets cases.

Endpoint/schema reference reviewed 2026-11-01 (upstream implementation, not an
official Yahoo API stability guarantee):
https://github.com/ranaroussi/yfinance/blob/main/yfinance/scrapers/fundamentals.py

## Nasdaq universe and discovery separation

nasdaq.py parses both official Trader directory schemas, exact exchange codes,
ETF/test/NextShares flags, financial warning fields and source footer dates.
The footer has no declared timezone, so only its calendar date is used and its
original text is retained. Classification is exhaustive across source rows;
unknown metadata/type, stale snapshots, ambiguous aliases and SEC exchange
conflicts cannot become candidates. Bankruptcy flags remain visible as risk
metadata rather than causing silent deletion. A candidate is not a final
verified active Security; legal fund types and halt/current-listing checks remain.

nasdaq_screener.py is an explicitly weaker discovery fallback. It checks complete
pagination, bounded counts, duplicate symbols, stable totals and labels; retains
original padded symbols; and exposes only symbol/name, without inventing exchange,
ETF/test/security-type or activity fields. Its last-price label must not be
reused as a listing timestamp. Source total=observed count is a discovery
integrity check, not proof that all active US common equities are included.

Official metadata definitions reviewed 2026-11-01:
https://www.nasdaqtrader.com/trader.aspx?id=symboldirdefs
Screener source: https://www.nasdaq.com/market-activity/stocks/screener
Actual response URLs, times and hashes are recorded with the fixtures. Trader
files returned an HTTP 503 during diagnostic access; they have no successful
live acceptance evidence in this checkpoint. Nasdaq financial fields are still
not an implemented provider in the first-valid financial resolver.

## Finnhub authentication and parser contract

FinnhubConfig reads only the two explicit environment names, hides the credential
from repr, and rejects conflicting values. No scanning of unrelated files or
legacy secrets is performed. Authenticated transport permits X-Finnhub-Token
only with the single exact finnhub.io origin, rejects credential query parameters,
refuses redirects and drops successful bodies that echo the configured token.
URLs, Facts and diagnostic errors retain no token. Authentication/error response
strings are mapped to typed failures without persisting their original contents.

FinnhubReported queries reported financials by CIK, frequency and exact end date;
verifies top-level and report CIK; accepts only exact configured GAAP concepts,
explicit monetary unit, period, filing metadata and nonconflicting raw Decimal
value. Unsupported legacy shapes are not assigned USD or scaled by guesswork.
Whole-entity context cannot be assumed from explicit segment/dimensional rows.
Current supported strict arrays still require real endpoint/account validation.
Memory cache reuses accepted raw snapshot evidence; disk/filing refresh is pending.

Official references reviewed on 2026-11-02 (local date):
https://finnhub.io/docs/api/financials-reported
https://github.com/Finnhub-Stock-API/finnhub-go
https://github.com/Finnhub-Stock-API/finnhub-go/blob/master/api/openapi.yaml
The official SDK demonstrates header authentication; its OpenAPI provides endpoint,
CIK/date/frequency/report contracts. Report.report remains loosely typed, so the
per-concept unit-bearing parser is deliberately unaccepted until a real response
is checked. No package dependency was added for the production client.

## Nasdaq financial evidence and lazy pipeline

NasdaqFinancials maps only two instant balance-sheet labels to Assets/Liabilities.
Its numeric parser rejects ambiguous comma/sign/currency strings and preserves
missing cells; no guessed zero. It requires exact period columns and a fresh SEC
symbol/CIK match, verifies vendor response symbol, and rejects duplicate labels
or dates. It never infers a duration start from a year-end caption.

API scale is not self-describing. The adapter independently fetches the same
symbol's official financial page, verifies title/heading identity and exactly one
visible currency/Thousands/Millions/Billions caption, ignoring scripts/styles.
Currency, multiplier, page/data hashes and separate timestamps remain in Fact,
including SQLite round trips. Overall retrieval/availability use the completed
evidence time; original observation timestamps are retained separately. Historical
fixed cutoffs still reject later evidence. Memory TTL covers both responses.

DeferredProvider creates each provider only when reached. The current-source
factory wires Yahoo, SEC, Nasdaq, Finnhub in policy order; missing or invalid
Finnhub configuration is not examined if an earlier provider succeeds. Factory
source mismatch/configuration failure remains typed and sanitized. research-fact
adds one fresh identity lookup before the financial source chain, not an eager
financial request to SEC or any lower-priority provider.

Reference reviewed 2026-11-02: https://www.nasdaq.com/market-activity/stocks/aapl/financials
Actual API/page URLs and raw bytes for AAPL/MSFT/NVDA are in the live evidence
manifest; the unit label is not generalized to unverified pages or EPS/ratios.


Batch evidence checkpoint: batch.py stores per-field source trails and validated
facts, keyed by symbol/CIK, exact query and policy version. Resume validates both
SHA-256 integrity and fact/query/chronology/source-order semantics. Freshness uses
original data observation time, not resume time. Missing/error observations have
short retry TTLs and never become zero-valued facts. Out-of-scope tasks are
skipped before provider creation. Provider/identity factory failures preserve
typed status but no exception text. SQLite transactions and an owner/expiry lease
prevent overlapping checkpoint writes; they do not coordinate different database
files or provide historical/security-level universe acceptance. Scope approval
is deliberately unavailable until affirmative listing/type evidence exists.


Primary listing audit: scope.audit_sample exhaustively reconciles explicit
sample symbol/CIK pairs against both Nasdaq Trader directories and a fresh SEC
identity directory. Each row retains flags, raw-source hashes and dates, source
classification and identity provenance. Both transport origins are exact
allowlisted official endpoints; fallback attempts are separate and do not mark
unqueried endpoints as tried. Scope evidence has a four-day maximum age at the
recorded observation cutoff. Missing/stale/colliding/disagreeing evidence stays
pending. Even complete listing evidence cannot approve legal issuer type or
investment suitability. Replay uses original observation time and is explicitly
labelled offline; it never refreshes the source observation timestamp.

Submissions evidence layer: SecSubmissions uses exact CIK URL/response matching,
strict columnar history parsing and explicit annual end dates. Safe unsupported
legacy filenames remain metadata; document_format controls future parser
eligibility. Six-hour SQLite entries preserve source observation, bytes and hash;
corrupt entries trigger typed diagnostics and a new fetch. Factory/cache failures
do not manufacture a financial fact. A current snapshot is not a historical
filing-availability database; no acceptance-label timezone or date alignment is
inferred. Older-history pointers are counted but not fetched automatically.

filing_metadata is a separate narrow cover corroborator, retaining per-class
contexts and exact document date/form. Non-common securities sharing a ticker
are ignored for common-title matching; conflicting common matches fail. Raw
shell/investment-company labels and registered title evidence remain separate
from legal-type determination. Neither this parser nor submissions changes the
scope approval gate or bypasses the financial-source resolver order.

Annual duration evidence: annual_period consumes original filing bytes and
requires a single explicit issuer duration shared by annual document type, FY
focus and exact document end, excluding segment/class contexts. Starts are never
calendar-derived; current end/type are checked against submissions metadata.
Multiple equivalent contexts are retained; competing starts fail. Duration
limits deliberately leave exceptional long transition periods unsupported.
CoverParser now tracks nested numeric-free facts with a stack so an inner
untracked fiscal-year-end fact cannot truncate its parent document date. This
is a narrow evidence parser, not a general XBRL engine; continuations/exclusions
and unsupported transformations fail closed. Period readiness and registered
share evidence are independent; neither grants legal/scope approval.

Document checkpoints: FilingStore extends the same-file SQLite lease mechanism
with raw annual bodies keyed by exact issuer/annual metadata. Origin/path/date
validation precedes network I/O; only expected source URLs enter raw storage.
Every source and final per-company outcome is transactionally committed under
an owner/expiry lease. Derived outcomes are versioned and retained for diagnosis;
current parsers always recompute from original source bytes. A failed parser does
not erase a valid download or become a financial fact. An interrupted process
leaves prior committed sources/outcomes available; hard termination can require
15-minute lease expiry. Cache use is bounded to original observation plus six
hours, separately from current listing or legal-type freshness/approval.

ResponseArchive separates immutable content-addressed public bodies from
URL/hash/original-time observations. Exact-time lookup prevents evidence from a
later request being passed off as an earlier observation. ArchivedTransport
persists only a successfully bounded, unauthenticated public transport response;
headers and credential-bearing URLs are excluded. Archive errors propagate as
evidence_error, not API_ERROR. ArchivedCompanyFacts captures original cached SEC
responses too, so disk hits remain replayable without new HTTP. Source ordering
and lazy client creation are preserved; archiving does not query a lower provider
for corroboration after the first valid financial fact. Independent original
filing comparison is a separate diagnostic, not a resolver fallback or score.

Concept diagnostics are isolated from financial resolution. Inventory preserves
original numeric facts, issuer/period/dimensional context, declared USD unit and
namespace/transform bindings. A constrained Decimal decoder rejects unsupported
presentation or competing requested-context values. Exact duration checks do not
borrow prior periods or segment facts. Alternative concepts are reported with
their literal taxonomy identity and are never injected as request-equivalent
facts. Arithmetic identity candidates retain operands/formula and an explicit
unaccepted status; an absent component is never assumed zero. Source URL/hash/
original retrieval metadata is reused from the archived annual documents.

The frozen FieldSpec registry owns literal accounting identities and instant/
duration shapes. TAGS remains the compatible SEC/batch projection. New broader
concepts are independently requestable; no provider may return one for a narrower
field. Unsupported provider mappings stop before HTTP. Accounting readiness checks
required literal definitions and issuer/period/currency alignment, retaining
semantic-review flags and a sector-model-pending state even for complete inputs.

Checkpoint packaging is isolated from recurring canonical paths. The builder
requires a clean committed worktree, verifies a complete Git bundle, snapshots
only known public evidence databases, writes a new exclusive ZIP, and verifies
all CRCs and the commit marker. An external manifest records the final SHA-256.
After writeback, verify the retained bytes in an independent destination before
claiming durable delivery; never overwrite the immutable upload source path.

Calculations are downstream of exact Facts and separate from acquisition. A
frozen formula registry declares literal operand identities; caller supplies
issuer, duration, input currency and aware cutoff. FactRequest.rejection enforces
identity/semantics/period/knowledge boundaries per operand. Missing fields,
invalid inputs, denominator/sign and magnitude problems are typed outputs with
no value. Successful results retain complete input provenance and explicit
semantic-review flags. Decimal computation has isolated precision; no global
rounding state or provider fallback influences the formula. Calculation success
never grants sector-model, scope or investment approval. No historical-vintage
claim follows from replaying currently observed historical-period facts.
