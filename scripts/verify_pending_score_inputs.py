"""Verify score operands from an extracted production checkpoint without network."""
import argparse
import json
import sqlite3
from datetime import date, datetime
from pathlib import Path
from types import SimpleNamespace

from equity_research.cache import encode
from equity_research.companyfacts import SecCompanyFacts
from equity_research.concept_diagnostics import inspect_concepts
from equity_research.documents import document_key
from equity_research.fields import SPECS
from equity_research.models import Fact
from equity_research.providers import ProviderFailure
from equity_research.reporting import build_report
from equity_research.scoring import REQUIRED, confirm_score_field
from equity_research.sector_models import MODELS
from equity_research.sector_policy import excluded_banking_or_insurance
from equity_research.transport import Response
from live_checkpoint import verify


RELATED_CONCEPTS = {
    'revenue': 'revenue_total',
    'capital_expenditure': 'productive_asset_cash_payments',
}


def audit_original_gaps(original, *, cik, start, end, missing_fields, cutoff):
    """Explain missing score inputs without selecting a replacement value."""
    fields = [name for name in RELATED_CONCEPTS if name in missing_fields]
    if not fields:
        return None
    if original is None or original.retrieved_at > cutoff:
        return dict(status='original_unavailable_at_cutoff', fields=fields)
    if start is None:
        return dict(status='annual_period_unavailable', fields=fields)
    definitions = {name: (SPECS[name].accounting_definition,
                          SPECS[RELATED_CONCEPTS[name]].accounting_definition)
                   for name in fields}
    proof = dict(url=original.url, sha256=original.sha256,
                 retrieved_at=original.retrieved_at)
    try:
        scan = inspect_concepts(
            original.body, cik=cik, period_start=start, period_end=end,
            concepts=[concept for pair in definitions.values() for concept in pair])
    except ValueError:
        return dict(status='original_diagnostic_unavailable', fields=fields, source=proof)
    concepts = {entry['concept']: entry for entry in scan['concepts']}
    return dict(status='original_diagnostics', source=proof,
                period_start=start, period_end=end, automatic_substitution=False,
                fields=[dict(field=name, required=concepts[required],
                             related=concepts[related],
                             related_scope=SPECS[RELATED_CONCEPTS[name]].scope_note)
                        for name, (required, related) in definitions.items()])


def selected_operating_symbols(metadata):
    """Select only modeled operating issuers from original SEC metadata.

    Fail closed on absent/unknown SIC, unmodeled legal entities and duplicated
    identities. A registry match is not participation-index certification.
    """
    if not isinstance(metadata, dict) or not isinstance(metadata.get('companies'), list):
        raise ValueError('SEC metadata companies required')
    result = []
    seen_symbols, seen_ids = set(), set()
    for row in metadata['companies']:
        if not isinstance(row, dict):
            raise ValueError('invalid metadata row')
        symbol, cik = row.get('symbol'), row.get('issuer_id')
        if (not isinstance(symbol, str) or not symbol or not isinstance(cik, str)
                or len(cik) != 10 or not cik.isascii() or not cik.isdigit()
                or not int(cik) or symbol in seen_symbols or cik in seen_ids):
            raise ValueError('duplicate or invalid SEC metadata identity')
        seen_symbols.add(symbol); seen_ids.add(cik)
        snapshot = row.get('snapshot')
        if not isinstance(snapshot, dict):
            continue
        sic = snapshot.get('sic_label')
        if (snapshot.get('entity_type_label') == 'operating'
                and not excluded_banking_or_insurance(sic)
                and sic in MODELS):
            result.append(symbol)
    return result


def missing_companyfacts_result(company, annual, original, cutoff):
    """Unverified proof report for an issuer lacking SEC Company Facts cache."""
    cik, symbol = company['issuer_id'], company['symbol']
    known_fields = {field['query']['field'] for field in company['fields']
                    if field.get('fact')}
    gaps = audit_original_gaps(
        original, cik=cik,
        start=date.fromisoformat(company['period_start']) if company['period_start'] else None,
        end=date.fromisoformat(annual['report_end']),
        missing_fields=[name for name in REQUIRED if name not in known_fields],
        cutoff=cutoff)
    result = dict(symbol=symbol, issuer_id=cik,
                  annual_accession=annual['accession'], confirmed_fields=0,
                  source_status='sec_companyfacts_cache_missing',
                  checks=[dict(field=name, status='source_cache_missing') for name in REQUIRED])
    if gaps is not None:
        result['original_score_input_gaps'] = gaps
    return result


def audit(root, run_id, symbols):
    manifest, _ = verify(root, run_id, {})
    batch = json.loads((root / 'batch.json').read_text())
    cutoff = datetime.fromisoformat(batch['generated_at'])
    metadata = {row['issuer_id']: row for row in
                json.loads((root / 'metadata.json').read_text())['companies']}
    requested = set(selected_operating_symbols(json.loads(
        (root / 'metadata.json').read_text()))) if symbols is None else set(symbols)
    if not requested:
        raise ValueError('no eligible score audit candidates')
    companies = [row for row in build_report(batch)['companies'] if row['symbol'] in requested]
    if {row['symbol'] for row in companies} != requested:
        raise ValueError('unknown score audit candidate')
    results = []
    with sqlite3.connect((root / 'documents.sqlite').resolve().as_uri() + '?mode=ro', uri=True) as db:
        for company in companies:
            cik, symbol = company['issuer_id'], company['symbol']
            rowmeta = metadata[cik]
            annual = rowmeta['snapshot']['annual_filings'][0]
            if rowmeta['symbol'] != symbol or annual['report_end'] != company['period_end']:
                raise ValueError('candidate annual identity or period mismatch')
            key = document_key(cik, annual)
            row = db.execute('SELECT url,body,sha256,retrieved_at FROM filing_documents_v1 WHERE key=?',
                             (key,)).fetchone()
            original = None
            if row is not None:
                url, body, checksum, stamp = row
                original = Response(url, body, datetime.fromisoformat(stamp))
                if original.url != annual['source_url'] or original.sha256 != checksum:
                    raise ValueError('annual filing body integrity failure')
            cache_path = root / 'companyfacts' / (cik + '.json')
            if not cache_path.is_file():
                results.append(missing_companyfacts_result(company, annual, original, cutoff))
                continue
            envelope = json.loads(cache_path.read_text())
            cf = Response(envelope['url'], envelope['body'].encode('utf-8'),
                          datetime.fromisoformat(envelope['retrieved_at']))
            if cf.sha256 != envelope['sha256']:
                raise ValueError('Company Facts body integrity failure')
            payload = SecCompanyFacts._parse(cf, cik)[1]
            filing = SimpleNamespace(source_url=annual['source_url'],
                                     report_end=date.fromisoformat(annual['report_end']))
            facts = {field['query']['field']: Fact(**field['fact'])
                     for field in company['fields'] if field['fact']}
            checks = []
            for name in REQUIRED:
                if name not in facts:
                    checks.append(dict(field=name, status='selected_fact_missing'))
                    continue
                try:
                    proof = confirm_score_field(facts[name], cf, payload, annual=filing,
                                                original=original, as_of=cutoff)
                    checks.append(dict(status='confirmed', **proof))
                except (ProviderFailure, ValueError, KeyError, TypeError, ArithmeticError) as exc:
                    checks.append(dict(field=name, status='unconfirmed',
                                       reason=exc.status.value if isinstance(exc, ProviderFailure) else str(exc)))
            result = dict(symbol=symbol, issuer_id=cik, annual_accession=annual['accession'],
                          confirmed_fields=sum(c['status'] == 'confirmed' for c in checks), checks=checks)
            gaps = audit_original_gaps(
                original, cik=cik, start=date.fromisoformat(company['period_start']) if company['period_start'] else None,
                end=filing.report_end, missing_fields=[name for name in REQUIRED if name not in facts],
                cutoff=cutoff)
            if gaps is not None:
                result['original_score_input_gaps'] = gaps
            results.append(result)
    return dict(mode='offline_production_score_operands', run_id=run_id,
                sequence=manifest['sequence'], as_of=cutoff, new_http_requests=0,
                companies=results, scores_generated=False, mvp_accepted=False)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--state-dir', type=Path, required=True)
    parser.add_argument('--run-id', type=int, required=True)
    parser.add_argument('--all-modeled', action='store_true',
                        help='Audit every SEC-confirmed modeled operating issuer; exclude banks, insurers and unmodeled entities')
    parser.add_argument('symbols', nargs='*')
    args = parser.parse_args()
    if args.all_modeled and args.symbols:
        parser.error('--all-modeled cannot be combined with explicit symbols')
    if not args.all_modeled and not args.symbols:
        parser.error('provide symbols or --all-modeled')
    print(json.dumps(audit(args.state_dir, args.run_id,
                           None if args.all_modeled else args.symbols),
                     default=encode, indent=2))


if __name__ == '__main__':
    main()
