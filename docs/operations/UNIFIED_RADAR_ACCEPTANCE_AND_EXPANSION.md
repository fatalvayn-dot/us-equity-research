# Birleşik Adaptif Yatırım Uzmanı — aşama ve iş akışı kayıtları

Tarih: 2026-11-22. Bu belge doğrulanmış AAPL çalışmalarını diğer piyasalara
açılmış gibi göstermez.

## AAPL kabul sözleşmesi

Tek bir `unified-aapl-full-pipeline.json` kanıt paketi, aynı çalışmanın
`unified-aapl-llm-readiness.json` beş ajan yanıtı ile
`unified-aapl-acceptance.py` tarafından değerlendirilir. Hatalı/eksik
LLM dosyası başarı sayılmaz. Sonuçlar hem makineye okunabilir JSON hem
Türkçe Markdown halinde ve aynı GitHub Actions artefaktında bulunur.

- **Tamamlanan operasyonel kapılar:** AAPL kimliği ve günlük piyasa
  serisi; SEC şirket finansalları; hisse sınıfı, fiyat ve fiyat geçmişi;
  mevcut karşılaştırmalı puanlama; haber başlık gözlemi; gerçek,
  `openrouter/free` beş ajan yürütmesi
- **Henüz tamamlanmamış kabul:** AAPL için tarihli, asıl belge
  SHA doğrulamalı katılım mali oranları ve standart sürümü; tahminin
  bağımsız gelecek veride kıyas modeline üstünlüğü; haber-olay
  etkisini doğrulayan tarihli nedensellik testleri
- **Üçüncü sonuç kategorisi:** Araştırma hattı çalışıyor, fakat tüm
  zorunlu kabuller tamamlanmadı. `investment_approved=false` ve
  `eligible_for_trade=false` değişmez

Bu rapor karar veren tek mühendislere yol göstermek içindir. LLM
yorumları kaynak ve sayısal kabul kapılarını geçersiz kılamaz.

## İş akışı çakışmaları ve devreden çıkarma sırası

| İş akışı | Doğrulanmış görev | Yapılacak işlem |
|---|---|---|
| `unified-single-issuer-proof.yml` | AAPL tek run finansal, kaynak, skor, LLM, kabul artefaktı | AAPL için **kanonik test**; zorunlu kabul kanıtını sakla |
| `llm-team.yml` | Ayrı, AAPL yalnız fiyat verisiyle ikinci beş ajan smoke | Kanonik akış tüm LLM alanlarını geçirince yalnız isteğe bağlı bağlantı teşhisinde tut; ayrı otomatik yürütmeyi kaldırmayı değerlendir |
| `market-radar-pilot.yml` | 9/14 sembollü elle tetiklenen fiyat adapter denemesi | Global fiyat kaynak testi; AAPL finansal analizinin yerine geçmez |
| `market-radar-agents.yml` | 3 saatte bir zamanlanmış kamu tahmin defteri; `radar-ledger` dalına append-only kayıt | Defter geri alınıp eski/yeni tahminler karşılaştırılmadan **silme / durdurma** |
| `adaptive-analyst-daily.yml` | Üç piyasanın günlük araştırma özeti | Kanonik kabul çıktılarını okuyana kadar çalışması ve yenileme sıklığı ayrı doğrulanmalı |
| `first-live-score.yml` | Kaynak artefaktlarını bağlayan 100 şirket skoru | Çoklu şirket genişlemesinden önce aynı veri şemasına bağla; artık iş mantığına alternatif yazma |
| `valuation-live.yml` ve `live-acceptance.yml` | Şirket bazlı değerleme, SEC kaynakları | Tarihli, doğrulanabilir SEC arşivleri korunmalı |
| Diğer dokuz iş akışı | Finansal talep, SEC aşama doğrulaması, gap, Finnhub ve kohort testleri | Girdi/çıktı, sıklık ve defter bağımlılıklarını topluca denetlemeden kaldırma |

## Kademeli genişleme için şartlar

1. **AAPL: 1 şirket.** Bütün aşamaların JSON kararları; eksik
   kaynak için fail-closed davranış; puan ve model benchmark doğrulanmalı.
2. **ABD: 5 → 25 → 100 şirket.** Aynı modüller şirket kimliğine göre
   parametreleştirilmeli. SEC CIK ve hisse sınıfı birebir eşlenmeden
   kayıt eklenmez. Sembol, ETF ve şirket evrenleri ayrılır.
3. **BIST: 5 → 25 → BIST aktif evreni.** Şirket katılım
   kapısı **yalnız tarihli resmî XKTUM üyeliğidir**.
   KAP finansalları SEC olarak gösterilmez.
4. **Avrupa: 5 → 25 → uygun aktif evren.** Borsa, MIC/ISIN,
   para birimi ve ilgili tarihli katılım standardı ayrı kanıtlanır.
5. **ETF/emtia ve piyasa haberleri.** Hisse ile aynı bilançoyu
   kullanma. Altın, gümüş, petrol, navlun ve makro göstergeler için
   ayrı varlık sınıfı şeması ve veri kaynağı şeffaflığı gerekir.
6. **Kıyas ve adaptif öğrenme.** En az iki bağımsız geçmiş rejim,
   yürüyen doğrulama, naif benchmark, işlem maliyeti, veri zaman
   sızıntısı ve bir sonraki gerçek dönem tahmin defteri kabulü olmadan
   gelişen uzman iddiasında bulunma.

Çalışma sürekliliği iş akışlarının açık olduğu varsayımıyla değil,
gerçek son çalışma zamanı, sonuç kodu ve çıktı artefaktıyla ölçülmelidir.
Ücretli LLM yönlendirmesi, kaldıraç, opsiyon ve gerçek alım otomasyonu yok.
