"""Compare *verified* dated score artifacts without blending market snapshots.

Inputs are the original GitHub Actions artifact ZIPs, not unverified reports.
Each ZIP must carry a report and its signed-by-content SHA-256 manifest.
This is a coverage audit, not an investment ranking or a current valuation.
"""
import argparse
import gzip
import hashlib
import json
import zipfile
from datetime import datetime
from pathlib import Path


class SnapshotError(ValueError):
    pass


def read_snapshot(path):
    with zipfile.ZipFile(path) as artifact:
        names = artifact.namelist()
        if len(names) != len(set(names)):
            raise SnapshotError('duplicate artifact member')
        for required in ('output/manifest.json', 'output/report.json.gz'):
            if required not in names:
                raise SnapshotError('missing score artifact content')
        manifest = json.loads(artifact.read('output/manifest.json'))
        files = manifest.get('files')
        if not isinstance(files, dict) or set(files) != {'report.json.gz', 'report.md', 'report.html'}:
            raise SnapshotError('incomplete score manifest')
        for name, expected in files.items():
            if type(expected) is not str or len(expected) != 64:
                raise SnapshotError('invalid expected source digest')
            actual = hashlib.sha256(artifact.read('output/' + name)).hexdigest()
            if actual != expected:
                raise SnapshotError('score manifest digest mismatch')
        report = json.loads(gzip.decompress(artifact.read('output/report.json.gz')))
        if (manifest.get('summary') != report.get('summary')
                or manifest.get('as_of') != report.get('as_of')
                or report.get('mvp_accepted') is not False
                or manifest.get('mvp_accepted') is not False
                or manifest.get('mode') != 'current_market_sources_with_recorded_financial_inputs'):
            raise SnapshotError('score summary or acceptance mismatch')
        try:
            stamp = datetime.fromisoformat(report['as_of'])
        except (TypeError, ValueError, KeyError) as exc:
            raise SnapshotError('missing score cutoff') from exc
        if stamp.tzinfo is None or stamp.utcoffset() is None:
            raise SnapshotError('timezone-aware cutoff required')
        candidates = report.get('companies')
        ranking = report.get('ranking')
        if (not isinstance(candidates, list) or not isinstance(ranking, list)
                or report['summary'].get('candidates') != len(candidates)
                or report['summary'].get('scored_companies') != len(ranking)):
            raise SnapshotError('invalid score counts')
        by_identity = {}
        for candidate in candidates:
            key = (candidate.get('issuer_id'), candidate.get('symbol'))
            if not all(isinstance(v, str) and v for v in key) or key in by_identity:
                raise SnapshotError('duplicate or invalid candidate identity')
            by_identity[key] = candidate
        scored = {}
        for i, row in enumerate(ranking, 1):
            key = (row.get('issuer_id'), row.get('symbol'))
            company = by_identity.get(key)
            if (key in scored or not company or company.get('total_score') is None
                    or company.get('status') != 'scored_research_hypothesis'
                    or row.get('rank') != i
                    or company.get('rank') != i
                    or str(row.get('score')) != str(company['total_score'])):
                raise SnapshotError('score ranking or identity mismatch')
            confirmations = company.get('evidence', {}).get('financial_confirmations', [])
            if len(confirmations) != 9:
                raise SnapshotError('missing verified financial confirmations')
            scored[key] = str(row['score'])
        return dict(cutoff=report['as_of'], model=report['model_version'],
                    scored=scored, candidates=len(candidates),
                    source_sha256=hashlib.sha256(Path(path).read_bytes()).hexdigest(),
                    score_report_sha256=files['report.json.gz'])


def compare(previous, current):
    if previous['model'] != current['model']:
        raise SnapshotError('model version changed: scores are not comparable')
    old, new = previous['scored'], current['scored']
    keys = sorted(set(old) | set(new), key=lambda key:(key[1], key[0]))
    rows = []
    for cik, symbol in keys:
        key=(cik,symbol)
        rows.append(dict(symbol=symbol,issuer_id=cik,
                         previous_score=old.get(key),current_score=new.get(key),
                         availability='both' if key in old and key in new else
                             'previous_only' if key in old else 'current_only'))
    return dict(schema_version=1,report_kind='dated_score_coverage_audit',
        model_version=current['model'],
        previous=dict(cutoff=previous['cutoff'],artifact_sha256=previous['source_sha256'],
                      score_report_sha256=previous['score_report_sha256'],
                      candidates=previous['candidates'],scored=len(old)),
        current=dict(cutoff=current['cutoff'],artifact_sha256=current['source_sha256'],
                     score_report_sha256=current['score_report_sha256'],
                     candidates=current['candidates'],scored=len(new)),
        distinct_historically_scored=len(keys),
        both=sum(x['availability']=='both' for x in rows),
        previous_only=sum(x['availability']=='previous_only' for x in rows),
        current_only=sum(x['availability']=='current_only' for x in rows),
        companies=rows,mvp_accepted=False,investment_approved=False,
        limitations=['not_a_combined_current_ranking',
                     'previous_only_scores_are_historical_not_current',
                     'no_cross_date_score_improvement_claim'])


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--previous-artifact',type=Path,required=True)
    parser.add_argument('--current-artifact',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    previous=read_snapshot(args.previous_artifact)
    current=read_snapshot(args.current_artifact)
    if datetime.fromisoformat(previous['cutoff']) >= datetime.fromisoformat(current['cutoff']):
        raise SnapshotError('previous cutoff must be strictly earlier')
    result=compare(previous,current)
    args.output.write_text(json.dumps(result,indent=2,ensure_ascii=False)+'\n')
    print(json.dumps({k:result[k] for k in
                      ('distinct_historically_scored','both','previous_only','current_only')}))


if __name__=='__main__':
    main()
