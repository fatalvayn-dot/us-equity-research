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
