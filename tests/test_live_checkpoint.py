"""Real corruption, active lease and stale-run regression tests."""
import importlib.util
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from datetime import datetime, timedelta, timezone

spec = importlib.util.spec_from_file_location('live_checkpoint', Path(__file__).resolve().parents[1] / 'scripts/live_checkpoint.py')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


class CheckpointTests(unittest.TestCase):
    def test_rerun_is_rejected_before_api_or_state_changes(self):
        from unittest.mock import patch
        for attempt in ('2', '3', '0', '-1', 'invalid'):
            with self.subTest(attempt=attempt), patch.dict(
                    'os.environ', {'GITHUB_RUN_ATTEMPT': attempt}), patch.object(
                    m, 'api') as api, patch('sys.argv', ['live_checkpoint.py', 'select']):
                before = m.inventory(self.root)
                with self.assertRaises(ValueError):
                    m.main()
                api.assert_not_called()
                self.assertEqual(m.inventory(self.root), before)

    def test_first_attempt_and_local_use_are_allowed(self):
        from unittest.mock import patch
        with patch.dict('os.environ', {}, clear=True):
            m.require_first_attempt()
        with patch.dict('os.environ', {'GITHUB_RUN_ATTEMPT': '1'}):
            m.require_first_attempt()

    def test_new_run_resumes_preceding_run_not_its_parent(self):
        previous = m.ROOT_RUN + 1
        runs = [self.run_row(m.ROOT_RUN), self.run_row(previous),
                self.run_row(previous + 1)]
        artifacts = lambda _: [dict(name='live-acceptance-state', expired=False)]
        self.assertEqual(m.select(runs, artifacts, previous + 1), previous)

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        for name in m.REQUIRED:
            with sqlite3.connect(self.root / name) as db:
                db.execute('CREATE TABLE batch_lease_v1(expires TEXT)')
        self.baseline = dict(root_run_id=m.ROOT_RUN, run_id=m.ROOT_RUN,
                             sequence=0, files=m.inventory(self.root))

    def test_exact_root_and_databases_pass(self):
        saved, counts = m.verify(self.root, m.ROOT_RUN, self.baseline)
        self.assertEqual(len(counts), 5)
        self.assertEqual(saved['sequence'], 0)

    def test_corrupt_file_and_missing_file_rejected(self):
        (self.root / 'financial.sqlite').write_bytes(b'corrupt')
        with self.assertRaises(ValueError):m.verify(self.root, m.ROOT_RUN, self.baseline)
        (self.root / 'financial.sqlite').unlink()
        with self.assertRaises(ValueError):m.verify(self.root, m.ROOT_RUN, self.baseline)

    def test_wrong_run_and_wrong_root_rejected(self):
        with self.assertRaises(ValueError):m.verify(self.root, m.ROOT_RUN + 1, self.baseline)
        self.baseline['root_run_id'] = 1
        with self.assertRaises(ValueError):m.verify(self.root, m.ROOT_RUN, self.baseline)

    def test_lease_blocks_restore_but_expired_lease_is_preserved(self):
        now = datetime.now(timezone.utc)
        with sqlite3.connect(self.root / 'run-lock.sqlite') as db:
            db.execute('INSERT INTO batch_lease_v1 VALUES (?)', ((now + timedelta(minutes=15)).isoformat(),))
        with self.assertRaises(ValueError):m.inspect_databases(self.root, now)
        counts = m.inspect_databases(self.root, now + timedelta(hours=1))
        self.assertEqual(counts['run-lock.sqlite']['batch_lease_v1'], 1)

    def test_body_corruption_rejected_even_if_database_is_valid(self):
        with sqlite3.connect(self.root / 'responses.sqlite') as db:
            db.execute('CREATE TABLE response_bodies_v1(sha256 TEXT,body BLOB)')
            db.execute('INSERT INTO response_bodies_v1 VALUES (?,?)', ('wrong', b'bytes'))
        with self.assertRaises(ValueError):m.inspect_databases(self.root)

    def test_manifest_is_bound_to_parent_run(self):
        saved = dict(self.baseline, run_id=m.ROOT_RUN + 2, parent_run_id=m.ROOT_RUN, sequence=1)
        (self.root / m.MANIFEST).write_text(json.dumps(saved))
        self.assertEqual(m.verify(self.root, m.ROOT_RUN + 2, self.baseline)[0]['sequence'], 1)
        with self.assertRaises(ValueError):m.verify(self.root, m.ROOT_RUN, self.baseline)

    def test_symlink_rejected(self):
        (self.root / 'link').symlink_to(self.root / 'financial.sqlite')
        with self.assertRaises(ValueError):m.inventory(self.root)

    def run_row(self, number, **kwargs):
        return dict(id=number, head_branch='main', event='workflow_dispatch', status='completed', **kwargs)

    def test_latest_failed_run_with_state_is_recovered(self):
        runs = [self.run_row(m.ROOT_RUN), self.run_row(m.ROOT_RUN + 1, conclusion='failure')]
        artifacts = lambda _: [dict(name='live-acceptance-state', expired=False)]
        self.assertEqual(m.select(runs, artifacts, 99999999999), m.ROOT_RUN + 1)
        with self.assertRaises(ValueError):m.select(runs, artifacts, 99999999999, str(m.ROOT_RUN))

    def test_expired_latest_does_not_fall_back(self):
        with self.assertRaises(ValueError):
            m.select([self.run_row(m.ROOT_RUN)], lambda _: [dict(name='live-acceptance-state', expired=True)], 99999999999)

    def test_pr_state_is_never_selected(self):
        run = self.run_row(m.ROOT_RUN + 1);run['event'] = 'pull_request'
        with self.assertRaises(ValueError):m.select([run], lambda _: [], 99999999999)

    def test_other_active_run_blocks(self):
        run = self.run_row(m.ROOT_RUN + 1);run['status'] = 'in_progress'
        with self.assertRaises(ValueError):m.select([run], lambda _: [], 99999999999)

    def test_no_state_never_creates_empty_run(self):
        with self.assertRaises(ValueError):m.select([self.run_row(m.ROOT_RUN)], lambda _: [], 99999999999)

    def test_unsealed_recovery_blocks_older_state(self):
        with self.assertRaises(ValueError):
            m.select([self.run_row(m.ROOT_RUN + 1), self.run_row(m.ROOT_RUN)],
                     lambda _: [dict(name='live-acceptance-recovery', expired=False)], 99999999999)

    def test_interrupted_lease_can_be_archived_without_clearing_it(self):
        with sqlite3.connect(self.root / 'run-lock.sqlite') as db:
            db.execute('INSERT INTO batch_lease_v1 VALUES (?)', ((datetime.now(timezone.utc) + timedelta(hours=1)).isoformat(),))
        self.assertEqual(m.inspect_databases(self.root, allow_active=True)['run-lock.sqlite']['batch_lease_v1'], 1)
        with self.assertRaises(ValueError):m.inspect_databases(self.root)

    def test_seal_and_restore_roundtrip_with_interrupted_state(self):
        import subprocess, sys
        (self.root.parent / 'resume-receipt.json').write_text(json.dumps(dict(parent_run_id=m.ROOT_RUN, root_run_id=m.ROOT_RUN, sequence=0)))
        self.addCleanup(lambda: (self.root.parent / 'resume-receipt.json').unlink(missing_ok=True))
        proc = subprocess.run([sys.executable, str(Path(m.__file__)), 'seal', '--state-dir', str(self.root), '--run-id', str(m.ROOT_RUN+1)], capture_output=True, text=True)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        saved, counts = m.verify(self.root, m.ROOT_RUN+1, self.baseline)
        self.assertEqual(saved['parent_run_id'], m.ROOT_RUN)
        self.assertEqual(saved['sequence'], 1)
        self.assertEqual(len(counts), 5)

    def test_lost_upload_does_not_silently_resume_older_state(self):
        runs = [self.run_row(m.ROOT_RUN + 1), self.run_row(m.ROOT_RUN)]
        artifacts = lambda rid: [] if rid > m.ROOT_RUN else [dict(name='live-acceptance-state', expired=False)]
        with self.assertRaises(ValueError):m.select(runs, artifacts, 99999999999)
        with self.assertRaises(ValueError):m.select(runs, artifacts, 99999999999, safe_to_skip=lambda _: False)
        self.assertEqual(m.select(runs, artifacts, 99999999999, safe_to_skip=lambda _: True), m.ROOT_RUN)

    def test_preflight_failure_can_skip_only_proven_unstarted_collection(self):
        name = 'Devam ettirilebilir finansal veri toplamasını çalıştır'
        self.assertTrue(m.collection_never_started([dict(steps=[dict(name=name, conclusion='skipped')])]))
        self.assertFalse(m.collection_never_started([]))
        self.assertFalse(m.collection_never_started([dict(steps=[dict(name=name, conclusion='success')])]))
        self.assertFalse(m.collection_never_started([dict(steps=[dict(name=name, conclusion='skipped'), dict(name=name, conclusion='failure')])]))

    def test_incomplete_attempt_history_is_not_safe_to_skip(self):
        from unittest.mock import patch
        job = dict(steps=[dict(name='Devam ettirilebilir finansal veri toplamasını çalıştır', conclusion='skipped')])
        with patch.object(m, 'api', return_value=dict(total_count=2, jobs=[job])):
            self.assertFalse(m.safe_run_skip(m.ROOT_RUN+1))
        with patch.object(m, 'api', return_value=dict(total_count=1, jobs=[job])):
            self.assertTrue(m.safe_run_skip(m.ROOT_RUN+1))

    def test_cancelled_queue_without_any_job_can_be_skipped(self):
        from unittest.mock import patch
        with patch.object(m, 'api', return_value=dict(total_count=0, jobs=[])):
            self.assertTrue(m.safe_run_skip(m.ROOT_RUN+1))
