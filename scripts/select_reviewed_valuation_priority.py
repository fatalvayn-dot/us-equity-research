"""Authorize a reviewed priority only for an intact production evidence lineage.

The fixed audited checkpoint is the trust anchor. A later valuation artifact can
continue the same priority only if the previous main-run artifact carries an
exact report-digest-bound continuation record. This never approves a score.
"""
import argparse
import hashlib
import json
from pathlib import Path


def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def select(plan, source_run, resume_run, resume_report, lineage=None):
    reviewed = json.loads(plan.read_text())
    if source_run != reviewed['financial_run_id'] or resume_run is None:
        return None
    if resume_run == reviewed['valuation_run_id']:
        if digest(resume_report) != reviewed['valuation_report_sha256']:
            raise ValueError('reviewed valuation continuation report digest mismatch')
        return plan
    if lineage is None or not lineage.is_file():
        return None
    record = json.loads(lineage.read_text())
    if (record.get('schema_version') != 1
            or record.get('source_run_id') != source_run
            or record.get('run_id') != resume_run
            or record.get('root_run_id') != reviewed['valuation_run_id']
            or record.get('root_report_sha256') != reviewed['valuation_report_sha256']
            or record.get('plan_sha256') != digest(plan)):
        return None
    if record.get('report_sha256') != digest(resume_report):
        raise ValueError('reviewed priority lineage report digest mismatch')
    return plan


def record_next(plan, source_run, run_id, report, lineage):
    """Persist an evidence link only when this run really used the priority."""
    reviewed = json.loads(plan.read_text())
    if (source_run != reviewed['financial_run_id']
            or type(run_id) is not int or run_id < 1):
        raise ValueError('priority lineage requires exact financial run and positive run ID')
    payload = json.loads(report.read_text())
    symbols = payload.get('priority_symbols')
    candidates = payload.get('companies')
    expected = {(row['symbol'], row['issuer_id']) for row in reviewed['companies']}
    if (payload.get('report_kind') != 'valuation_source_collection_scope_pending'
            or not isinstance(symbols, list) or not symbols
            or len(symbols) != len(set(symbols))
            or not isinstance(candidates, list)
            or not set(symbols).issubset({symbol for symbol, _ in expected})
            or not set(symbols).issubset({c.get('symbol') for c in candidates})
            or not expected.issubset({(c.get('symbol'), c.get('issuer_id')) for c in candidates})):
        raise ValueError('priority lineage requires a real exact-candidate report')
    priority_gets = sum(
        1 for candidate in candidates if candidate.get('symbol') in symbols
        for attempt in candidate.get('attempts', []) if attempt.get('http_requested') is True)
    if priority_gets == 0:
        # A selected list is not evidence of source acquisition. Do not
        # propagate a stale record against an overwritten report.json.
        lineage.unlink(missing_ok=True)
        return None
    entry = dict(schema_version=1, source_run_id=source_run, run_id=run_id,
                 root_run_id=reviewed['valuation_run_id'],
                 root_report_sha256=reviewed['valuation_report_sha256'],
                 plan_sha256=digest(plan), report_sha256=digest(report),
                 observed_priority_symbols=symbols, priority_http_gets=priority_gets)
    lineage.write_text(json.dumps(entry, sort_keys=True, indent=2) + '\n')
    return entry


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    if len(__import__('sys').argv) > 1 and __import__('sys').argv[1] == 'record':
        parser.add_argument('operation', choices=['record'])
        parser.add_argument('--plan', type=Path, required=True)
        parser.add_argument('--source-run', type=int, required=True)
        parser.add_argument('--run-id', type=int, required=True)
        parser.add_argument('--report', type=Path, required=True)
        parser.add_argument('--lineage', type=Path, required=True)
        args = parser.parse_args()
        record_next(args.plan, args.source_run, args.run_id, args.report, args.lineage)
        return
    parser.add_argument('--plan', type=Path, required=True)
    parser.add_argument('--source-run', type=int, required=True)
    parser.add_argument('--resume-run', type=int)
    parser.add_argument('--resume-report', type=Path, required=True)
    parser.add_argument('--lineage', type=Path)
    args = parser.parse_args()
    chosen = select(**vars(args))
    if chosen is not None:
        print(chosen)


if __name__ == '__main__':
    main()
