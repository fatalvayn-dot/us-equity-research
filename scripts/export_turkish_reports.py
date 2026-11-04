"""Kayıtlı prototip raporlarını kaynak tarihlerini değiştirmeden Türkçe yayımla.

Çalıştırma: PYTHONPATH=src python scripts/export_turkish_reports.py
Ağ isteği yapmaz; mevcut tarihli JSON kayıtlarını yalnızca görünüme dönüştürür.
"""
import gzip
import hashlib
import json
from pathlib import Path

from equity_research.financial_cohort import render_cohort_html, render_cohort_markdown
from equity_research.scoring import render_score_markdown
from equity_research.score_html import render_score_html
from equity_research.comparative import render_comparative_markdown
from equity_research.valuation import render_valuation_markdown
from equity_research.mvp import save_text
from equity_research.prices import render_price_markdown

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / 'docs/evidence/turkish-reports'
REPORTS = (
    ('common-price100/report.json.gz', 'fiyat-raporu', (('md', render_price_markdown),)),
    ('current-score100/report.json.gz', 'radar', (('html', render_score_html), ('md', render_score_markdown))),
    ('common-financial100/report.json.gz', 'finansal-rapor', (('html', render_cohort_html), ('md', render_cohort_markdown))),
    ('common-comparative100/report.json.gz', 'yillik-karsilastirma', (('md', render_comparative_markdown),)),
    ('valuation-sample/report.json.gz', 'degerleme-orneklemi', (('md', render_valuation_markdown),)),
)


def main():
    OUTPUT.mkdir(parents=True, exist_ok=True)
    inputs = {}; outputs = {}
    for source, name, renderers in REPORTS:
        path = ROOT / 'docs/evidence' / source
        data = path.read_bytes()
        report = json.loads(gzip.decompress(data) if path.suffix == '.gz' else data)
        inputs[source] = dict(sha256=hashlib.sha256(data).hexdigest(), as_of=report.get('as_of') or report['generated_at'])
        for extension, render in renderers:
            filename = name + '.' + extension
            text = render(report)
            save_text(OUTPUT / filename, text)
            outputs[filename] = hashlib.sha256(text.encode()).hexdigest()
    manifest = dict(language='tr', mode='recorded_report_presentation_only', new_network_requests=0,
                    source_dates_refreshed=False, mvp_accepted=False, inputs=inputs, outputs=outputs)
    save_text(OUTPUT / 'manifest.json', json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True)+'\n')
    print('Türkçe raporlar üretildi; kaynak tarihleri korunmuştur.')


if __name__ == '__main__':
    main()
