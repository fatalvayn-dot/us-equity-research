"""Bind the exact common100 financial/comparison inputs to a dated market collection."""
import argparse
import gzip
import hashlib
import json
import os
import tempfile
from datetime import datetime
from pathlib import Path

from equity_research.cache import encode
from equity_research.evidence_bundle import read_bundle
from equity_research.mvp import save_json, save_text
from equity_research.scoring import build_score_report, render_score_markdown
from equity_research.score_html import render_score_html


def build(*, financial, current, prior, sources, output, as_of):
    output=Path(output).resolve()
    inputs=[Path(p).resolve() for p in (financial,current,prior,sources)]
    if any(p==output or output in p.parents or p in output.parents for p in inputs):
        raise ValueError('score output directory must be separate from all inputs')
    def read(path):
        data=path.read_bytes()
        return json.loads(gzip.decompress(data) if str(path).endswith('.gz') else data)
    report=build_score_report(*(read(p) for p in inputs[:3]),read_bundle(inputs[3]),as_of=as_of)
    output.mkdir(parents=True,exist_ok=True)
    data=json.dumps(report,default=encode,sort_keys=True).encode()
    # Replace the directory entry atomically; never follow an existing output
    # symlink into a raw source bundle, even when the output directory is separate.
    temporary=None
    try:
        with tempfile.NamedTemporaryFile(dir=output,delete=False) as handle:
            temporary=handle.name;handle.write(gzip.compress(data,mtime=0));handle.flush();os.fsync(handle.fileno())
        os.replace(temporary,output/'report.json.gz')
    finally:
        if temporary and os.path.exists(temporary):os.unlink(temporary)
    save_text(output/'report.md',render_score_markdown(report))
    save_text(output/'report.html',render_score_html(report))
    save_json(output/'manifest.json',dict(as_of=as_of,summary=report['summary'],mvp_accepted=False,
        mode='current_market_sources_with_recorded_financial_inputs',new_http_requests=0,
        source_bundle_manifest_sha256=hashlib.sha256((inputs[3]/'manifest.json').read_bytes()).hexdigest(),
        input_provenance=report['input_provenance'],
        files={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in output.iterdir() if p.name!='manifest.json'}))
    return report


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for arg in ('financial','current','prior','sources','output','as-of'):parser.add_argument('--'+arg,required=True)
    args=parser.parse_args()
    report=build(financial=args.financial,current=args.current,prior=args.prior,sources=args.sources,
                 output=args.output,as_of=datetime.fromisoformat(args.as_of))
    print(json.dumps(report['summary']))


if __name__=='__main__':main()
