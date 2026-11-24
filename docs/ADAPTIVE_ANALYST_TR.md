# Adaptif Yatırım Uzmanı — ilk veri aktarım sözleşmesi

Bu küçük bileşen, mevcut 100-şirket araştırma zincirini değiştirmeden ayrı çalışır.
GitHub veriyi toplar; karar verici yapay zekâ ise **kanıtı yorumlar**.

## Çalışma

`python scripts/adaptive_daily_brief.py`

Her iş gününde GitHub Actions çalışmayı dener, JSON ve Türkçe Markdown dosyalarını
`adaptive-analyst-daily-evidence` adıyla **Actions artifact** olarak kaydeder.
İki dosya da kişisel portföy pozisyonu, nakit veya işlem geçmişi içermez.
Hisse listesi `data/analyst/public_research_universe.json` içindedir.
Bu liste yalnızca kamusal araştırma örneklemidir; Midas'ta işlem erişimi veya
katılım uygunluğu doğrulanmış liste **değildir**.

Her sembolde son düzenli seans fiyatı, kaynağı, zaman damgası, sağlayıcı para
birimi ve mümkünse önceki kapanışa göre değişim yer alır. Kaynak erişimi başarısız
olduğunda fiyat `null` kalır. Fiyatın dört günden eski olması ayrıca işaretlenir.
Mutlak günlük değişim %3'e ulaşırsa araştırma önceliği tetiklenir; bu bir
alım/satım sinyali değildir. Başka tür olayların (bilançolar, haberler, riskler)
izlenmesi henüz otomatikleştirilmedi.

## GPT Work için kullanım

1. En son başarılı `Adaptif yatırım uzmanı veri özeti` koşusundaki artifact'i aç.
2. JSON kanıtının `created_at`, `market_at`, kaynak durumlarını kontrol et.
3. `source_unavailable` ve eski veriler için fiyat tahmini üretme.
4. Araştırma gerektiren sembollerde kaynaklı ve tarihli analiz yap.
5. AL/TUT/AZALT/SAT/BEKLE görüşünü yalnızca fiyat hareketinden çıkartma.
6. Katılım uygunluğu belirsizse uygunluk onayı verme.
7. Kişisel portföy ağırlıklarını yalnızca kullanıcıya ait özel bir kaynaktan al;
   herkese açık GitHub deposuna yazma.

Bu iş akışı **GPT Work'ü kendiliğinden başlatmaz**; Work günlük oturumu ve
gerekli GitHub bağlantısı ayrıca kurularak test edilmelidir. Bu bileşen
yapay zekâ yorumu, yatırım puanı, temettü, portföy optimizasyonu, emir,
katılım onayı veya kendi kendini eğiten model üretmez.

## Doğrulama

`python -m unittest tests.test_adaptive_daily_brief -v`

Testler ağsızdır. Canlı piyasa verisi doğruluğu ayrıca izlenmelidir.

## Tavsiye defteri ve sonuç doğrulaması

`data/analyst/advice_ledger.jsonl` yalnızca eklenen, hash zincirli kayıtlardır (geçmiş tavsiye sessizce değiştirilemez; `verify` bozulmayı yakalar).
Kayıt türleri: `advice` (görüş, referans fiyat ve tarihi, kıyas endeksi, ufuk, gerekçe, kanıt referansı, geçersiz kılma koşulu), `outcome` (ufuk dolunca ölçüm), `review` (hata sınıfı).

Kurallar:
- `AL` katılım uygunluğu bağımsız doğrulanmadan yazılamaz. Kayıt emir değildir (`investment_order=false`).
- Fiyat gözlemi 4 günden eski veya gelecekte olamaz; ufuk dolmadan ve ufuk + 7 günden sonra sonuç ölçülmez (`gozlem_yok`).
- Sonuç kıyas endeksine göre değerlendirilir (aşırı getiri). ±1 puan bandı `belirsiz`; `TUT/BEKLE` ölçülmez.
- Her `yanlis` sonuç hata sınıfıyla işaretlenir: `veri`, `model`, `haber_yorumu`, `sans_belirsizlik`. `dogru` yalnızca doğru sonuca verilir.
- Kalibrasyon raporu 25'ten az karara bağlanmış örnekte başarı oranı vermez (`yetersiz_ornek`); yeterli örnekte Wilson %95 aralığı verir ve yine avantaj kanıtı değildir.

Komutlar: `python scripts/advice_ledger.py add|evaluate|review|report|verify`.
Model veya eşik değişikliği yalnızca bu defterdeki hata sınıflarına dayanıp walk-forward testten geçince PR ile gelir.
