"""Synthetic archive tests; never represent these fixtures as real stocks."""
import gzip
import hashlib
import json
import tempfile
import unittest
import zipfile
from pathlib import Path

from scripts.audit_dated_score_coverage import SnapshotError, read_snapshot, compare


def archive(path, when, scores, *, tamper=None, mvp=False):
    companies=[]
    for idx,(symbol,score) in enumerate(scores.items(),1):
        companies.append(dict(issuer_id=f'{int(hashlib.sha256(symbol.encode()).hexdigest()[:12],16)%10**10:010d}',symbol=symbol,
            rank=idx,total_score=str(score),status='scored_research_hypothesis',
            evidence=dict(financial_confirmations=[{} for _ in range(9)])))
    ranking=[dict(issuer_id=row['issuer_id'],symbol=row['symbol'],
                  rank=row['rank'],score=row['total_score']) for row in companies]
    report=dict(as_of=when,model_version='model-v1',companies=companies,
                ranking=ranking,mvp_accepted=mvp,
                summary=dict(candidates=len(companies),scored_companies=len(ranking)))
    blobs=dict(report_json=gzip.compress(json.dumps(report).encode(),mtime=0),
               report_md=b'report',report_html=b'html')
    paths={'report.json.gz':blobs['report_json'],'report.md':blobs['report_md'],
           'report.html':blobs['report_html']}
    manifest=dict(as_of=when,summary=report['summary'],mvp_accepted=mvp,
        mode='current_market_sources_with_recorded_financial_inputs',
        files={name:hashlib.sha256(body).hexdigest() for name,body in paths.items()})
    if tamper=='manifest':
        manifest['files']['report.md']='0'*64
    if tamper=='summary':
        manifest['summary']['scored_companies']+=1
    if tamper=='ranking':
        report['ranking'][0]['score']='999'
        paths['report.json.gz']=gzip.compress(json.dumps(report).encode(),mtime=0)
        manifest['files']['report.json.gz']=hashlib.sha256(paths['report.json.gz']).hexdigest()
    with zipfile.ZipFile(path,'w') as dest:
        dest.writestr('output/manifest.json',json.dumps(manifest))
        for name,body in paths.items():
            dest.writestr('output/'+name,body)


class DatedCoverageAuditTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.root=Path(self.tmp.name)
    def tearDown(self):
        self.tmp.cleanup()
    def snapshots(self, a, b):
        old=self.root/'old.zip'; new=self.root/'new.zip'
        archive(old,'2026-11-08T08:00:00+00:00',a)
        archive(new,'2026-11-09T08:00:00+00:00',b)
        return read_snapshot(old),read_snapshot(new)

    def test_distinct_research_coverage_never_looks_like_combined_live_ranking(self):
        old,new=self.snapshots(dict(AAPL=67,MU=92),dict(NOW=62,INTU=78))
        result=compare(old,new)
        self.assertEqual(result['distinct_historically_scored'],4)
        self.assertEqual(result['previous_only'],2)
        self.assertEqual(result['current_only'],2)
        self.assertEqual(result['both'],0)
        self.assertEqual(result['current']['scored'],2)
        self.assertFalse(result['mvp_accepted'])
        self.assertIn('not_a_combined_current_ranking',result['limitations'])
        self.assertEqual({r['symbol'] for r in result['companies'] if
            r['availability']=='previous_only'}, {'AAPL','MU'})
        self.assertTrue(all(r['current_score'] is None for r in result['companies']
                            if r['availability']=='previous_only'))

    def test_overlap_preserves_both_cutoffs_without_claiming_return(self):
        old,new=self.snapshots(dict(MU=92,AAPL=67),dict(MU=80,NOW=62))
        result=compare(old,new)
        self.assertEqual((result['both'],result['previous_only'],result['current_only']),(1,1,1))
        mu=next(x for x in result['companies'] if x['symbol']=='MU')
        self.assertEqual((mu['previous_score'],mu['current_score']),('92','80'))
        self.assertIn('no_cross_date_score_improvement_claim',result['limitations'])

    def test_tampered_manifest_or_summary_or_ranking_is_rejected(self):
        for error in ('manifest','summary','ranking'):
            with self.subTest(error=error):
                path=self.root/(error+'.zip')
                archive(path,'2026-11-09T08:00:00+00:00',dict(MU=92),tamper=error)
                with self.assertRaises(SnapshotError):
                    read_snapshot(path)

    def test_mvp_acceptance_claim_cannot_be_smuggled_into_archival_audit(self):
        path=self.root/'accepted.zip'
        archive(path,'2026-11-09T08:00:00+00:00',dict(MU=92),mvp=True)
        with self.assertRaises(SnapshotError):
            read_snapshot(path)

    def test_model_drift_rejected(self):
        old,new=self.snapshots(dict(MU=92),dict(NOW=62))
        new['model']='different'
        with self.assertRaisesRegex(SnapshotError,'model version'):
            compare(old,new)


if __name__=='__main__':
    unittest.main()
