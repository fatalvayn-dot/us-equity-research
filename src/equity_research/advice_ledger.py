"""Append-only advice ledger with later outcome checks and honest calibration.

A record is research evidence, never an order. 'AL' is refused unless
participation eligibility was independently verified. Outcomes are judged against
a benchmark, small samples never produce a success-rate claim, and records are
hash-chained so silent edits of past advice are detectable.
"""
import hashlib
import json
import math
from datetime import datetime, timedelta, timezone
from decimal import Decimal

VIEWS = ('AL', 'TUT', 'AZALT', 'SAT', 'BEKLE', 'ARASTIRMA_ADAYI')
UP, DOWN = frozenset({'AL', 'ARASTIRMA_ADAYI'}), frozenset({'AZALT', 'SAT'})
CONFIDENCE = ('dusuk', 'orta', 'yuksek')
ERROR_CLASSES = ('dogru', 'veri', 'model', 'haber_yorumu', 'sans_belirsizlik')
MIN_SAMPLE = 25
NEUTRAL_BAND_PCT = Decimal(1)
MAX_PRICE_AGE = timedelta(days=4)
OBSERVATION_GRACE = timedelta(days=7)
GENESIS = '0' * 64


def _when(value, label):
    d = value if isinstance(value, datetime) else datetime.fromisoformat(str(value))
    if d.tzinfo is None:
        raise ValueError(label + ' must be timezone-aware')
    return d.astimezone(timezone.utc)


def _price(value, label):
    d = Decimal(str(value))
    if not d.is_finite() or d <= 0:
        raise ValueError(label + ' must be a positive finite number')
    return d


def _text(value, label):
    if not isinstance(value, str) or not value.strip():
        raise ValueError(label + ' required')
    return value.strip()


def _canon(record):
    return json.dumps(record, sort_keys=True, separators=(',', ':'), ensure_ascii=False)


def _seal(record, prev):
    body = dict(record, prev=prev)
    return dict(body, hash=hashlib.sha256(_canon(body).encode()).hexdigest())


def read(path):
    try:
        with open(path, encoding='utf-8') as handle:
            return [json.loads(line) for line in handle if line.strip()]
    except FileNotFoundError:
        return []


def verify_chain(rows):
    prev = GENESIS
    for row in rows:
        body = {k: v for k, v in row.items() if k != 'hash'}
        if row.get('prev') != prev or hashlib.sha256(_canon(body).encode()).hexdigest() != row.get('hash'):
            raise ValueError('ledger chain broken at ' + str(row.get('id')))
        prev = row['hash']
    return prev


def _append(path, record):
    rows = read(path)
    sealed = _seal(record, verify_chain(rows))
    with open(path, 'a', encoding='utf-8') as handle:
        handle.write(_canon(sealed) + '\n')
    return sealed


def record_advice(path, *, created_at, symbol, view, price, price_at, price_source, benchmark,
                  benchmark_price, benchmark_at, horizon_days, rationale, evidence, model_version,
                  confidence, invalidation, target_price=None, participation_verified=False):
    now = _when(created_at, 'created_at')
    if view not in VIEWS:
        raise ValueError('unknown view')
    if view == 'AL' and participation_verified is not True:
        raise ValueError('AL requires verified participation eligibility')
    if confidence not in CONFIDENCE or not isinstance(horizon_days, int) or not 5 <= horizon_days <= 365:
        raise ValueError('confidence or horizon invalid')
    if (not isinstance(rationale, list) or not rationale or any(not isinstance(x, str) or not x.strip() for x in rationale)
            or not isinstance(evidence, list) or not evidence):
        raise ValueError('rationale and evidence references required')
    for label, stamp in (('price_at', price_at), ('benchmark_at', benchmark_at)):
        at = _when(stamp, label)
        if at > now or now - at > MAX_PRICE_AGE:
            raise ValueError(label + ' must be recent and not in the future')
    rows = [r for r in read(path) if r['kind'] == 'advice']
    record = dict(kind='advice', id='A%04d' % (len(rows) + 1), created_at=now.isoformat(), symbol=_text(symbol, 'symbol'), view=view,
        price=str(_price(price, 'price')), price_at=_when(price_at, 'price_at').isoformat(), price_source=_text(price_source, 'price_source'),
        benchmark=_text(benchmark, 'benchmark'), benchmark_price=str(_price(benchmark_price, 'benchmark_price')),
        benchmark_at=_when(benchmark_at, 'benchmark_at').isoformat(), horizon_days=horizon_days,
        due_at=(now + timedelta(days=horizon_days)).isoformat(), rationale=[x.strip() for x in rationale],
        evidence=[_text(x, 'evidence') for x in evidence], model_version=_text(model_version, 'model_version'),
        confidence=confidence, invalidation=_text(invalidation, 'invalidation'),
        target_price=None if target_price is None else str(_price(target_price, 'target_price')),
        participation_verified=bool(participation_verified), investment_order=False)
    return _append(path, record)


def evaluate(path, advice_id, *, observed_at, price, benchmark_price, price_at, benchmark_at):
    rows = read(path);verify_chain(rows)
    advice = next((r for r in rows if r['kind'] == 'advice' and r['id'] == advice_id), None)
    if advice is None:
        raise ValueError('unknown advice')
    if any(r['kind'] == 'outcome' and r['advice_id'] == advice_id for r in rows):
        raise ValueError('outcome already recorded')
    due, seen = _when(advice['due_at'], 'due_at'), _when(observed_at, 'observed_at')
    if seen < due:
        raise ValueError('horizon not reached')
    base = dict(kind='outcome', id='O' + advice_id[1:], advice_id=advice_id, observed_at=seen.isoformat())
    stamps = [_when(price_at, 'price_at'), _when(benchmark_at, 'benchmark_at')]
    if any(s < due or s > due + OBSERVATION_GRACE or s > seen for s in stamps):
        return _append(path, dict(base, label='gozlem_yok', reason='observation_outside_due_window'))
    ret = (_price(price, 'price') / Decimal(advice['price']) - 1) * 100
    bench = (_price(benchmark_price, 'benchmark_price') / Decimal(advice['benchmark_price']) - 1) * 100
    excess = ret - bench
    view = advice['view']
    if view in UP:
        label = 'dogru' if excess > NEUTRAL_BAND_PCT else 'yanlis' if excess < -NEUTRAL_BAND_PCT else 'belirsiz'
    elif view in DOWN:
        label = 'dogru' if excess < -NEUTRAL_BAND_PCT else 'yanlis' if excess > NEUTRAL_BAND_PCT else 'belirsiz'
    else:
        label = 'olculmedi'
    target = advice['target_price']
    reached = None if target is None else (Decimal(str(price)) >= Decimal(target) if view in UP else Decimal(str(price)) <= Decimal(target))
    return _append(path, dict(base, label=label, return_pct=str(ret.quantize(Decimal('0.001'))),
        benchmark_return_pct=str(bench.quantize(Decimal('0.001'))), excess_pct=str(excess.quantize(Decimal('0.001'))),
        target_reached_at_observation=reached, price=str(price), benchmark_price=str(benchmark_price)))


def review(path, advice_id, *, error_class, note):
    rows = read(path);verify_chain(rows)
    outcome = next((r for r in rows if r['kind'] == 'outcome' and r['advice_id'] == advice_id), None)
    if outcome is None or error_class not in ERROR_CLASSES:
        raise ValueError('outcome and valid error class required')
    if any(r['kind'] == 'review' and r['advice_id'] == advice_id for r in rows):
        raise ValueError('review already recorded')
    if (error_class == 'dogru') != (outcome['label'] == 'dogru'):
        raise ValueError("error class 'dogru' only for correct outcomes")
    return _append(path, dict(kind='review', id='R' + advice_id[1:], advice_id=advice_id, error_class=error_class, note=_text(note, 'note')))


def _wilson(k, n):
    z = 1.96;p = k / n;d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d;h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return round(max(0.0, c - h), 3), round(min(1.0, c + h), 3)


def calibration(path):
    rows = read(path);verify_chain(rows)
    advice = {r['id']: r for r in rows if r['kind'] == 'advice'}
    outcomes = [r for r in rows if r['kind'] == 'outcome']
    reviews = {r['advice_id']: r for r in rows if r['kind'] == 'review'}
    scored = [o for o in outcomes if o['label'] in ('dogru', 'yanlis', 'belirsiz')]
    decided = [o for o in scored if o['label'] != 'belirsiz']
    right = sum(o['label'] == 'dogru' for o in decided)
    report = dict(advice=len(advice), outcomes=len(outcomes), pending=len(advice) - len(outcomes),
        no_observation=sum(o['label'] == 'gozlem_yok' for o in outcomes), not_measured=sum(o['label'] == 'olculmedi' for o in outcomes),
        uncertain=sum(o['label'] == 'belirsiz' for o in scored), decided=len(decided),
        errors_by_class={c: sum(1 for r in reviews.values() if r['error_class'] == c) for c in ERROR_CLASSES},
        unreviewed_wrong=sum(1 for o in scored if o['label'] == 'yanlis' and o['advice_id'] not in reviews),
        minimum_sample=MIN_SAMPLE, investment_edge_claim=False)
    if len(decided) < MIN_SAMPLE:
        report.update(status='yetersiz_ornek', hit_rate=None, hit_rate_95ci=None, mean_excess_pct=None)
    else:
        sign = lambda o: Decimal(-1) if advice[o['advice_id']]['view'] in DOWN else Decimal(1)
        mean = sum(sign(o) * Decimal(o['excess_pct']) for o in scored) / len(scored)  # view-adjusted: positive = advice direction paid
        report.update(status='olculdu_avantaj_kaniti_degil', hit_rate=round(right / len(decided), 3),
            hit_rate_95ci=_wilson(right, len(decided)), mean_excess_pct=str(mean.quantize(Decimal('0.001'))))
    return report
