import unittest

from scripts.live_checkpoint import ROOT_RUN
from scripts.select_valuation_financial_source import select_source


def run(offset, **changes):
    return dict(id=ROOT_RUN + offset, head_branch='main', event='schedule',
                status='completed', conclusion='success') | changes


def artifact(suffix, *, expired=False):
    return dict(name='live-acceptance-' + suffix, expired=expired)


class ValuationFinancialSourceTests(unittest.TestCase):
    def setUp(self):
        self.responses = {
            'actions/workflows/live-acceptance.yml/runs?branch=main&per_page=100&page=1':
                {'workflow_runs': [run(3), run(2), run(1)]},
            f'actions/runs/{ROOT_RUN + 3}/artifacts?per_page=100':
                dict(total_count=0, artifacts=[]),
            f'actions/runs/{ROOT_RUN + 3}/jobs?filter=all&per_page=100':
                dict(total_count=1, jobs=[dict(steps=[{
                    'name': 'Devam ettirilebilir finansal veri toplamasını çalıştır',
                    'conclusion': 'skipped',
                }])]),
        }
        self.latest = f'actions/runs/{ROOT_RUN + 2}/artifacts?per_page=100'
        self.responses[self.latest] = dict(total_count=2, artifacts=[
            artifact('state'), artifact('evidence'),
        ])

    def test_proven_idle_run_uses_latest_paired_evidence(self):
        self.assertEqual(select_source(fetch=self.responses.__getitem__), ROOT_RUN + 2)
        self.assertEqual(select_source(str(ROOT_RUN + 2), fetch=self.responses.__getitem__),
                         ROOT_RUN + 2)

    def test_explicit_older_source_is_rejected(self):
        with self.assertRaisesRegex(ValueError, 'Eski çalışma seçimi'):
            select_source(str(ROOT_RUN + 1), fetch=self.responses.__getitem__)

    def test_missing_expired_or_duplicate_evidence_blocks_rollback(self):
        for items in ([], [artifact('evidence', expired=True)],
                      [artifact('evidence'), artifact('evidence')]):
            with self.subTest(items=items):
                self.responses[self.latest] = dict(total_count=1 + len(items),
                                                   artifacts=[artifact('state'), *items])
                with self.assertRaisesRegex(ValueError, 'kanıt paketi'):
                    select_source(fetch=self.responses.__getitem__)

    def test_recovery_and_truncated_artifacts_block_rollback(self):
        for total, items in ((1, [artifact('recovery')]), (2, [artifact('state')])):
            with self.subTest(total=total):
                self.responses[self.latest] = dict(total_count=total, artifacts=items)
                with self.assertRaisesRegex(ValueError, 'kurtarma paketi|listesi eksik'):
                    select_source(fetch=self.responses.__getitem__)

    def test_failed_run_with_artifacts_is_not_valuation_input(self):
        endpoint = 'actions/workflows/live-acceptance.yml/runs?branch=main&per_page=100&page=1'
        self.responses[endpoint] = {'workflow_runs': [run(2, conclusion='failure'), run(1)]}
        with self.assertRaisesRegex(ValueError, 'üretim koşusu başarılı değil'):
            select_source(fetch=self.responses.__getitem__)

    def test_active_collector_blocks_valuation(self):
        with self.assertRaisesRegex(ValueError, 'toplayıcı bekliyor veya çalışıyor'):
            select_source(fetch=lambda _: {'workflow_runs': [run(3, status='in_progress')]})
