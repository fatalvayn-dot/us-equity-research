"""Verify score operands from an extracted production checkpoint without network."""
import argparse
import json
import sqlite3
from datetime import date, datetime
from pathlib import Path
from types import SimpleNamespace

from equity_research.cache import encode
from equity_research.companyfacts import SecCompanyFacts
from equity_research.documents import document_key
from equity_research.models import Fact
from equity_research.providers import ProviderFailure
from equity_research.reporting import build_report
from equity_research.scoring import REQUIRED, confirm_score_field
from equity_research.transport import Response
from live_checkpoint import verify


def audit(root, run_id, symbols):
    manifest, _ = verify(root, run_id, {})
    batch = json.loads((root / 'batch.json').read_text())
    cutoff = datetime.fromisoformat(batch['generated_at'])
    metadata = {row['issuer_id']: row for row in
                json.loads((root / 'metadata.json').read_text())['companies']}
    requested = set(symbols)
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
            envelope = json.loads((root / 'companyfacts' / (cik + '.json')).read_text())
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
            results.append(dict(symbol=symbol, issuer_id=cik, annual_accession=annual['accession'],
                                confirmed_fields=sum(c['status'] == 'confirmed' for c in checks), checks=checks))
    return dict(mode='offline_production_score_operands', run_id=run_id,
                sequence=manifest['sequence'], as_of=cutoff, new_http_requests=0,
                companies=results, scores_generated=False, mvp_accepted=False)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--state-dir', type=Path, required=True)
    parser.add_argument('--run-id', type=int, required=True)
    parser.add_argument('symbols', nargs='+')
    args = parser.parse_args()
    print(json.dumps(audit(args.state_dir, args.run_id, args.symbols), default=encode, indent=2))


if __name__ == '__main__':
    main()
