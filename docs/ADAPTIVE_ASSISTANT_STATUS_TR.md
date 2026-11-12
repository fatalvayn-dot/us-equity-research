# Adaptif Yatırım Uzmanı: Çalışan bileşenler ve kabul koşulları

## Aktif kod parçaları

- `scripts/adaptive_daily_brief.py` — ABD, BIST ve Avrupa'daki **örnek kamusal** 23 örnek hissenin tarihli fiyat kanıtını toplar.
- `scripts/adaptive_investment_assistant.py` — fiyatların güvenilirliğini kontrol eder, önemli günlük hareketleri ve kaynak sorunlarını araştırma kuyruğuna alır; `research-packet.json` ve `analyst-work-order.md` üretir.
- `.github/workflows/adaptive-analyst-daily.yml` — hafta içi 14:15 UTC'de fiyat ve araştırma iş emri artifact'lerini üretmeyi dener.
- `scripts/investment_decision_log.py` — **yalnızca yerel/özel dosyaya** zamanlı karar ve daha sonra sonuç kaydı ekler; her satır öncekinin SHA-256 değerine zincirlenir. İşlem açmaz.
- `docs/ADAPTIVE_ANALYST_TR.md` — araştırmacı için ilk kullanım sözleşmesi.

## Sınırlar: henüz hazır olmayanlar

- GitHub'ın oluşturduğu iş emri GPT Work oturumunu **otomatik başlatmaz**. Work'te bağlantı ve günlük zamanlama ayrıca yapılandırılmalı, gerçek oturumla doğrulanmalıdır.
- Portföyün son gerçek adet ve alış maliyetleri otomatik bağlı değildir. Midas hesabına otomatik erişim yoktur.
- Kapsam üç piyasada **23 sembollük örnek**; bütün Midas evreni, tam katılım endeksi denetimi, temel değerleme ve finansal sağlık için geniş tarama henüz entegre değildir.
- Günlük fiyat değişimi bir yatırım önerisi veya otomatik piyasa yönü tahmini değildir. Yapay zekâ güncel haber ve makro koşulları ayrıca araştırmalıdır.
- Kendi kendine öğrenme, bu aşamada **denetlenebilir karar/sonuç günlüğü** demektir. Performans karşılaştırması ve kanıtlı strateji değişikliği ayrıca inşa edilmelidir.
- Public depoya **asla** müşteri adı, portföy miktarı, alış maliyeti, bakiye, işlem geçmişi, broker şifresi veya özel görüş kaydı koyma.

## Günlük akış

1. GitHub Actions çalışma özeti ve artifact'teki `research-packet.json` indirilir.
2. `analyst-work-order.md` GPT Work veya sohbet asistanına verilir.
3. Asistan piyasaları ayrı analiz eder; belirsiz verileri açıkça gösterir.
4. Özel portföy kaydı (kullanıcı tarafından doğrulandıysa) piyasa ve sektörel risklerle karşılaştırılır.
5. Yalnızca kaynaklı, işlem maliyetli ve karşıt senaryolu öneri hazırlanır; kullanıcı onayı olmadan işlem yapılmaz.
6. Öneri `scripts/investment_decision_log.py` ile kamu deposunun **dışında** kalıcı tutulur.
7. Zamanı geldiğinde kanıtlı gerçekleşme gözlemi eklenir; otomatik model değişikliği yapılmaz.

## Çalıştırma ve doğrulama

```bash
python scripts/adaptive_daily_brief.py
python scripts/adaptive_investment_assistant.py
python -m unittest tests.test_adaptive_daily_brief tests.test_adaptive_investment_assistant tests.test_investment_decision_log -v
```

Bu belge tamamlanmış ürün kabulü değil, çalıştırılabilir parçaların ve eksiklerin dürüst envanteridir.
