"""Rebuild the dated 18-score report offline and record byte identity."""
import hashlib
import importlib.util
import json
import tempfile
from datetime import datetime
from pathlib import Path

from equity_research.mvp import save_json

ROOT=Path(__file__).resolve().parents[1]
AS_OF=datetime.fromisoformat('2026-11-03T05:36:21.308165+00:00')
FILES=('report.json.gz','report.md','report.html')


def run():
    path=ROOT/'scripts/build_current_scores.py'
    spec=importlib.util.spec_from_file_location('current_score_builder',path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    target=ROOT/'docs/evidence/current-score100'
    with tempfile.TemporaryDirectory() as folder:
        module.build(financial=ROOT/'docs/evidence/common-financial100/batch.json.gz',
            current=ROOT/'docs/evidence/common-comparative100/current-batch.json.gz',
            prior=ROOT/'docs/evidence/common-comparative100/prior-batch.json.gz',
            sources=ROOT/'tests/fixtures/valuation22-sources',
            financial_sources=[ROOT/'tests/fixtures/liability-equation5-sources'],
            output=folder,as_of=AS_OF)
        checks={}
        for name in FILES:
            original=hashlib.sha256((target/name).read_bytes()).hexdigest()
            reproduced=hashlib.sha256((Path(folder)/name).read_bytes()).hexdigest()
            checks[name]=dict(original=original,reproduced=reproduced)
        result=dict(mode='offline_fixed_cutoff_same_CLI_builder',new_http_requests=0,
            as_of=AS_OF.isoformat(),byte_identical=all(v['original']==v['reproduced'] for v in checks.values()),
            files=checks,mvp_accepted=False)
        if not result['byte_identical']:raise ValueError('dated score report is not reproducible')
        save_json(target/'reproduction-proof.json',result)
        print(json.dumps(result))
        return result


if __name__=='__main__':run()
