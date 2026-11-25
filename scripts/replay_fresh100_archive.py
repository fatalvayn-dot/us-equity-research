"""Replay pinned fresh100 evidence at its original cutoff without provider access."""
import argparse
import gzip
import hashlib
import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from equity_research.batch import BatchRunner, BatchStore, load_plan
from equity_research.cache import encode
from equity_research.evidence_bundle import read_bundle
from equity_research.models import Source, aware
from equity_research.pipeline import research_resolver
from equity_research.providers import ProviderFailure, Status
from equity_research.sec import DIRECTORY_URL, parse_directory
from scripts.build_current_scores import build
from scripts.prepare_first_score_plans import plans


MODE = 'archived_source_replay_not_current_analysis'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def replay_basis(evidence, recovered):
    """Bind cutoff and original score to the unchanged recovered input hashes."""
    manifest = json.loads((evidence / 'scoring/manifest.json').read_text())
    report_path = evidence / 'scoring/report.json.gz'
    if sha(report_path) != manifest['files']['report.json.gz']:
        raise ValueError('Özgün skor raporu SHA değeri uyuşmuyor')
    original = json.loads(gzip.decompress(report_path.read_bytes()))
    cutoff = datetime.fromisoformat(manifest['as_of'])
    receipt = json.loads((recovered / 'valuation/cohort-handoff.json').read_text())
    if (not aware(cutoff) or original['as_of'] != manifest['as_of']
            or original['summary'] != manifest['summary']
            or receipt.get('purpose') != 'fresh100_same_cohort_artifact_recovery'
            or receipt.get('recovered_without_provider_requests') is not True
            or receipt['financial_batch_sha256'] != sha(recovered / 'financial/batch.json')
            or receipt['metadata_sha256'] != sha(recovered / 'financial/metadata.json')
            or receipt['valuation_report_sha256'] != sha(recovered / 'valuation/report.json')
            or manifest['source_bundle_manifest_sha256'] != sha(recovered / 'valuation/source-bundle/manifest.json')
            or [x['manifest_sha256'] for x in manifest['additional_financial_source_bundles']]
            != [sha(recovered / 'financial-evidence/live-sources/manifest.json')]):
        raise ValueError('Arşiv kesim zamanı veya kaynak SHA zinciri uyuşmuyor')
    return cutoff, original


class RecordedTransport:
    """No network fallback, including for absent later-provider observations."""
    max_bytes = 32 * 1024 * 1024

    def __init__(self, responses):
        self.responses = responses

    def get(self, url, **kwargs):
        if url not in self.responses:
            raise ProviderFailure(Status.NOT_CONFIGURED)
        return self.responses[url]


def replay(*, evidence: Path, recovered: Path, output: Path):
    cutoff, original = replay_basis(evidence, recovered)
    if output.exists():
        raise ValueError('Arşiv replay hedefi boş olmalıdır')
    responses = {}
    for directory in (recovered / 'valuation/source-bundle', recovered / 'financial-evidence/live-sources'):
        for response in read_bundle(directory):
            if response.retrieved_at > cutoff:
                raise ValueError('Arşiv kesim zamanından sonraki kaynak kullanılamaz')
            old = responses.get(response.url)
            if old is None or old.retrieved_at < response.retrieved_at:
                responses[response.url] = response
            elif old.retrieved_at == response.retrieved_at and old.sha256 != response.sha256:
                raise ValueError('Aynı zamanda çelişen arşiv gözlemi')
    directory = parse_directory(responses[DIRECTORY_URL])
    read = lambda path: json.loads(path.read_text())
    financial = read(recovered / 'financial/batch.json')
    current_plan, prior_plan, selection = plans(financial,
        read(recovered / 'financial/metadata.json'), read(recovered / 'valuation/report.json'),
        recovered / 'financial/companyfacts')
    output.mkdir(parents=True)
    transport = RecordedTransport(responses)
    clock = lambda: cutoff
    with tempfile.TemporaryDirectory() as scratch:
        def factory(company):
            if directory.lookup(company.symbol, expected_cik=company.issuer_id) is None:
                raise ValueError('Arşiv şirket kimliği uyuşmuyor')
            resolver = research_resolver(directory=directory, symbol=company.symbol,
                user_agent='offline-archive-replay', cache_dir=Path(scratch) / 'cache',
                clock=clock, transport_factory=lambda hosts: transport)
            # Finnhub has its own credential-backed transport. There are no
            # Finnhub observations in this public archive; never initialize it.
            resolver.providers.pop(Source.FINNHUB, None)
            return resolver
        for name, plan in (('current', current_plan), ('prior', prior_plan)):
            store = BatchStore(Path(scratch) / (name + '.sqlite'))
            try:
                batch = BatchRunner(store, factory, clock=clock).run(load_plan(plan))
            finally:
                store.close()
            (output / (name + '.json')).write_text(json.dumps(batch, default=encode))
    # The builder independently verifies and reads the same bundles. Release
    # the comparison transport's large raw bodies before that second pass.
    responses.clear()
    (output / 'selection.json').write_text(json.dumps(selection, ensure_ascii=False))
    report = build(financial=recovered / 'financial/batch.json', current=output / 'current.json',
        prior=output / 'prior.json', sources=recovered / 'valuation/source-bundle',
        financial_sources=[recovered / 'financial-evidence/live-sources'],
        output=output / 'report', as_of=cutoff, mode=MODE)
    report = json.loads(json.dumps(report, default=encode))
    # This gate detects changed numeric scores, identities and ranking; missing
    # evidence remains missing and is never filled to meet a target count.
    if (report['summary'] != original['summary'] or report['ranking'] != original['ranking']
            or [(c['issuer_id'], c['symbol'], c['total_score']) for c in report['companies']]
            != [(c['issuer_id'], c['symbol'], c['total_score']) for c in original['companies']]):
        raise ValueError('Arşiv replay özgün skor veya şirket kimliklerini değiştirdi')
    receipt = dict(mode=MODE, as_of=cutoff.isoformat(), summary=report['summary'],
        replayed_at=datetime.now(timezone.utc).isoformat(),
        provider_network_requests=0, original_scores_reproduced=True,
        original_manifest_sha256=sha(evidence / 'scoring/manifest.json'),
        recovery_receipt_sha256=sha(recovered / 'valuation/cohort-handoff.json'),
        current_investment_analysis=False, investment_approved=False, mvp_accepted=False)
    (output / 'replay-receipt.json').write_text(json.dumps(receipt, indent=2))
    return receipt


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('evidence', 'recovered', 'output'):
        parser.add_argument('--' + name, type=Path, required=True)
    receipt = replay(**vars(parser.parse_args()))
    print(json.dumps(receipt, ensure_ascii=False))
    if os.environ.get('GITHUB_STEP_SUMMARY'):
        with Path(os.environ['GITHUB_STEP_SUMMARY']).open('a') as summary:
            summary.write(f"## Arşiv skor doğrulaması\n\nKaynak kesim zamanı: {receipt['as_of']}. "
                          f"Özgün puanları yeniden doğrulanan: {receipt['summary']['scored_companies']}/100. "
                          "Yeni sağlayıcı isteği: 0. Güncel analiz veya yatırım onayı değildir.\n")
