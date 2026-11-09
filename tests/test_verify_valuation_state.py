import json
import sqlite3
import tempfile
import unittest
from contextlib import closing
from datetime import datetime, timedelta, timezone
from pathlib import Path

from equity_research.batch import BatchStore
from equity_research.evidence_bundle import write_bundle
from equity_research.response_archive import ResponseArchive
from equity_research.transport import Response
from scripts.verify_valuation_state import verify


class VerifyValuationStateTests(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.root = Path(folder.name)
        self.source = self.root / "sources.sqlite"
        self.lock = self.root / "run-lock.sqlite"
        self.bundle = self.root / "source-bundle"
        self.report = self.root / "report.json"
        self.now = datetime.now(timezone.utc)
        BatchStore(self.lock).close()
        with closing(ResponseArchive(self.source)) as archive:
            archive.record(Response("https://www.sec.gov/example", b"original", self.now))
            manifest = write_bundle(archive, self.bundle)
        self.report.write_text(json.dumps({"source_bundle": manifest}))

    def test_accepts_intact_state_without_rewriting_files(self):
        before = {p: p.read_bytes() for p in self.root.rglob("*") if p.is_file()}
        self.assertEqual(verify(self.root), 1)
        self.assertEqual(
            {p: p.read_bytes() for p in self.root.rglob("*") if p.is_file()},
            before,
        )

    def test_rejects_missing_state_without_creating_empty_database(self):
        self.lock.unlink()
        with self.assertRaisesRegex(ValueError, "run-lock.sqlite"):
            verify(self.root)
        self.assertFalse(self.lock.exists())

    def test_rejects_active_lease_without_modifying_it(self):
        with closing(BatchStore(self.lock)) as lock:
            lock.acquire(self.now, timedelta(minutes=5))
        original = self.lock.read_bytes()
        with self.assertRaisesRegex(ValueError, "Etkin kira"):
            verify(self.root)
        self.assertEqual(self.lock.read_bytes(), original)

    def test_rejects_changed_raw_body(self):
        with closing(sqlite3.connect(self.source)) as db, db:
            db.execute("UPDATE response_bodies_v1 SET body = ?", (b"altered",))
        with self.assertRaisesRegex(ValueError, "Ham kaynak özeti"):
            verify(self.root)

    def test_rejects_same_count_with_different_sqlite_observation(self):
        with closing(sqlite3.connect(self.source)) as db, db:
            db.execute(
                "UPDATE response_observations_v1 SET url = ?",
                ("https://www.sec.gov/other",),
            )
        with self.assertRaisesRegex(ValueError, "SQLite kaydıyla uyuşmuyor"):
            verify(self.root)

    def test_rejects_report_manifest_mismatch(self):
        self.report.write_text(json.dumps({"source_bundle": {}}))
        with self.assertRaisesRegex(ValueError, "kaynak manifesti uyuşmuyor"):
            verify(self.root)

    def test_rejects_corrupted_bundle_part(self):
        next(self.bundle.glob("*.part*")).write_bytes(b"altered")
        with self.assertRaisesRegex(ValueError, "bundle part integrity"):
            verify(self.root)
