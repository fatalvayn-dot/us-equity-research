# Global Market Radar — kontrollü ilk pilot

Bu sürüm **tüm piyasaları taramaz** ve **yapay zekâ ile eğitilmiş tahmin modeli değildir**. Çalışan veri/toplama → basit referans sinyali → kaydedilmiş tahmin → 5 işlem günü sonrasında değerlendirme zinciridir. Yatırım tavsiyesi, katılım onayı, portföy işlem önerisi veya gerçek emir üretmez.

## Hazır açık kaynak veri adaptörü (21 Kasım 2026)
İlk fiyat kaynağı `ranaroussi/yfinance` (Apache-2.0, sabitlenen sürüm 1.8.0) artık `requirements/market-radar.txt` üzerinden kuruluyor; upstream kaynak kodunun tümü depoya kopyalanmadı. Günlük kapanış fiyatı sağlayıcısı sırası **yfinance → Yahoo Chart → Stooq (yalnız eşlemesi bilinen semboller)**. Her tahmin gerçek kaynak etiketiyle kaydedilir; başarısız kaynak sessizce sıfıra dönüştürülmez.

Yahoo'nun veri lisansı yfinance'ın Apache lisansından ayrıdır. Yahoo verisinin kullanım/yeniden dağıtım şartları ayrıca geçerlidir; sağlayıcı, araştırma/kişisel kullanım çerçevesinin dışına çıkarılmamalıdır. Kaynak: https://github.com/ranaroussi/yfinance ve https://pypi.org/project/yfinance/1.8.0/ .

ABD pilotuna ilaveten **ASELS.IS (BIST)** ve **SAP.DE (Avrupa)** araştırma örneği denenir; bunlar herhangi bir tam piyasa evreni veya katılım onayı değildir. Otomatik varlık kataloğu, gerçek emtia spot fiyatları, finansal tablo doğrulama ve makro/olay veri hattı henüz bu pilotun parçası değildir.

## Çalıştırma
- Çevrimdışı test: \`PYTHONPATH=.:src python -m unittest tests.test_market_radar_pilot -v\`
- Canlı veri denemesi: \`PYTHONPATH=.:src python scripts/market_radar_pilot.py\`
- GitHub: Actions > Market radar manual pilot > Run workflow.
- Sonuç: \`radar-pilot-report.json\` ve 7 günlük Actions artifact.

## Mevcut kapsam
yfinance / Yahoo Chart / Stooq yedeklemesi ile AAPL, MSFT, SPY, QQQ, emtia **ETF vekilleri** GLD, SLV, USO ve örnek BIST/Avrupa sembolleri ASELS.IS/SAP.DE denenir. GLD/SLV/USO spot altın/gümüş/petrol fiyatı değildir. Sağlayıcı erişilemiyorsa eksik veri açıkça raporlanır. BIST ve Avrupa'nın tam evrenleri, tüm hisse ve ETF evreni, haber akışı, bilanço, portföy, siyasi olay modellemesi ve model adaptasyonu bu sürümde tamamlanmış değildir. RSS girişi opsiyoneldir; başlık kategorilemesi öngörü modeline etki etmez.

## Ajana verilecek roller
- Müdür: tek ana görev, kanıt kapısı, maliyet, Türkçe rapor.
- Veri: kimlik/eşleme, lisans, tarih ve kaynak.
- Olay: haber/olayları olay zamanı ve kaynakla normalleştirme; gündem manipülasyonuna karşı doğrulama.
- Tahmin: olasılık kalibrasyonu, kıyas modeli ve dönem dışı test (henüz yok).
- Risk/katılım: banka/sigorta hariç; BIST XKTUM kuralı, Avrupa/ABD standardı ve ETF'lere ayrı doğrulama.
- Denetim: ileriye bakma sızıntısı, survivorship bias, işlem maliyeti ve canlı/fixture ayrımı.

## Sonraki uygulama sırası
1. Resmî BIST/XKTUM, Avrupa borsaları ve ABD listeleriyle tam varlık kimlik ve kapsam kataloğu; ETF sınıflandırması ayrı.
2. RSS/GDELT ve resmî açıklamalar için kaynaklı, tekrarsız, olay-zamanı takip hattı. API/lisans uygunluğu incelenecek.
3. Finansal veriler, SEC/KAP/ESEF, makro (FRED/ECB), emtia spot/vadeli kaynakları ve kur normalizasyonu.
4. Tahmin defterinin kalıcı depolanması; hedef zamanında sonuç eşleşmesi, Brier score/kalibrasyon, walk-forward ve kıyas.
5. Yalnız ölçülerek başarılı bulunan modellerin sürümlü yükseltilmesi; geçmiş model korunur, otomatik sınırsız öz-değişim yok.
6. Özel portföy gözlemi ve gerekçeli AL/TUT/AZALT/SAT/BEKLE değerlendirmesi, katılım ve kaynak kapıları sonrası; otomatik emir yok.

## Açık kaynak araştırma adayları
- Microsoft Qlib: https://github.com/microsoft/qlib
- FinGPT: https://github.com/AI4Finance-Foundation/FinGPT
- vectorbt: https://github.com/polakowo/vectorbt
- yfinance: https://github.com/ranaroussi/yfinance
Lisans, bakım durumu ve kaynak davranışı incelenmeden bu projelerden kod kopyalanmaz veya güvenilmeyen üçüncü taraf komutu çalıştırılmaz.

## Güvenlik
Varsayılan araçlar salt okunur, API anahtarları kayıtlara gitmez, hiçbir kişisel portföy verisi public GitHub'a yazılmaz. Eksik veri sıfır değildir. Bu iş akışı manuel başlar, main'e yalnız testler ve PR incelemesi sonrası aktarılır.
