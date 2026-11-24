import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from equity_research import advice_ledger as L

T0 = datetime(2026, 11, 24, 12, tzinfo=timezone.utc)


def advice(path, **kw):
    base = dict(created_at=T0, symbol='MSFT', view='ARASTIRMA_ADAYI', price='100', price_at=T0 - timedelta(hours=2),
        price_source='Yahoo Finance chart', benchmark='SPY', benchmark_price='500', benchmark_at=T0 - timedelta(hours=2),
        horizon_days=30, rationale=['skor 66.5, kanıtlı'], evidence=['run:45338840972'], model_version='v3',
        confidence='orta', invalidation='net kâr zararı')
    base.update(kw);return L.record_advice(path, **base)


def outcome(path, i='A0001', price='110', bench='505', **kw):
    due = T0 + timedelta(days=30)
    base = dict(observed_at=due + timedelta(days=1), price=price, benchmark_price=bench, price_at=due, benchmark_at=due)
    base.update(kw);return L.evaluate(path, i, **base)


class LedgerTests(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.TemporaryDirectory();self.p = Path(self.d.name) / 'l.jsonl'
    def tearDown(self):self.d.cleanup()

    def test_al_refused_without_verified_participation(self):
        with self.assertRaises(ValueError):advice(self.p, view='AL')
        self.assertEqual(advice(self.p, view='AL', participation_verified=True)['view'], 'AL')

    def test_records_are_hash_chained_and_tampering_is_detected(self):
        advice(self.p);advice(self.p, symbol='NVDA');L.verify_chain(L.read(self.p))
        rows = self.p.read_text().splitlines();first = json.loads(rows[0]);first['price'] = '1'
        rows[0] = json.dumps(first, sort_keys=True, separators=(',', ':'));self.p.write_text('\n'.join(rows) + '\n')
        with self.assertRaises(ValueError):L.verify_chain(L.read(self.p))
        with self.assertRaises(ValueError):advice(self.p)

    def test_stale_future_or_naive_inputs_rejected(self):
        for kw in (dict(price_at=T0 - timedelta(days=5)), dict(price_at=T0 + timedelta(hours=1)),
                   dict(created_at=datetime(2026, 11, 24, 12)), dict(price='0'), dict(horizon_days=1),
                   dict(rationale=[]), dict(evidence=[]), dict(invalidation=' '), dict(view='X')):
            with self.assertRaises(ValueError, msg=str(kw)):advice(self.p, **kw)

    def test_outcome_is_benchmark_relative_and_one_shot(self):
        advice(self.p);o = outcome(self.p)  # +10% vs +1%
        self.assertEqual(o['label'], 'dogru');self.assertEqual(o['excess_pct'], '9.000')
        with self.assertRaises(ValueError):outcome(self.p)

    def test_market_up_but_lagging_benchmark_is_wrong_not_right(self):
        advice(self.p);self.assertEqual(outcome(self.p, price='103', bench='550')['label'], 'yanlis')

    def test_inside_neutral_band_is_uncertain_and_sell_view_inverts(self):
        advice(self.p);self.assertEqual(outcome(self.p, price='101', bench='505')['label'], 'belirsiz')
        advice(self.p, view='SAT');self.assertEqual(outcome(self.p, 'A0002', price='90', bench='500')['label'], 'dogru')

    def test_early_or_off_window_observation_never_scored(self):
        advice(self.p)
        with self.assertRaises(ValueError):outcome(self.p, observed_at=T0 + timedelta(days=10))
        due = T0 + timedelta(days=30)
        o = outcome(self.p, observed_at=due + timedelta(days=20), price_at=due + timedelta(days=20), benchmark_at=due + timedelta(days=20))
        self.assertEqual(o['label'], 'gozlem_yok')

    def test_hold_is_not_measured(self):
        advice(self.p, view='TUT');self.assertEqual(outcome(self.p)['label'], 'olculmedi')

    def test_review_class_must_match_outcome(self):
        advice(self.p);outcome(self.p, price='95', bench='505')
        with self.assertRaises(ValueError):L.review(self.p, 'A0001', error_class='dogru', note='x')
        self.assertEqual(L.review(self.p, 'A0001', error_class='model', note='eşik fazla iyimser')['error_class'], 'model')
        with self.assertRaises(ValueError):L.review(self.p, 'A0001', error_class='veri', note='x')

    def test_small_sample_makes_no_rate_claim(self):
        for _ in range(3):advice(self.p)
        for i in (1, 2, 3):outcome(self.p, 'A000%d' % i)
        r = L.calibration(self.p)
        self.assertEqual(r['status'], 'yetersiz_ornek');self.assertIsNone(r['hit_rate']);self.assertFalse(r['investment_edge_claim'])

    def test_calibration_with_enough_samples_reports_interval_not_edge(self):
        for i in range(1, 27):
            advice(self.p);outcome(self.p, 'A%04d' % i, price='110' if i <= 15 else '90', bench='500')
        r = L.calibration(self.p)
        self.assertEqual(r['decided'], 26);self.assertEqual(r['hit_rate'], round(15 / 26, 3))
        self.assertEqual(r['status'], 'olculdu_avantaj_kaniti_degil');self.assertFalse(r['investment_edge_claim'])
        self.assertEqual(r['unreviewed_wrong'], 11);self.assertLess(r['hit_rate_95ci'][0], r['hit_rate'])


if __name__ == '__main__':unittest.main()
