"""Bind the exact common100 financial/comparison inputs to a dated market collection."""
import argparse
import gzip
import hashlib
import json
import os
import tempfile
from datetime import datetime
from itertools import chain
from pathlib import Path

from equity_research.cache import encode
from equity_research.evidence_bundle import read_bundle
from equity_research.mvp import save_json, save_text
from equity_research.scoring import build_score_report, ACTIVE_MODEL_VERSION, render_score_markdown
from equity_research.sec_attestation import guard_selected_batch
from equity_research.score_html import render_score_html


def build(*, financial, current, prior, sources, output, as_of, financial_sources=(),
          sec_stage1=None, sec_raw_dir=None):
    output=Path(output).resolve()
    extra_source_labels=[str(Path(p)) for p in financial_sources]
    extra_sources=[Path(p).resolve() for p in financial_sources]
    if (sec_stage1 is None) != (sec_raw_dir is None):
        raise ValueError('both verified stage-one manifest and original raw directory required')
    extra_evidence=[Path(p).resolve() for p in (sec_stage1,sec_raw_dir) if p is not None]
    inputs=[Path(p).resolve() for p in (financial,current,prior,sources)]+extra_sources+extra_evidence
    if any(p==output or output in p.parents or p in output.parents for p in inputs):
        raise ValueError('score output directory must be separate from all inputs')
    def read(path):
        data=path.read_bytes()
        return json.loads(gzip.decompress(data) if str(path).endswith('.gz') else data)
    financial_batch=read(inputs[0]);current_batch=read(inputs[1]);prior_batch=read(inputs[2])
    corroboration=(guard_selected_batch(financial_batch,sec_raw_dir,read(Path(sec_stage1)),as_of=as_of)
                   if sec_stage1 is not None else None)
    responses=chain(read_bundle(inputs[3]),*(read_bundle(p) for p in extra_sources))
    report=build_score_report(financial_batch,current_batch,prior_batch,responses,as_of=as_of,
                              model_version=ACTIVE_MODEL_VERSION)
    # Separate read-only corroboration is not a source selected by the resolver.
    if corroboration is not None:
        report['supplemental_sec_evidence']=corroboration
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
        additional_financial_source_bundles=[dict(path=label,manifest_sha256=hashlib.sha256((p/'manifest.json').read_bytes()).hexdigest())
            for label,p in zip(extra_source_labels,extra_sources)],
        input_provenance=report['input_provenance'],
        supplemental_sec_evidence=corroboration,
        files={name:hashlib.sha256((output/name).read_bytes()).hexdigest()
               for name in ('report.json.gz','report.md','report.html')}))
    return report


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for arg in ('financial','current','prior','sources','output','as-of'):parser.add_argument('--'+arg,required=True)
    parser.add_argument('--financial-sources',action='append',default=[],help='additional original-filing public source bundle')
    parser.add_argument('--sec-stage1',help='optional reviewed SEC SHA-256 evidence JSON')
    parser.add_argument('--sec-raw-dir',help='original immutable SEC JSON directory required with --sec-stage1')
    args=parser.parse_args()
    report=build(financial=args.financial,current=args.current,prior=args.prior,sources=args.sources,
                 output=args.output,as_of=datetime.fromisoformat(args.as_of),financial_sources=args.financial_sources,
                 sec_stage1=args.sec_stage1,sec_raw_dir=args.sec_raw_dir)
    print(json.dumps(report['summary']))


if __name__=='__main__':main()
