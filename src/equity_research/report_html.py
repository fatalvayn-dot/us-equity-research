"""Portable research browser. All company and source text is escaped."""
from .turkish import label, calculation_label
from html import escape


def render_html(report):
    def text(value): return escape(label(value), quote=True)
    def amount(value): return 'Mevcut değil' if value is None else text(value)
    cards=[]
    for company in report['companies']:
        assessment=company['financial_assessment']
        fields=[]
        for row in company['fields']:
            fact=row['fact'];query=row['query']
            proof=(f'<a href="{text(fact["source_url"])}" target="_blank" rel="noopener noreferrer">kaynak</a>'
                   f'<small>{text(fact["raw_sha256"])}</small>' if fact else 'Mevcut değil')
            attempts='; '.join(a['source']+': '+label(a['status']) for a in row['attempts']) or 'Henüz denenmedi'
            fields.append('<tr>'+''.join('<td>'+v+'</td>' for v in (
                text(query['field']), amount(fact['value'])+' '+text(fact['currency']) if fact else 'Mevcut değil',
                text(query['accounting_definition']),text(attempts),proof))+'</tr>')
        checks=''.join('<li><strong>'+text(c['check'])+': '+text(c['status'])+'</strong> '+text(c['explanation'])
                       + (' Eksik: '+text(', '.join(label(f) for f in c['missing_fields']))+'.' if c['missing_fields'] else '')
                       + (' Reddedilen: '+text('; '.join(label(r['field'])+': '+label(r['reason']) for r in c['rejections']))+'.' if c['rejections'] else '')+'</li>'
                       for c in assessment['checks'])
        calculations=''.join('<tr><td>'+text(calculation_label(r))+'</td><td>'+amount(r['value'])+'</td><td>'+text(r['status'])+'</td></tr>'
                             for r in company['calculations'])
        gate=assessment['quantitative_gate']
        cards.append(f'''<article data-gate="{escape(str(gate), quote=True)}">
<h2>{text(company['symbol'])} <small>CIK {text(company['issuer_id'])}</small></h2>
<p>Dönem: {text(company.get('period_start') or 'unresolved')} / {text(company.get('period_end') or 'unresolved')}.
Kabul edilen veri: {company['accepted_fact_count']}. Puan: hesaplanmadı.</p>
<p class="gate">Finansal inceleme: {text(gate)}</p><ul>{checks}</ul>
<p>Puanın hesaplanmama nedenleri: {text('; '.join(company['score_blockers']))}.</p>
<details><summary>Finansal hesaplamalar ve kaynak kanıtları</summary>
<div class="scroll"><table><thead><tr><th>Hesaplama</th><th>Değer</th><th>Durum</th></tr></thead><tbody>{calculations}</tbody></table></div>
<div class="scroll"><table><thead><tr><th>Alan</th><th>Değer</th><th>Muhasebe tanımı</th><th>Kaynak denemeleri</th><th>Kanıt</th></tr></thead><tbody>{''.join(fields)}</tbody></table></div>
</details></article>''')
    summary=report['summary']
    return f'''<!doctype html>
<html lang="tr"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'; script-src 'unsafe-inline'; base-uri 'none'; form-action 'none'">
<title>ABD Hisse Araştırması — araştırma prototipi</title>
<style>
body{{font:16px/1.5 system-ui,sans-serif;margin:auto;padding:24px;max-width:1100px;background:#f4f6f8;color:#172332}}
header,article{{background:white;border:1px solid #d8dfe6;border-radius:10px;padding:22px;margin-bottom:18px}}
h1,h2{{margin:0 0 12px}}h2 small{{font-size:14px;font-weight:400}}small{{display:block;overflow-wrap:anywhere}}
label{{display:inline-block;margin:8px 18px 8px 0}}input,select{{font:inherit;max-width:100%;padding:7px;border:1px solid #8797a8;border-radius:4px}}
.gate{{font-weight:600}}article[data-gate="critical_review_required"]{{border-left:5px solid #b63933}}
li{{margin:10px 0}}.scroll{{overflow:auto}}table{{border-collapse:collapse;width:100%;font-size:14px;margin:16px 0}}
td,th{{padding:9px;text-align:left;border-bottom:1px solid #d8dfe6;vertical-align:top}}summary{{cursor:pointer;font-weight:600}}
[hidden]{{display:none!important}}a{{color:#095ca5}}.notice{{background:#fff3d9;padding:12px;border-radius:4px}}
</style></head><body>
<header><h1>ABD Hisse Araştırması</h1><p>Araştırma prototipi · Kaynak verilerinin kesim zamanı: {text(report['as_of'])}</p>
<p>{summary['companies']} aday · {summary['accepted_facts']} kabul edilen veri · {summary['arithmetic_results']} hesaplama · {summary['scored_companies']} puanlanan şirket</p>
<p class="notice">İlk sürümün (MVP) kabulü bekleniyor. Kayıtlı veriler tarihli kaynak kanıtlarıdır; canlı fiyat hizmeti değildir. Bu kontroller ön eleme varsayımlarıdır.
Uyarı oluşmaması genel risk onayı anlamına gelmez. Kapsam, sektör veya değerleme kanıtları eksik şirketler sıralanmamıştır.</p>
<label>Sembol veya CIK ara <input id="search" type="search" placeholder="AAPL veya 0000320193"></label>
<label>Finansal inceleme <select id="gate"><option value="">Tüm adaylar</option><option value="critical_review_required">Kritik inceleme gerekiyor</option><option value="unresolved">Çözümlenmedi</option><option value="no_screen_trigger">Bu taramada uyarı oluşmadı</option><option value="invalid_evidence">Geçersiz kaynak kanıtı</option></select></label>
<p id="count" aria-live="polite">{summary['companies']} aday gösteriliyor</p></header>
<main>{''.join(cards)}</main><script>
const search=document.getElementById('search'),gate=document.getElementById('gate');
function filter(){{let count=0;const query=search.value.trim().toLowerCase();
for(const article of document.querySelectorAll('article')){{const match=article.querySelector('h2').textContent.toLowerCase().includes(query)&&(!gate.value||article.dataset.gate===gate.value);article.hidden=!match;if(match)count++;}}
document.getElementById('count').textContent=count+' aday gösteriliyor';}}
search.addEventListener('input',filter);gate.addEventListener('change',filter);
</script></body></html>'''
