# Küçük ölçekli ABD fiyat gözlem denemesi — 21 Kasım 2026

## Deneme kapsamı
İlk ana dal pilotundaki dokuz sembol (AAPL, MSFT, SPY, QQQ, GLD, SLV, USO, ASELS.IS, SAP.DE) korunur. Yeni tarama yalnız ABD'den NVDA, AVGO, AMZN, GOOGL ve META sembollerini ekler. Toplam 14 benzersiz günlük fiyat gözlemi denenir; bu sayı veri başarı garantisi veya yatırım tavsiyesi değildir.

Kaynak dosyası `data/analyst/radar_small_us_trial.json`, mevcut `data/analyst/public_research_universe.json` listesinden seçilmiş kamuya açık beş araştırma sembolünü taşır. Orijinal tam liste değiştirilmedi. Araç giriş SHA-256 değerini çıktı manifestine kaydeder. Yazılım beşten fazla ek sembolü veya toplam 14'ten fazlasını reddeder.

## Kabul kapısı
1. PR içinde ağsız testler ve Yahoo/yfinance fallback kontrolleri başarılı olmalı.
2. Gerçek GitHub Actions'da 14 sembol istenmeli; kaçından kapanış verisi geldiği açıkça raporlanmalı.
3. Python 3.11, 3.12, 3.13 temel testleri tamamlanmalı.
4. İlk ana dal çalışması dokuz eski tahmini korumalı ve aynı veri tarihi için tekrar kayıt üretmemeli.
5. Herhangi bir veri eksikliği varsa gerçek durum açıkça yazılmalı; kaynak erişilememesi sıfır fiyat sayılamaz.

Bu geçici fiyat gözlemidir. Resmî bütün ABD, BIST veya Avrupa hisse kataloğu değildir. Banka ve sigorta, katılım uygunluğu ve aktif borsa üyeliği ayrıca doğrulanmadıkça yatırım önerisi üretilemez. BIST yatırım uygunluğu için yalnız resmî XKTUM üyeliği ölçütü, Avrupa ve ABD için ayrıca doğrulanmış ilgili standart uygulanacak. Gerçek alım-satım, özel portföy ve ücretli kaynak yoktur.
