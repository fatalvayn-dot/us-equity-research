"""Exact audited valuation priority lineage; fixture-only security tests."""
import json
import tempfile
import unittest
from pathlib import Path

from scripts.select_reviewed_valuation_priority import select, record_next


class PriorityLineageTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.root=Path(self.tmp.name)
        self.plan=self.root/'plan.json'
        self.report=self.root/'report.json'
        self.lineage=self.root/'priority-lineage.json'
        self.report.write_text('{"original":"audited"}')
        import hashlib
        checksum=hashlib.sha256(self.report.read_bytes()).hexdigest()
        self.original_checksum=checksum
        self.reviewed=dict(financial_run_id=11,valuation_run_id=22,
            valuation_report_sha256=checksum,
            companies=[dict(symbol='NOW',issuer_id='0001373715'),
                       dict(symbol='INTU',issuer_id='0000896878')])
        self.plan.write_text(json.dumps(self.reviewed))
    def tearDown(self):
        self.tmp.cleanup()
    def produce(self, *, names=('NOW',), candidate=('NOW','0001373715')):
        self.report.write_text(json.dumps(dict(
            schema_version=1,
            report_kind='valuation_source_collection_scope_pending',
            priority_symbols=list(names),
            companies=[dict(symbol=s,issuer_id=c) for s,c in
                [candidate,('INTU','0000896878')]])))
        return record_next(self.plan,11,33,self.report,self.lineage)

    def test_original_checkpoint_requires_exact_digest(self):
        self.assertEqual(select(self.plan,11,22,self.report,self.lineage),self.plan)
        self.assertIsNone(select(self.plan,12,22,self.report,self.lineage))
        self.report.write_text('different')
        with self.assertRaisesRegex(ValueError,'digest mismatch'):
            select(self.plan,11,22,self.report,self.lineage)

    def test_verified_successor_requires_exact_run_and_report(self):
        self.produce()
        self.assertEqual(select(self.plan,11,33,self.report,self.lineage),self.plan)
        self.assertIsNone(select(self.plan,11,34,self.report,self.lineage))
        self.assertIsNone(select(self.plan,12,33,self.report,self.lineage))
        self.assertIsNone(select(self.plan,11,None,self.report,self.lineage))
        self.assertIsNone(select(self.plan,11,33,self.report),None)
        self.report.write_text('changed')
        with self.assertRaisesRegex(ValueError,'digest mismatch'):
            select(self.plan,11,33,self.report,self.lineage)

    def test_plan_changes_and_lineage_tampering_fails_closed(self):
        self.produce()
        self.reviewed['companies'].append(dict(symbol='PLTR',issuer_id='0001321655'))
        self.plan.write_text(json.dumps(self.reviewed))
        self.assertIsNone(select(self.plan,11,33,self.report,self.lineage))
        self.reviewed['companies'].pop()
        self.plan.write_text(json.dumps(self.reviewed))
        raw=json.loads(self.lineage.read_text())
        raw['root_run_id']=999
        self.lineage.write_text(json.dumps(raw))
        self.assertIsNone(select(self.plan,11,33,self.report,self.lineage))

    def test_only_proven_priority_collection_can_record(self):
        with self.assertRaisesRegex(ValueError,'exact-candidate report'):
            self.produce(names=())
        with self.assertRaisesRegex(ValueError,'exact-candidate report'):
            self.produce(names=('NOTLISTED',))
        with self.assertRaisesRegex(ValueError,'exact-candidate report'):
            self.produce(candidate=('NOW','0000000001'))
        with self.assertRaisesRegex(ValueError,'exact financial run'):
            record_next(self.plan,12,33,self.report,self.lineage)
        with self.assertRaisesRegex(ValueError,'exact financial run'):
            record_next(self.plan,11,0,self.report,self.lineage)

    def test_no_side_effect_when_lineage_unavailable(self):
        self.assertIsNone(select(self.plan,11,33,self.report,self.lineage))
        self.assertFalse(self.lineage.exists())


if __name__=='__main__':
    unittest.main()
