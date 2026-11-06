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
