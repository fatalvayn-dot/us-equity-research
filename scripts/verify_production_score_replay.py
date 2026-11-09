"""Replay a published production score at its original cutoff without network."""
import argparse
import gzip
import hashlib
import json
from collections import Counter
from datetime import datetime
from itertools import chain
from pathlib import Path

from equity_research.cache import encode
from equity_research.evidence_bundle import read_bundle
from equity_research.scoring import build_score_report
from live_checkpoint import verify


def read_json(path):
    return json.loads(path.read_text())


def digest(path):
    with path.open('rb') as source:
        return hashlib.file_digest(source, 'sha256').hexdigest()


def audit(*, financial, financial_run, valuation, financial_sources, score):
    verify(financial, financial_run, {})
    linked = read_json(valuation / 'financial-source-run.json')['run_id']
    if type(linked) is not int or linked != financial_run:
        raise ValueError('valuation and financial run identity mismatch')

    published = score / 'output'
    manifest = read_json(published / 'manifest.json')
    expected_files = {'report.json.gz', 'report.md', 'report.html'}
    if set(manifest['files']) != expected_files or any(
            digest(published / name) != sha for name, sha in manifest['files'].items()):
        raise ValueError('published score file digest mismatch')
    market_sources = valuation / 'source-bundle'
    if digest(market_sources / 'manifest.json') != manifest['source_bundle_manifest_sha256']:
        raise ValueError('published market source manifest mismatch')
    finance_hashes = [digest(path / 'manifest.json') for path in financial_sources]
    if finance_hashes != [item['manifest_sha256'] for item in manifest['additional_financial_source_bundles']]:
        raise ValueError('published financial source manifest mismatch')

    original = json.loads(gzip.decompress((published / 'report.json.gz').read_bytes()))
    as_of = datetime.fromisoformat(manifest['as_of'])
    if original['as_of'] != manifest['as_of'] or original['summary'] != manifest['summary']:
        raise ValueError('published cutoff or summary mismatch')
    responses = chain(read_bundle(market_sources), *(read_bundle(path) for path in financial_sources))
    replay = build_score_report(read_json(financial / 'batch.json'), read_json(score / 'current.json'),
                                read_json(score / 'prior.json'), responses, as_of=as_of)
    replay = json.loads(json.dumps(replay, default=encode))
    if (replay['input_provenance'] != manifest['input_provenance']
            or original['input_provenance'] != manifest['input_provenance']):
        raise ValueError('published score input provenance mismatch')

    def rows(report):
        by_identity = {(row['issuer_id'], row['symbol']): row for row in report['companies']}
        if len(by_identity) != len(report['companies']):
            raise ValueError('duplicate score identity')
        return by_identity

    old, new = rows(original), rows(replay)
    if old.keys() != new.keys() or original['ranking'] != replay['ranking']:
        raise ValueError('replay changed score identities or ranking')
    for key, row in old.items():
        if row['total_score'] is not None and row != new[key]:
            raise ValueError('replay changed a scored company or its evidence')

    changes = [dict(issuer_id=key[0], symbol=key[1], before=old[key]['blockers'],
                    after=new[key]['blockers']) for key in old
               if old[key]['blockers'] != new[key]['blockers']]
    return dict(mode='offline_production_score_replay', financial_run_id=financial_run,
                as_of=manifest['as_of'], new_http_requests=0, summary=replay['summary'],
                ranking=replay['ranking'], scored_company_evidence_unchanged=True,
                old_blockers=dict(Counter(reason for row in old.values() for reason in row['blockers'])),
                replayed_blockers=dict(Counter(reason for row in new.values() for reason in row['blockers'])),
                blocker_changes=changes, mvp_accepted=False)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('financial', 'valuation', 'score'):
        parser.add_argument('--' + name, type=Path, required=True)
    parser.add_argument('--financial-run', type=int, required=True)
    parser.add_argument('--financial-sources', type=Path, action='append', default=[])
    print(json.dumps(audit(**vars(parser.parse_args())), indent=2))


if __name__ == '__main__':
    main()
