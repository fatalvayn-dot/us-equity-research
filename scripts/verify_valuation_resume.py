"""Verify immediate cached reproduction; do not relabel old quotes as newly fetched."""
import argparse
import json
from pathlib import Path
from verify_valuation_inputs import run

ROOT=Path(__file__).resolve().parents[1]


def main(user_agent):
    state=ROOT/'data/valuation-sample'
    before=json.loads((state/'report.json').read_text())
    run(state,user_agent)
    after=json.loads((state/'report.json').read_text());audit=json.loads((state/'audit.json').read_text())
    old={r['symbol']:r['valuation'] for r in before['companies'] if r['valuation']}
    new={r['symbol']:r['valuation'] for r in after['companies'] if r['valuation']}
    unchanged=old.keys()==new.keys() and all(all(old[s][k]==new[s][k] for k in ('price','disclosed_shares','metrics','indicated_capitalization')) for s in old)
    result=dict(source_get_invocations=audit['source_get_invocations'],
        price_get_invocations=audit['new_price_get_invocations'],identity_get_invocations=audit['new_identity_get_invocations'],
        original_prices_counts_sources_times_and_indications_unchanged=unchanged,
        before_cutoff=before['as_of'],after_cutoff=after['as_of'],companies=len(new),fresh_live_acceptance=False)
    if any(result[k]!=0 for k in ('source_get_invocations','price_get_invocations','identity_get_invocations')) or not unchanged:
        raise ValueError('not a zero-network unchanged-source resume; do not publish as one')
    target=ROOT/'docs/evidence/valuation-sample/zero-work-resume.json'
    target.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--user-agent',required=True)
    main(parser.parse_args().user_agent)
