"""Offline recorded comparisons; explicit cutoff and input/output separation."""
import argparse
import gzip
import html
import json
from datetime import datetime
from itertools import chain
from pathlib import Path

from equity_research.cache import encode
from equity_research.comparative import render_comparative_markdown
from equity_research.comparative_replay import replay_comparisons
from equity_research.evidence_bundle import read_bundle
from equity_research.mvp import save_json, save_text


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--candidates', required=True)
    parser.add_argument('--documents', action='append', required=True)
    parser.add_argument('--sources', action='append', required=True)
    parser.add_argument('--as-of', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    output = Path(args.output).resolve()
    inputs = [Path(p).resolve() for p in [args.candidates]+args.documents+args.sources]
    if any(p == output or output in p.parents or p in output.parents for p in inputs):
        parser.error('output directory must be separate from all inputs and source bundles')
    def read(path):
        data = Path(path).read_bytes()
        return json.loads(gzip.decompress(data) if str(path).endswith('.gz') else data)
    result = replay_comparisons(read(args.candidates), [read(p) for p in args.documents],
        chain.from_iterable(read_bundle(p) for p in args.sources), as_of=datetime.fromisoformat(args.as_of))
    for key, value in result.items():
        name = key.replace('_', '-')
        if key.endswith('batch') or key == 'report':
            payload = json.dumps(value, default=encode, sort_keys=True).encode()
            output.mkdir(parents=True, exist_ok=True)
            (output/(name+'.json.gz')).write_bytes(gzip.compress(payload, mtime=0))
        else:
            save_json(output/(name+'.json'), value)
    audit=result['audit']
    unresolved=audit['deferred']+[{k:p[k] for k in ('symbol','issuer_id','status')}
        for p in audit['plans'] if p['status']!='ready_for_ordered_collection']
    notice=['Recorded source replay; zero new HTTP requests. Not a live or historical-vintage acceptance.', '',
        f"Candidates: {audit['candidates']}; current values: {audit['current_facts']}; prior values: {audit['prior_facts']}.",
        'Unresolved candidates (no invented growth or score):', '']
    notice.extend('- '+html.escape(r['symbol'])+': '+r['status'] for r in unresolved)
    save_text(output/'report.md', '\n'.join(notice)+'\n\n'+render_comparative_markdown(result['report']))
    print(json.dumps({k:v for k,v in result['audit'].items() if k not in ('plans','deferred')}, default=encode))


if __name__ == '__main__':
    main()
