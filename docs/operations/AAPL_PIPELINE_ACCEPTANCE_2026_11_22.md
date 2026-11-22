# AAPL uçtan uca araştırma kabul kaydı — 22.11.2026

Özgün GitHub Actions kanıtı:
- [Tam finansal/puanlama, geçmiş test ve LLM yapılandırma çıktısı](https://github.com/fatalvayn-dot/us-equity-research/actions/runs/45017446020)
- [Tahmin üstünlüğü olmayan modelin kapatıldığı sonraki sürüm denemesi](https://github.com/fatalvayn-dot/us-equity-research/pull/168)

| Aşama | Kanıtlı sonuç | Kabul veya açık engel |
|---|---|---|
| Resmî SEC kimlik | AAPL / CIK 0000320193 | Geçti |
| Piyasa kapanışları | yfinance günlük, kaynak atıflı | Geçti; anlık spot iddiası yok |
| Finansal SEC | 11 kabul edilen veri alanı, 8 hesaplama | Kaynak arşivi mevcut; şirketçe nitel inceleme ayrı |
| Hisse sınıfı/değerleme kaynağı | Kimlik, hisse sınıfı, fiyat ve tarihsel seri: 4/4 | Geçti |
| Karşılaştırmalı dönem | 1/1 şirket, 0 kaynak engeli | Geçti |
| Araştırma skoru | 67,5 / 100; operating-sector-research-batch-v2 | Puanlandı, alım onayı değil |
| Geçmiş 5 seans yön testi | 143 yön tahmini; %53,15 isabet; hep-yukarı %58,74 | **Tahmin üretim yetkisi kapalı** |
| Katılım ekranı | AAPL 20.11.2026 SPUS fon portföyünde gözlendi | Orijinal mali oran/standart kanıtı eksik, onay yok |
| Haber ve olay tahmini | Genel RSS altyapısı var; AAPL tarihli haber-etki modeli bağlı değil | Bloke |
| Gerçek LLM | RADAR_FREE_LLM_ENABLED ve OPENROUTER_API_KEY ortamda yok | 5 rollü mock test var; gerçek API testi yok |
| Gerçek alım / portföy | Kapalı | Kaldıraç, emir, özel portföy entegrasyonu yok |

## Eylem sırası

1. **Katılım:** Tarihi/sürümü belirlenmiş ABD endeks metodunu ve özgün SEC beyanlarını
   doğrulayarak faizli borç, faizli nakit/menkul kıymet, uygunsuz faaliyet geliri için
   eksiksiz pay/payda hesaplarını üret. SPUS holdings gözlemi bağımsız uygunluk sertifikası
   yerine geçmez; `bilinmiyor` yeni alım için engeldir.
2. **LLM:** Repo Actions Secrets içinde `OPENROUTER_API_KEY`, Variables altında
   `RADAR_FREE_LLM_ENABLED=true` kullanıcı tarafından kurulmalı. Yoksa gerçek API
   sınaması başarı raporlamamalı. Ücretli model, kart veya ücretli yedekleme yok.
3. **Tahmin:** Aynı örneklemde naif kıyası geçemediği için 5/20 momentumun AL/SAT
   yön iddiasını üretimden uzak tut. Günlük tarihli ileriye dönük tahmin defteri,
   5/20/60 seans gerçekleşme ölçümü, örtüşmeyen kontrol dilimleri ve işlem maliyetleriyle
   walk-forward doğrulaması yapılmadan adaptif öğrenme iddia etme.
4. **Haber:** Kaynak tarihli olay kanıtı, etkilenme olasılığı ile haberin gerçekleşme
   zamanını sakla; geçmiş olay sonuçlarına bakıp geçmişe tahmin yazma.
5. **Evrensel genişleme:** AAPL'de bütün zorunlu kapılar geçmeden diğer piyasalara
   alım onayı yayma. Önceki workflow'lar ancak kimlik/artefakt sürekliliği
   doğrulanırsa devre dışı bırakılabilir.

Bu dosya araştırma durumudur; yatırım önerisi, pozisyon talimatı veya
katılım sertifikası değildir.
