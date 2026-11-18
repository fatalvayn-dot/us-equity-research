# Şirket keşfinde üst sınırların kaldırılması — 19 Kasım 2026

Şirket **keşfi** ve açık aday listesi kabulünde sabit 20 sayfa/20.000 kayıt, 100 aday ve 125 havuz sınırları kaldırıldı. Nasdaq screener tek bir HTTP isteğinde en çok 10.000 kayıt döndürmeye devam eder; bu sağlayıcı **sayfa** sınırıdır, toplam tarama sınırı değildir. Yazılım sayfaları özgün `totalrecords` tamamlanıncaya kadar ve hiçbir kayıt atlanmadan alır. Gerçek sağlayıcının sunduğu evren doğal olarak sonludur.

Önemli kontroller korunur:
- Her sayfada yanıt şeması, aynı toplam/snapshot zamanı, tekil sembol ve eksiksiz sayfalama kontrol edilir. Eksik veri **başarılı tarama** diye sunulmaz.
- Gerekli çalışma durumlarında isteğe bağlı `max_pages` ve `max_records` kontrolleri açıkça seçilebilir; varsayılanlar toplam şirket limitine dönüşmez.
- SEC/yahoo/diğer sağlayıcıların hız, erişim ve lisans kuralları; canlı çalışmadaki 501 dış GET bütçesi, tek çalışma kilidi ve devam kontrolü değişmedi.
- `common-sample` için `--sample-size 100` varsayılanı ve 100 şirketin kabul raporu **ayrı bir kalite sınavıdır**, küresel arama tavanı değildir. Büyük hedef sayı desteklenir, yeterli veri yoksa kabul edilmez.
- Gerçek yıllık finansal veri, katılım uygunluğu, piyasa fiyatı ve nihai puanlama her şirket için ayrıca doğrulanmalıdır. Keşfedilmiş şirket, puanlanmış şirket değildir.
- Ana dalda yeni keşif başlatılması veya mevcut 100 puanlama koşusunun başarı sayısı bu kod değişikliğiyle kendiliğinden artmaz.

Test kapsamı: 21 sayfa, 20.001 Nasdaq kaydı, 151 benzersiz MVP aday girdisi ve 130 benzersiz ortak örnek adayı. Sentetik veriler canlı piyasa başarısı sayılmaz.

Sonraki iş: açık arama evrenini kalıcı aday dosyalarına sayfalı artımlı biçimde aktarabilen ve kaynaktan gelmeyen şirketi eklemeyen, tekrarlarda kaldığı yerden devam eden ölçekleme iş akışı tasarlamak. Mevcut 100 şirketlik prototipin mali ve sektörel kalite kapıları kaldırılmayacaktır.
