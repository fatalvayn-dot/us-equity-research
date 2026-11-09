"""Bounded source acquisition for explicit candidates; never scope or score approval."""
import hashlib
import json
import re
from collections import Counter
from dataclasses import asdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlsplit

from .batch import BatchStore
from .companyfacts import companyfacts_url
from .evidence_bundle import write_bundle, read_bundle
from .market_history import history_url, parse_history
from .models import aware
from .mvp import validate_candidates, save_json
from .prices import cached_response, parse_price, price_url, _identity, IDENTITY_TTL, PRICE_TTL
from .providers import ProviderFailure, Status
from .response_archive import ResponseArchive, ArchivedTransport
from .sec import DIRECTORY_URL, parse_directory
from .submissions import parse_submissions, submissions_url
from .transport import RateLimiter, strict_json
from .valuation import disclosed_shares, verify_share_class, SNAPSHOT_TTL

LEASE_TTL = timedelta(minutes=15)
RETRY_DELAY = timedelta(minutes=5)
MAX_SOURCE_BYTES = 16_000_000
SEED_MAX_AGE = timedelta(hours=6)


class CollectionPending(Exception):
    pass


def candidate_rows(payload):
    rows = validate_candidates(payload)
    for row in rows:
        price_url(row['symbol'])
    return rows


def request_limit(value):
    if type(value) is not int or not 0 <= value <= 501:
        raise ValueError('0..501 new GET invocations required for at most 100 candidates')
    return value


class ValuationSourceCollector:
    def __init__(self, archive, transports, *, max_new_requests, checkpoint, owner, clock=None):
        self.archive, self.transports = archive, transports
        self.limit = request_limit(max_new_requests)
        self.checkpoint, self.owner = checkpoint, owner
        self.clock = clock or (lambda: datetime.now(timezone.utc))
        if not aware(self.clock()):
            raise ValueError('aware collection clock required')
        self.calls = Counter()

    def get(self, url, ttl, attempts, stage, *, not_before=None):
        now = self.clock()
        outcome = dict(stage=stage, url=url, checked_at=now.isoformat(), http_requested=False, cached=False)
        attempts.append(outcome)
        self.checkpoint.renew(self.owner, now, LEASE_TTL)
        response = cached_response(self.archive, url, now, ttl)
        if response is not None and not_before is not None and response.retrieved_at < not_before:
            response = None
        if response is not None:
            outcome.update(status='body_available', cached=True)
        else:
            key = hashlib.sha256(('valuation-source-failure-v1:' + url).encode()).hexdigest()
            failure = self.checkpoint.read(key)
            if failure and timedelta(0) <= now - datetime.fromisoformat(failure['failed_at']) < RETRY_DELAY:
                outcome.update(status=failure['status'], deferred_reason='retry_cooldown',
                               http_status=failure['http_status'], failure_reason=failure['failure_reason'])
                raise CollectionPending()
            if sum(self.calls.values()) >= self.limit:
                outcome.update(status='not_started', deferred_reason='request_budget')
                raise CollectionPending()
            host = urlsplit(url).hostname
            self.calls[host] += 1
            outcome['http_requested'] = True
            try:
                response = self.transports[host].get(url)
                if (response.url != url or not aware(response.retrieved_at)
                        or not timedelta(0) <= self.clock() - response.retrieved_at <= ttl
                        or (not_before is not None and response.retrieved_at < not_before)):
                    raise ProviderFailure(Status.INVALID_DATA)
                self.archive.record(response)
            except ProviderFailure as exc:
                outcome.update(status=exc.status.value, http_status=exc.http_status,
                               failure_reason=exc.reason.value if exc.reason else None)
                self.checkpoint.write(key, dict(status=exc.status.value, failed_at=self.clock().isoformat(),
                    http_status=exc.http_status, failure_reason=exc.reason.value if exc.reason else None),
                    self.owner, self.clock(), LEASE_TTL)
                raise CollectionPending() from None
            outcome['status'] = 'body_available'
        if len(response.body) > MAX_SOURCE_BYTES:
            outcome['status'] = Status.INVALID_DATA.value
            raise ProviderFailure(Status.INVALID_DATA)
        outcome.update(raw_sha256=response.sha256, retrieved_at=response.retrieved_at.isoformat())
        return response

    @staticmethod
    def reject(row, leg, exc):
        row[leg] = dict(status=exc.status.value if isinstance(exc, ProviderFailure) else 'invalid_data')

    def collect(self, payload):
        rows = candidate_rows(payload)
        # A fixed head-first budget can starve the back of a 100-company
        # cohort forever when prices expire between scheduled runs.
        # Store only an ordered-candidate-bound position, not cached approval.
        fingerprint = hashlib.sha256(json.dumps(
            [(r['symbol'], r['issuer_id']) for r in rows],
            separators=(',', ':')).encode()).hexdigest()
        cursor_key = 'valuation-candidate-cursor-v1'
        prior = self.checkpoint.read(cursor_key) if self.limit else None
        cursor_matches = (isinstance(prior, dict)
                          and prior.get('fingerprint') == fingerprint
                          and type(prior.get('next_index')) is int
                          and 0 <= prior['next_index'] < len(rows))
        start = prior['next_index'] if cursor_matches else 0
        retrying_partial = cursor_matches and prior.get('retrying_partial') is True
        scan = rows[start:] + rows[:start]
        last_requested_index = None
        last_request_partial = False
        identity_attempts = []
        identity = None
        identity_validation = dict(status='not_started')
        try:
            identity = self.get(DIRECTORY_URL, IDENTITY_TTL, identity_attempts, 'identity')
            parse_directory(identity)
            identity_validation = dict(status='valid', raw_sha256=identity.sha256, retrieved_at=identity.retrieved_at.isoformat())
        except CollectionPending:
            identity_validation = dict(status=identity_attempts[-1]['status'])
            identity = None
        except (ProviderFailure, ValueError, KeyError, TypeError) as exc:
            identity_validation = dict(status=exc.status.value if isinstance(exc, ProviderFailure) else 'invalid_data')
            identity = None
        companies = []
        for offset, row in enumerate(scan):
            result = dict(**row, attempts=[], identity_status='not_started',
                share_check=dict(status='not_started'), price_check=dict(status='not_started'),
                history_check=dict(status='not_started'), scope_approved=False,
                sector_model_supported=False, investment_approved=False, total_score=None, rank=None)
            companies.append(result)
            if identity is None:
                result['identity_status'] = 'identity_unavailable'
                continue
            cik, symbol = row['issuer_id'], row['symbol']
            try:
                entry = _identity(identity, cik, symbol, self.clock(), IDENTITY_TTL)
                if entry.exchange_label not in ('NYSE', 'Nasdaq', 'NYSE American'):
                    result['identity_status'] = 'out_of_scope_exchange'
                    continue
                result['identity_status'] = 'exact_match'
            except (ProviderFailure, ValueError) as exc:
                result['identity_status'] = exc.status.value if isinstance(exc, ProviderFailure) else 'invalid_data'
                continue
            shares = None
            try:
                cf = self.get(companyfacts_url(cik), SNAPSHOT_TTL, result['attempts'], 'companyfacts')
                shares = disclosed_shares(cf, cik=cik, as_of=self.clock())
                if shares is None:
                    result['share_check'] = dict(status='missing_disclosed_shares')
                else:
                    meta = self.get(submissions_url(cik), SNAPSHOT_TTL, result['attempts'], 'submissions')
                    snapshot = parse_submissions(meta, cik)
                    if symbol not in snapshot.tickers:
                        raise ProviderFailure(Status.SYMBOL_MISMATCH)
                    recent = strict_json(meta.body)['filings']['recent']
                    indices = [i for i, value in enumerate(recent['accessionNumber']) if value == shares['accession']]
                    if len(indices) != 1:
                        raise ValueError('share filing absent or ambiguous')
                    document = recent['primaryDocument'][indices[0]]
                    if not re.fullmatch(r'[A-Za-z0-9_-][A-Za-z0-9_.-]*', document) or '..' in document:
                        raise ValueError('unsafe filing path')
                    url = f'https://www.sec.gov/Archives/edgar/data/{int(cik)}/{shares["accession"].replace("-", "")}/{document}'
                    filing = self.get(url, SNAPSHOT_TTL, result['attempts'], 'original_share_filing')
                    verified = verify_share_class(shares, meta, filing, symbol=symbol, as_of=self.clock())
                    result['share_check'] = dict(status='verified_dated_share_class', evidence=verified)
            except CollectionPending:
                result['share_check'] = dict(status='pending_source_collection')
            except (ProviderFailure, ValueError, KeyError, TypeError) as exc:
                self.reject(result, 'share_check', exc)
            price = None
            try:
                quote = self.get(price_url(symbol), PRICE_TTL, result['attempts'], 'price', not_before=identity.retrieved_at)
                price = parse_price(quote, identity, cik=cik, symbol=symbol, as_of=self.clock())
                result['price_check'] = dict(status='valid' if price else 'missing', evidence=asdict(price) if price else None)
            except CollectionPending:
                result['price_check'] = dict(status='pending_source_collection')
            except (ProviderFailure, ValueError, KeyError, TypeError) as exc:
                self.reject(result, 'price_check', exc)
            if price is not None and result['share_check']['status'] != 'verified_dated_share_class':
                result['history_check']['deferred_reason'] = 'share_class_unverified'
            elif price is not None:
                try:
                    history = self.get(history_url(symbol), PRICE_TTL, result['attempts'], 'history', not_before=price.market_at)
                    market = parse_history(history, identity, cik=cik, symbol=symbol, share_date=shares['end'],
                                           price_market_at=price.market_at, as_of=self.clock())
                    result['history_check'] = dict(status='valid', evidence=market)
                except CollectionPending:
                    result['history_check'] = dict(status='pending_source_collection')
                except (ProviderFailure, ValueError, KeyError, TypeError) as exc:
                    self.reject(result, 'history_check', exc)
            if any(a.get('http_requested') for a in result['attempts']):
                last_requested_index = (start + offset) % len(rows)
                last_request_partial = any(
                    a.get('deferred_reason') == 'request_budget' for a in result['attempts'])
        next_index = None
        if last_requested_index is not None:
            # Resume the boundary company once so its cached partial work can
            # finish. Then rotate even if expired inputs consume the budget again.
            retry_partial = last_request_partial and not (
                retrying_partial and last_requested_index == start)
            next_index = (last_requested_index + (0 if retry_partial else 1)) % len(rows)
            self.checkpoint.write(cursor_key, dict(fingerprint=fingerprint,
                next_index=next_index, retrying_partial=retry_partial),
                self.owner, self.clock(), LEASE_TTL)
        order = {r['issuer_id']: i for i, r in enumerate(rows)}
        companies.sort(key=lambda company: order[company['issuer_id']])
        return dict(schema_version=1, report_kind='valuation_source_collection_scope_pending',
            as_of=self.clock().isoformat(), companies=companies, identity_attempts=identity_attempts,
            identity_validation=identity_validation,
            continuation=dict(start_symbol=rows[start]['symbol'],
                next_symbol=rows[next_index]['symbol'] if next_index is not None else None),
            summary=dict(candidates=len(companies), new_get_invocations=sum(self.calls.values()),
                get_invocations_by_host=dict(self.calls),
                identity_states=dict(Counter(c['identity_status'] for c in companies)),
                share_states=dict(Counter(c['share_check']['status'] for c in companies)),
                price_states=dict(Counter(c['price_check']['status'] for c in companies)),
                history_states=dict(Counter(c['history_check']['status'] for c in companies))),
            max_new_requests=self.limit, mvp_accepted=False, hundred_active_common_shares_accepted=False,
            request_measure='GET invocations excluding bounded internal retries',
            limitations=['No annual financial batch refresh or first-valid field replacement',
                'Dated share reconciliation is not all capital actions, fund/legal or active common-share clearance',
                'No scores, sector model, fair value or investment approval; unqueried legs stay not started'])


def seed_sources(archive, bundles, *, clock, pulse):
    counts = Counter()
    for bundle in bundles:
        for response in read_bundle(bundle):
            pulse()
            if len(response.body) > MAX_SOURCE_BYTES:
                counts['oversized_observations'] += 1
            elif not timedelta(0) <= clock() - response.retrieved_at <= SEED_MAX_AGE:
                counts['outside_seed_freshness'] += 1
            else:
                archive.record(response)
                counts['imported_observations'] += 1
    return dict(counts)


def run_collection(payload, *, state_dir, user_agent, max_new_requests=51, seed_bundles=(), clock=None):
    rows = candidate_rows(payload)
    request_limit(max_new_requests)
    path = Path(state_dir).resolve()
    bundles = tuple(Path(p).resolve() for p in seed_bundles)
    if any(p == path or p in path.parents or path in p.parents for p in bundles):
        raise ValueError('Değerleme çalışma dizini kaynak paketlerinden ayrı olmalıdır')
    clock = clock or (lambda: datetime.now(timezone.utc))
    path.mkdir(parents=True, exist_ok=True)
    lock = BatchStore(path/'run-lock.sqlite'); archive = ResponseArchive(path/'sources.sqlite')
    owner = None
    try:
        owner = lock.acquire(clock(), LEASE_TTL)
        seeded = seed_sources(archive, bundles, clock=clock,
                              pulse=lambda: lock.renew(owner, clock(), LEASE_TTL))
        limiter = RateLimiter(.6)
        transports = {host: ArchivedTransport(archive=archive, user_agent=user_agent, allowed_hosts={host},
            limiter=limiter, timeout=10, budget=25, max_attempts=2, max_bytes=MAX_SOURCE_BYTES)
            for host in ('www.sec.gov', 'data.sec.gov', 'query1.finance.yahoo.com')}
        collector = ValuationSourceCollector(archive, transports, max_new_requests=max_new_requests,
                                             checkpoint=lock, owner=owner, clock=clock)
        report = collector.collect(dict(companies=rows))
        report['candidate_plan'] = dict(companies=rows)
        report['seed_summary'] = seeded
        report['source_bundle'] = write_bundle(archive, path/'source-bundle')
        save_json(path/'report.json', report)
        return report
    finally:
        if owner is not None:
            lock.release(owner)
        archive.close(); lock.close()
