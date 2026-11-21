"""Separate live-helper integration cohort, followed by an unchanged zero-GET rerun."""
import argparse
import json
import shutil
from pathlib import Path
from verify_research_score import run

ROOT=Path(__file__).resolve().parents[1]


def main(user_agent):
    state=ROOT/'data/research-score-refresh-check'
    before=json.loads((state/'report.json').read_text());first=json.loads((state/'audit.json').read_text())
    run(state,user_agent)
    after=json.loads((state/'report.json').read_text());last=json.loads((state/'audit.json').read_text())
    keys=('sec_source_get_invocations','quote_get_invocations','identity_get_invocations','history_get_invocations')
    first_calls={k:first[k] for k in keys};last_calls={k:last[k] for k in keys}
    old={c['symbol']:c for c in before['companies'] if c['total_score'] is not None}
    new={c['symbol']:c for c in after['companies'] if c['total_score'] is not None}
    stable=(before['ranking']==after['ranking'] and old.keys()==new.keys() and all(
        all(old[s][k]==new[s][k] for k in ('components','metrics','market_risk','valuation')) for s in old))
    # Only report evaluation times may change; the valuation's financial review
    # includes that evaluation cutoff, so compare its sourced inputs explicitly.
    if not stable:
        stable=before['ranking']==after['ranking'] and old.keys()==new.keys() and all(
            all(old[s][k]==new[s][k] for k in ('components','metrics','market_risk')) and
            all(old[s]['valuation']['indication'][k]==new[s]['valuation']['indication'][k] for k in ('price','disclosed_shares','metrics','indicated_capitalization')) for s in old)
    if not stable or any(v!=0 for v in last_calls.values()):raise ValueError('not unchanged zero-GET reproduction')
    bundle=ROOT/'tests/fixtures/score-helper-market-sources';bundle.mkdir(parents=True,exist_ok=True)
    manifest=json.loads((state/'market-bundle/manifest.json').read_text())
    for name in ['manifest.json']+[p['file'] for p in manifest['parts']]:shutil.copy2(state/'market-bundle'/name,bundle/name)
    result=dict(initial_get_invocations=first_calls,resume_get_invocations=last_calls,
        original_sources_times_components_metrics_and_ranking_unchanged=True,
        before_cutoff=before['as_of'],after_cutoff=after['as_of'],ranking=after['ranking'],
        source_bundles=['tests/fixtures/valuation-sources','tests/fixtures/score-helper-market-sources'],
        cohort='separate_live_helper_integration_not_primary_pilot_capture',mvp_accepted=False)
    target=ROOT/'docs/evidence/score-pilot/live-helper-validation.json'
    target.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--user-agent',required=True)
    main(parser.parse_args().user_agent)
