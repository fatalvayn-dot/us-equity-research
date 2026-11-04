"""Portable pilot-ranking browser; escaped content, no remote scripts."""
from .turkish import label, calculation_label
from html import escape
from decimal import Decimal


def render_score_html(report):
    def e(value):return escape(label(value),quote=True)
    def number(value,digits=6):return format(Decimal(str(value)),f'.{digits}f')
    ranked=''.join('<tr>'+''.join('<td>'+e(c[k])+'</td>' for k in ('rank','symbol','score','model_id'))+'</tr>' for c in report['ranking'])
    cards=[]
    for c in report['companies']:
        score='puan yok' if c['total_score'] is None else e(c['total_score'])+' / 100'
        components=''.join('<tr><td>'+e(k)+'</td><td>'+('hesaplanmadı' if v['score'] is None else e(v['score']))+'</td><td>'+e(v['weight'])+'</td></tr>' for k,v in c['components'].items())
        proof=[]
        for item in c.get('evidence',{}).get('financial_confirmations',[]):
            f=item['selected'];verified=item['confirmed']
            proof.append('<tr>'+''.join('<td>'+v+'</td>' for v in (e(label(item['field'])),e(f['value'])+' '+e(f['currency']),
                e(f['period_start'] or 'instant')+' / '+e(f['period_end']),
                '<a href="'+e(f['source_url'])+'" target="_blank" rel="noopener noreferrer">kaynak</a><small>'+e(f['raw_sha256'])+'</small>',
                '<a href="'+e(verified['source_url'])+'" target="_blank" rel="noopener noreferrer">SEC doğrulaması</a><small>'+e(verified['raw_sha256'])+'</small>'))+'</tr>')
        extra=''
        if c['total_score'] is not None:
            metrics=''.join('<li>'+e(k)+': '+e(number(v))+'</li>' for k,v in c['metrics'].items())
            market=c['market_risk'];v=c['valuation'];p=v['indication']['price'];s=v['indication']['disclosed_shares']
            extra=f'''<p>Finansal oranlar:</p><ul>{metrics}</ul>
<p>Değerleme girdisi: {e(p['value'])} USD fiyat × {e(s['value'])} tarihli bildirilmiş hisse.
Hisse sayısı tarihi: {e(s['disclosed_on'])}. Fiyat zamanı: {e(p['market_at'])}.</p>
<p>Değerleme puanı için %25 ek hisse ve bir raporlama hassasiyet birimi uygulanır.
Bu, gerçek hisse sayısı veya istatistiksel güven aralığı değildir. Bölünme dışındaki sermaye değişiklikleri doğrulanmış sayılmaz.</p>
<p>Gözlenen yıllıklandırılmış fiyat oynaklığı: {e(number(market['annualized_sample_volatility']))}.
63 seanslık medyan kapanış × hacim: {e(number(market['median_63_session_close_times_volume'],2))} USD.</p>
<p><a href="{e(market['source_url'])}" target="_blank" rel="noopener noreferrer">Piyasa geçmişi</a><small>{e(market['raw_sha256'])}</small></p>
<div class="scroll"><table><thead><tr><th>Alan</th><th>Değer</th><th>Dönem</th><th>İlk kaynak</th><th>Bağımsız kontrol</th></tr></thead><tbody>{''.join(proof)}</tbody></table></div>'''
        cards.append(f'''<article data-scored="{str(c['total_score'] is not None).lower()}">
<h2>{e(c['symbol'])} <small>CIK {e(c['issuer_id'])}</small></h2><p class="score">{score}</p>
<p>Durum: {e(c['status'])}. Engeller: {e('; '.join(c['blockers']+([c['failed_validation_stage']] if c.get('failed_validation_stage') else [])) or 'sayısal araştırma modeli için yok')}.</p>
<details><summary>Bileşenler, gerekçe ve kaynaklar</summary><div class="scroll"><table><thead><tr><th>Bileşen</th><th>Puan</th><th>Ağırlık</th></tr></thead><tbody>{components}</tbody></table></div>{extra}
<p>Nitel riskler, yönetim ve tüm sermaye değişiklikleri onaylanmış değildir. Yatırım onayı: verilmedi.</p></details></article>''')
    summary=report['summary']
    provenance=''
    if report.get('input_provenance'):
        dates=''.join('<li>'+e(name)+': '+e(s['oldest_selected_observation'])+' / '+e(s['newest_selected_observation'])+'<small>SHA-256 '+e(s['sha256'])+'</small></li>' for name,s in report['input_provenance']['batches'].items())
        provenance='<p class="notice">Finansal ve karşılaştırma girdilerinin kaynak tarihleri korunmuştur. Raporun üretilmesi bütün 100 şirketin finansal verilerinin yeniden toplandığı anlamına gelmez.</p><ul>'+dates+'</ul>'
    return f'''<!doctype html><html lang="tr"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'; script-src 'unsafe-inline'; base-uri 'none'; form-action 'none'">
<title>ABD Hisse Araştırması — puanlama prototipi</title><style>
body{{font:16px/1.5 system-ui,sans-serif;background:#f3f5f7;color:#1b2a39;margin:auto;max-width:1100px;padding:24px}}
header,article{{background:white;padding:22px;border:1px solid #d8e0e7;border-radius:10px;margin-bottom:18px}}
h1,h2{{margin:0 0 12px}}h2 small{{font-weight:400;font-size:14px}}small{{display:block;overflow-wrap:anywhere}}
.notice{{background:#fff0d3;padding:12px}}.score{{font-size:22px;font-weight:600}}.scroll{{overflow:auto}}
table{{border-collapse:collapse;width:100%;margin:12px 0}}td,th{{text-align:left;padding:9px;border-bottom:1px solid #dde3e9;vertical-align:top}}
summary{{cursor:pointer;font-weight:600}}label{{display:inline-block;margin:10px 16px 10px 0}}input,select{{padding:7px;font:inherit;max-width:100%}}
[hidden]{{display:none!important}}a{{color:#075b9e}}
</style></head><body><header><h1>ABD Hisse Araştırması</h1><p>Araştırma puanlama prototipi · Kaynak verilerinin kesim zamanı: {e(report['as_of'])}</p>
{provenance}<p>{summary['candidates']} aday · {summary['scored_companies']} araştırma puanı · {summary['unscored']} puansız · {summary['critical_review']} kritik inceleme</p>
<p class="notice">100 aktif adi hisselik MVP henüz kabul edilmedi. Puanlar sınırlı sektör modelinin başlangıç hipotezidir;
getiri başarısı, alım önerisi veya yatırım onayı değildir. Kayıtlı veriler canlı fiyat hizmeti olarak sunulmaz.</p>
<h2>Puanlanabilen örnek şirketler</h2><div class="scroll"><table><thead><tr><th>Sıra</th><th>Sembol</th><th>Puan / 100</th><th>Model</th></tr></thead><tbody>{ranked}</tbody></table></div>
<label>Sembol / CIK ara <input id="search" type="search"></label><label>Görünüm <select id="mode"><option value="">Tüm adaylar</option><option value="true">Puanlananlar</option><option value="false">Puansızlar</option></select></label>
<p id="count" aria-live="polite">{summary['candidates']} aday gösteriliyor</p></header><main>{''.join(cards)}</main><script>
const search=document.getElementById('search'),mode=document.getElementById('mode');
function filter(){{let n=0;const query=search.value.trim().toLowerCase();for(const card of document.querySelectorAll('article')){{const show=card.querySelector('h2').textContent.toLowerCase().includes(query)&&(!mode.value||card.dataset.scored===mode.value);card.hidden=!show;if(show)n++;}}document.getElementById('count').textContent=n+' aday gösteriliyor';}}
search.addEventListener('input',filter);mode.addEventListener('change',filter);
</script></body></html>'''
