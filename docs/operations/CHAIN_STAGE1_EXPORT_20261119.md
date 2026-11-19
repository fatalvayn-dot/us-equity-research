# Zincirleme görev #135 — SEC/MotherDuck hazırlık katmanı (19 Kasım 2026)

## Veri akışı ve güvenlik

1. Firecrawl Alexandria SEC companyconcept JSON kaydı, kullanıcı denetimindeki **yerel** dosyaya kaydedilir; GitHub deposuna ham veri veya API anahtarı yazılmaz.
2. SEC kavramları ve dosya/dönem/şirket kimliği, daha önce kabul edilmiş salt okunur SEC denetçisiyle kontrol edilir.
3. Farklı değer taşıyan aynı gözlem, uyumsuz URL, yanlış accession, kayıp dönem, birim veya MotherDuck DECIMAL(38,6) hassasiyetinin dışındaki sayı hata üretir.
4. Yalnızca `exact_concept_candidate_unverified` durumunda CSV hazırlanır ve SHA-256 manifesti oluşturulur.
5. **MotherDuck'a otomatik yazılmaz.** Yetkilendirilmiş aktarım adımı olmadan SEC source hash yoktur; `source_verified` durumu verilmez. Radar puanlaması/Yahoo->SEC->Nasdaq->Finnhub önceliği aynı kalır.

Komut (repo kökünden):

```bash
python -m scripts.export_sec_evidence_staging \
  --input /guvenli/yerel/alinan_alexandria.json \
  --csv /guvenli/yerel/sec_evidence_staging.csv \
  --manifest /guvenli/yerel/sec_evidence_manifest.json
```

`my_db.main.sec_evidence_staging` tablosu 19 Kasım'da oluşturulup sütunları doğrulandı. Hiçbir özel portföy alanı bu şemaya dâhil edilmez. Aktarım/INSERT veri değişikliği için açık onay ve tekrar-gözlem/çakışma politikası gereklidir.

**Kabul durumu:** Bu değişiklik ağsız test kontratını güvence altına alır. Gerçek MotherDuck'a veri yüklemesi, 2–3 farklı şirket için özgün SEC kaynak gövdesi/hashi ve son canlı 100 şirketlik puanlamanın başarısı henüz gösterilmiş sayılmaz.

Sonraki iş: belge/dönem kanıtını özgün SEC kaynak gövdesiyle ilişkilendirmek, kontrollü veri yüklemesi ve tekrar taramayı gerçek verilerle sınamak. Kullanıcının bankacılık/sigorta dışlama, katılım filtresi ve emir otomasyonu yasağı korunur.
