# 3. Aşama — Yeni 100 ABD şirketi, önceki kohorttan tamamen farklı

Kullanıcı talimatı: 19 Kasım 2026'da eski 100 şirket listesi aktif
tarama listesinden kaldırılacak ve ABD borsalarında SEC kaydı bulunan
**tamamen farklı 100 ihraççı** seçilecek. Eski kanıtlı raporlar,
SHA-256 arşivleri ve Git geçmişi silinmeyecek.

## Ön filtre (yatırım onayı değil)

`scripts/select_new_us_100.py` resmî SEC şirket/borsa dizinini
`https://www.sec.gov/files/company_tickers_exchange.json`
üzerinden indirir. Gerçek SEC `submissions/CIK{CIK}.json`
kimliği, ticker, `entityType=operating`, SIC, tek ticker,
10-Q/10-K varlığı doğrulanır. Eski 100'ün CIK ve ticker'ı
ret edilir. Banka, sigorta, fon, gayrimenkul yatırım ortaklığı,
tütün, içki üretimi ve kumar faaliyet kodları/isimleri elenir.
İlk aday havuzu sağlık, teknoloji, sanayi, tüketim, enerji,
malzeme ve kamu hizmetleri sektörlerinin geniş öncelik sırasından
gelir. Başvuru finansal oranları katılım standardına göre henüz
onaylanmadığı için hiçbir şirket uygun sayılmaz.

Gerçek hisse sınıfı/fiilî işlem açıklığı ve güncel finansal
veri **SEC dizini ve SIC ile tek başına ispatlanmış olmaz**;
bu aşamaların canlı kaynak testleri ve model kapıları ayrıca
yapılır. Yeni listede kâğıt üstünde 100 aday olması
100/100 puanlama garantisi değildir.

## Kaynağa dayalı iki faz

1. Ayrı dalda seçici kodu, sentetik regresyon kontrolü ve
   resmî SEC kimlik işlemi için tek seferlik Actions.
   Daha sonra iş akışının resmî SEC kaynaklarıyla ürettiği
   100 sembol+CIK kimlikleri **aynı GitHub PR dalında**
   `docs/evidence/common100/candidates.json` yerine geçer.
   SEC kaynağı SHA-256/ret sebepleri Actions artifact'te kalır.
2. Liste PR ile birleştikten sonra, **eski devam arşivini
   kullanmayan** yeni canlı finansal toplama başlatılır.
   Eski kohortun SQLite/valuation geçmişi yeni şirket
   kanıtı olarak devralınmaz. Katılım ve yatırım kararları
   kapalı tutulur.

Başarı kriteri: 100 yeni SEC kimliği, 0 eski CIK/ticker,
bankacılık/sigorta/piyasadışı eleme ve resmî veri toplama
kanıtı. Başarı değildir: 100/100 katılım veya mali puan.
