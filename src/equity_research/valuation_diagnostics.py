"""Presentation of observed valuation blockers, never a collection or approval."""
from .turkish import label

STAGES={
    'source_inventory':'Kaynak dosyaları', 'financial_batch':'Finansal girdi',
    'price':'Fiyat ve fiyat tazeliği', 'disclosed_shares':'Bildirilen hisse adedi',
    'original_share_filing':'Özgün hisse bildirimi', 'share_class':'Hisse sınıfı ve adet eşleşmesi',
    'share_price_chronology':'Fiyat ve bildirim tarihleri',
    'financial_period_currency':'Finansal dönem ve para birimi',
    'sec_financial_confirmation':'SEC finansal değer teyidi',
}

def diagnostic_lines(diagnostic):
    if not diagnostic:return []
    lines=[]
    if diagnostic.get('failed_validation_stage'):
        stage=diagnostic['failed_validation_stage']
        lines.append('Değerleme kontrolü: '+STAGES.get(stage,stage)+'.')
    for url in diagnostic.get('missing_source_urls',[]):
        lines.append('Eksik kaynak: '+('Özgün hisse adedi bildirimi' if url=='exact_original_share_filing' else url)+'.')
    for item in diagnostic.get('missing_evidence',[]):
        lines.append('Eksik kanıt: '+STAGES.get(item,label(item))+'.')
    for key in ('provider_status','failure_detail'):
        if diagnostic.get(key):lines.append('Kontrol sonucu: '+label(diagnostic[key])+'.')
    for source in diagnostic.get('source_observations',[]):
        lines.append('Gözlenen kaynak: '+source['url']+'; tarih: '+source['retrieved_at']+'; SHA-256: '+source['raw_sha256']+'.')
    return lines
