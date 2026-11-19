# 7. aşama — Türkçe karar destek raporu (19.11.2026)

## Ayrım ve güvenlik

Mevcut `scoring.py`, `score_html.py` ve Türkçe rapor üreticisi
değiştirilmedi. 7. aşama, **önceden hesaplanmış, tarihli** araştırma
puanlarının üzerine yeni bir salt-okunur görünüm getirir:

- Finansal: finansal sağlamlık, büyüme, kârlılık ve nakit akışı ayrı.
- Değerleme: kaynak puanı, aynı referans tarihini koruyarak ayrı.
- Risk: kayıttaki risk bileşeni ayrı; nitel risk onaylanmış sayılmaz.
- Katılım: #140'ın `uygunsuz` / `bilinmiyor` / `kosullu_esik_gecisi`
  araştırma durumları ayrı. Koşullu geçiş **sertifika değildir**,
  alım için yeterli değildir. Ek veri yoksa `bilinmiyor`.
- Karar: AL / TUT / AZALT / SAT / BEKLE uzman için sözlüktür;
  **otomatik karar verilmez**. Hisse tutma bilgisi olmadan TUT/SAT
  özellikle üretilmez.
- Maliyet ve EUR: kaynaklı komisyon, döviz kuru, gerçekleşmiş getiri
  ve kıyas endeksi yoksa **bilinmiyor**, sıfır varsayılmaz.

`src/equity_research/decision_report.py` finansal puanları
yeniden hesaplamaz. Toplamı alt bileşenlerin toplamıyla doğrular;
eksik bileşen veya şirket listesi sayısı çelişirse hata verir.
Puansız şirkete sıfır verilmez, engel açıklamaları ve özgün
kaynak URL / SHA-256 referansları korunur.
Yatırım onayı ve otomatik emir her zaman `false` kalır.

## Yeniden üretme

```bash
PYTHONPATH=src python scripts/export_decision_report.py \
  --score-report docs/evidence/current-score100/report.json.gz \
  --output /tmp/karar-destek.md
```

**Örnek dosya geçmiş rapordur**, canlı piyasa kesimi değildir.
Kaynağın kimliği, tarihi ve SHA-256 özeti ayrı çıktı makbuzuna
yazılır. İsteğe bağlı `--participation` Stage-6 araştırma
çıktı listesi ile birleştirir; SEC kimliği/tarih ve sertifika
olmama kapısı yine zorunludur.

## Kanıt ve kalan kabul koşulları

`tests/test_decision_report.py` hem sentetik durumları
hem depodaki eski 100 aday raporunu salt okunur test eder.
Bu test, bugün gerçekten 100 şirketin puanlandığını göstermez.
19 Kasım'da en son doğrulanmış skor 23/100 idi; yeni 100 şirket
finansal kaynak çalışması 44526775886 başarılı oldu, fakat
puanlama/katılım nihai kabulü henüz doğrulanmadı.
Kapsamlı Türkçe AL/TUT/AZALT/SAT/BEKLE gerekçelerini gerçek
piyasa ve portföy verileriyle üretmek, geleceğe dönük risk
hesaplamak ve resmî katılım uyumunu teyit etmek **tamamlanmadı**.

#135–#140 kabul koşulları açık; #141 üretim kabulü kapatılamaz.
Sonraki tek iş: taze değerleme/puanlama kanıtları ve
gerçek şirketlerin katılım kaynaklarını eşleştirip,
belirsizliği çözümlenen şirketlerde uzman onaylı karar akışını
özel kayıt sistemiyle birleştirmek (gerçek emir yok).
