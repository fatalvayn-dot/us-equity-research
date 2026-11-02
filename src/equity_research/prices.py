"""Sourced regular-session prices, separate from accounting facts and scope approval."""
import re
from collections import Counter
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from enum import Enum
from pathlib import Path
from urllib.parse import quote

from .batch import BatchStore
from .models import Source, aware
from .providers import ProviderFailure, Status
from .response_archive import ResponseArchive, ArchivedTransport
from .sec import DIRECTORY_URL, parse_directory
from .transport import strict_json

PRICE_TTL = timedelta(minutes=15)
IDENTITY_TTL = timedelta(days=1)
QUOTE_MAX_AGE = timedelta(days=4)
EXCHANGES = {'NMS': 'Nasdaq', 'NGM': 'Nasdaq', 'NCM': 'Nasdaq', 'NYQ': 'NYSE', 'ASE': 'NYSE American'}


class PriceIssue(str, Enum):
    STALE_QUOTE = 'stale_quote'
    STALE_RESPONSE = 'stale_response'
    STALE_IDENTITY = 'stale_identity'
    FUTURE_OBSERVATION = 'future_observation'
    UNSUPPORTED_INSTRUMENT = 'unsupported_instrument'
    UNSUPPORTED_EXCHANGE = 'unsupported_or_conflicting_exchange'
    CURRENCY_MISMATCH = 'currency_mismatch'


class PriceFailure(ProviderFailure):
    def __init__(self, issue):
        self.issue = PriceIssue(issue)
        super().__init__(Status.INVALID_DATA)


class PriceNotStarted(Exception): pass


def price_url(symbol):
    if not isinstance(symbol, str) or not re.fullmatch(r'[A-Z][A-Z0-9.-]{0,15}', symbol):
        raise ValueError('exact uppercase class symbol required; no punctuation conversion')
    return 'https://query1.finance.yahoo.com/v8/finance/chart/' + quote(symbol, safe='') + '?interval=1d&range=5d'


def _identity(response, cik, symbol, as_of, ttl):
    price_url(symbol)
    if not isinstance(cik, str) or not re.fullmatch(r'[0-9]{10}', cik) or int(cik) == 0:
        raise ValueError('canonical nonzero issuer required')
    if not aware(as_of) or not aware(response.retrieved_at):
        raise ProviderFailure(Status.INVALID_DATA)
    if not timedelta(0) <= as_of - response.retrieved_at <= ttl:
        raise PriceFailure(PriceIssue.STALE_IDENTITY)
    entry = parse_directory(response).lookup(symbol, expected_cik=cik)
    if entry is None: raise ProviderFailure(Status.SYMBOL_MISMATCH)
    return entry


@dataclass(frozen=True)
class MarketPrice:
    issuer_id: str
    symbol: str
    value: Decimal
    currency: str
    exchange: str
    source: Source
    source_field: str
    definition: str
    unit: str
    market_at: datetime
    retrieved_at: datetime
    available_at: datetime
    source_url: str
    raw_sha256: str
    identity_evidence_url: str
    identity_evidence_sha256: str
    identity_observed_at: datetime
    instrument_label: str
    scope_approved: bool = field(default=False, init=False)
    sector_model_supported: bool = field(default=False, init=False)
    investment_approved: bool = field(default=False, init=False)

    def __post_init__(self):
        if (not re.fullmatch(r'[0-9]{10}', self.issuer_id) or int(self.issuer_id) == 0
                or self.source is not Source.YAHOO or self.source_url != price_url(self.symbol)
                or not isinstance(self.value, Decimal) or not self.value.is_finite() or self.value <= 0
                or self.currency != 'USD' or self.unit != 'currency_per_share'
                or self.exchange not in EXCHANGES or self.instrument_label != 'EQUITY'
                or self.identity_evidence_url != DIRECTORY_URL
                or not all(re.fullmatch(r'[0-9a-f]{64}', h) for h in (self.raw_sha256, self.identity_evidence_sha256))):
            raise ValueError('invalid market price contract')
        if (not all(aware(t) for t in (self.market_at, self.retrieved_at, self.available_at, self.identity_observed_at))
                or self.market_at > self.retrieved_at or self.identity_observed_at > self.retrieved_at
                or self.available_at != self.retrieved_at):
            raise ValueError('invalid price evidence chronology')


def parse_price(response, identity, *, cik, symbol, as_of,
                price_ttl=PRICE_TTL, identity_ttl=IDENTITY_TTL, quote_max_age=QUOTE_MAX_AGE):
    if min(price_ttl, identity_ttl, quote_max_age) <= timedelta(0):
        raise ValueError('positive freshness policies required')
    entry = _identity(identity, cik, symbol, as_of, identity_ttl)
    if response.url != price_url(symbol) or not aware(response.retrieved_at):
        raise ProviderFailure(Status.INVALID_DATA)
    if response.retrieved_at > as_of or identity.retrieved_at > response.retrieved_at:
        raise PriceFailure(PriceIssue.FUTURE_OBSERVATION)
    if as_of - response.retrieved_at > price_ttl:
        raise PriceFailure(PriceIssue.STALE_RESPONSE)
    payload = strict_json(response.body)
    try:
        chart = payload['chart']
        if not isinstance(chart, dict): raise ValueError('chart object required')
        if chart.get('error') is not None:
            error = chart['error']
            code = error.get('code', '') if isinstance(error, dict) else ''
            if not isinstance(code, str): raise ValueError('invalid error code')
            code = code.lower()
            status = (Status.ACCESS_DENIED if code in ('unauthorized', 'forbidden') else
                      Status.RATE_LIMIT if code in ('too many requests', 'ratelimit') else Status.API_ERROR)
            raise ProviderFailure(status)
        results = chart['result']
        if not isinstance(results, list) or len(results) != 1: raise ValueError('one exact result required')
        meta = results[0]['meta']
        if meta['symbol'] != symbol: raise ProviderFailure(Status.SYMBOL_MISMATCH)
        if meta['instrumentType'] != 'EQUITY': raise PriceFailure(PriceIssue.UNSUPPORTED_INSTRUMENT)
        exchange = meta['exchangeName']
        if exchange not in EXCHANGES or EXCHANGES[exchange] != entry.exchange_label:
            raise PriceFailure(PriceIssue.UNSUPPORTED_EXCHANGE)
        if meta.get('exchangeTimezoneName') != 'America/New_York':
            raise PriceFailure(PriceIssue.UNSUPPORTED_EXCHANGE)
        if meta['currency'] != 'USD': raise PriceFailure(PriceIssue.CURRENCY_MISMATCH)
        if meta.get('regularMarketPrice') is None: return None
        value, stamp = meta['regularMarketPrice'], meta['regularMarketTime']
        if type(value) not in (int, Decimal) or not Decimal(value).is_finite() or value <= 0 or type(stamp) is not int:
            raise ValueError('positive exact price and epoch seconds required')
        value = Decimal(value)
        if max(len(value.as_tuple().digits), abs(value.adjusted())) > 1000: raise ValueError('unsupported magnitude')
        market_at = datetime.fromtimestamp(stamp, timezone.utc)
        if market_at > response.retrieved_at: raise PriceFailure(PriceIssue.FUTURE_OBSERVATION)
        if as_of - market_at > quote_max_age: raise PriceFailure(PriceIssue.STALE_QUOTE)
    except (KeyError, TypeError, ValueError, OverflowError, OSError, ArithmeticError):
        raise ProviderFailure(Status.INVALID_DATA) from None
    return MarketPrice(cik, symbol, value, 'USD', exchange, Source.YAHOO,
                       'chart.result[0].meta.regularMarketPrice',
                       'Yahoo latest regular-session market price; not adjusted close, NAV, market capitalization or a financial-statement value',
                       'currency_per_share', market_at, response.retrieved_at, response.retrieved_at,
                       response.url, response.sha256, identity.url, identity.sha256,
                       identity.retrieved_at, 'EQUITY')


def cached_response(archive, url, now, ttl):
    rows = [r for r in archive.observations() if r['url'] == url
            and timedelta(0) <= now - datetime.fromisoformat(r['retrieved_at']) <= ttl]
    if not rows: return None
    latest = max(rows, key=lambda r: datetime.fromisoformat(r['retrieved_at']))
    return archive.get(url, latest['sha256'], datetime.fromisoformat(latest['retrieved_at']))


class YahooMarketPrice:
    def __init__(self, transport, *, identity, archive, clock=None):
        self.transport, self.identity, self.archive = transport, identity, archive
        self.clock = clock or (lambda: datetime.now(timezone.utc))
        self.http_calls = 0
        self.last_response = None

    def fetch(self, cik, symbol, *, allow_network=True):
        self.last_response = None
        _identity(self.identity, cik, symbol, self.clock(), IDENTITY_TTL)
        url = price_url(symbol)
        response = cached_response(self.archive, url, self.clock(), PRICE_TTL)
        if response is not None and response.retrieved_at < self.identity.retrieved_at:
            response = None
        cached = response is not None
        if response is None:
            if not allow_network: raise PriceNotStarted()
            self.http_calls += 1
            response = self.transport.get(url)
            self.archive.record(response)
        self.last_response = response
        result = parse_price(response, self.identity, cik=cik, symbol=symbol, as_of=self.clock())
        return result, cached


def collect_prices(candidates, *, provider, max_new_prices=100, clock=None):
    from .mvp import validate_candidates
    rows = validate_candidates(candidates)
    for row in rows: price_url(row['symbol'])
    if type(max_new_prices) is not int or not 0 <= max_new_prices <= 100:
        raise ValueError('bounded 0..100 new price requests required')
    clock = clock or (lambda: datetime.now(timezone.utc))
    started = provider.http_calls
    companies = []
    for row in rows:
        result = dict(**row, state='pending_data', price=None, attempts=[], total_score=None, rank=None,
                      scope_approved=False, sector_model_supported=False, investment_approved=False)
        before = provider.http_calls
        stamp = clock()
        try:
            price, cached = provider.fetch(row['issuer_id'], row['symbol'], allow_network=provider.http_calls-started < max_new_prices)
            status = Status.VALID if price is not None else Status.MISSING
            result.update(state='collected' if price is not None else 'pending_data', price=asdict(price) if price else None, cached=cached)
            result['attempts'].append(dict(source='Yahoo', status=status.value, attempted_at=stamp.isoformat(),
                                           http_requested=provider.http_calls > before, cached=cached))
        except PriceNotStarted:
            result['state'] = 'not_started'; companies.append(result); continue
        except ProviderFailure as exc:
            result['attempts'].append(dict(source='Yahoo', status=exc.status.value, attempted_at=stamp.isoformat(),
                http_requested=provider.http_calls > before, issue=exc.issue.value if isinstance(exc,PriceFailure) else None,
                failure_reason=exc.reason.value if exc.reason else None, http_status=exc.http_status))
        response = provider.last_response
        result['source_evidence'] = (dict(url=response.url, sha256=response.sha256, retrieved_at=response.retrieved_at.isoformat())
                                     if response is not None else None)
        if result['price'] is None:
            result['attempts'].extend(dict(source=source, status=status, attempted_at=clock().isoformat(), http_requested=False)
                for source,status in [('SEC','unsupported_field'),('Nasdaq','not_configured'),('Finnhub','not_configured')])
        companies.append(result)
    references = []
    for row in companies:
        p = row['price']
        if p is None: continue
        for url, sha, observed in [(p['source_url'],p['raw_sha256'],p['retrieved_at']),
                                   (p['identity_evidence_url'],p['identity_evidence_sha256'],p['identity_observed_at'])]:
            references.append(provider.archive.get(url, sha, observed) is not None)
    return dict(schema_version=1, report_kind='market_price_inputs_scope_pending', generated_at=clock().isoformat(),
                companies=companies, ranking=[], mvp_accepted=False,
                summary=dict(candidates=len(companies), collected_prices=sum(c['price'] is not None for c in companies),
                    company_states=dict(Counter(c['state'] for c in companies)), scored_companies=0,
                    new_price_get_invocations=provider.http_calls-started),
                all_selected_price_references_archived=bool(references) and all(references),
                max_quote_age_seconds=int(QUOTE_MAX_AGE.total_seconds()),
                limitations=['EQUITY label and SEC directory do not prove active common shares',
                             'latest regular-session price may be delayed; not a synchronized consolidated or executable quote',
                             'no market capitalization or class/issuer share count derived',
                             'no historic-price or point-in-time backtest claim'])


def run_prices(candidates, *, state_dir, user_agent, max_new_prices=100):
    from .mvp import save_json, save_text, validate_candidates
    rows = validate_candidates(candidates)
    for row in rows: price_url(row['symbol'])
    if type(max_new_prices) is not int or not 0 <= max_new_prices <= 100:
        raise ValueError('bounded new-price request limit required')
    path = Path(state_dir); path.mkdir(parents=True, exist_ok=True)
    lock = BatchStore(path/'run-lock.sqlite'); archive = ResponseArchive(path/'sources.sqlite')
    now = lambda: datetime.now(timezone.utc)
    owner = None
    try:
        owner = lock.acquire(now(), timedelta(minutes=15))
        identity = cached_response(archive, DIRECTORY_URL, now(), IDENTITY_TTL)
        identity_gets = 0
        if identity is None:
            if max_new_prices == 0:
                raise PriceNotStarted('no cached identity; zero-work run cannot fetch it')
            identity = ArchivedTransport(archive=archive, user_agent=user_agent, allowed_hosts={'www.sec.gov'},
                timeout=10,budget=20,max_attempts=2,max_bytes=2000000).get(DIRECTORY_URL)
            identity_gets = 1
        parse_directory(identity)
        class PriceTransport(ArchivedTransport):
            def get(self, url):
                lock.renew(owner, now(), timedelta(minutes=15))
                return super().get(url)
        transport = PriceTransport(archive=archive,user_agent=user_agent,allowed_hosts={'query1.finance.yahoo.com'},
                    timeout=10,budget=20,max_attempts=2,max_bytes=1000000)
        provider = YahooMarketPrice(transport,identity=identity,archive=archive)
        report = collect_prices(dict(companies=rows),provider=provider,max_new_prices=max_new_prices)
        report['new_identity_get_invocations'] = identity_gets
        save_json(path/'report.json',report)
        save_text(path/'report.md',render_price_markdown(report))
        return report
    finally:
        if owner is not None: lock.release(owner)
        archive.close(); lock.close()


def render_price_markdown(report):
    import html
    def cell(value):
        return html.escape(str(value)).replace('|','&#124;').replace('\n',' ')
    lines=['# Market-price inputs', '', 'Active common-share/sector approval and investment scores remain pending. Prices may be delayed.', '',
           '| Symbol | CIK | Price / USD per share | Market time UTC | Source observation UTC | Status | Provider outcomes |',
           '| --- | --- | ---: | --- | --- | --- | --- |']
    for row in report['companies']:
        p=row['price']
        attempts='; '.join(a['source']+': '+a['status'] for a in row['attempts']) or 'not attempted'
        lines.append('| '+' | '.join(cell(v) for v in (row['symbol'],row['issuer_id'],p['value'] if p else 'unavailable',
            p['market_at'] if p else '',p['retrieved_at'] if p else '',row['state'],attempts))+' |')
    lines.extend(['', 'Full JSON retains exact price and identity URLs, raw SHA-256 values, original observation times, field definition, currency and provider outcomes. No market capitalization or share count is inferred.', ''])
    return '\n'.join(lines).rstrip()+'\n'
