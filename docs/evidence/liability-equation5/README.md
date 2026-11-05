# Beş şirket için SEC yükümlülük denklemi kanıtı

Bu kayıt, seçilmiş Nasdaq `Total Liabilities` değerini aynı dönem ve aynı ihraççıya
ait özgün yıllık SEC iXBRL bildirimiyle bağımsız olarak doğrular. SEC bildirimi
literal `us-gaap:Liabilities` olgusunu sunmadığında şu denklem kullanılır:

`LiabilitiesAndStockholdersEquity - total_equity = liabilities`

| Sembol | Dönem sonu | Doğrulanan yükümlülük (USD) | Ek kapsam kontrolü |
| --- | --- | ---: | --- |
| AMD | 2025-12-27 | 13,927,000,000 | Geçici/itfa edilebilir ve kontrol gücü olmayan pay yok |
| INTC | 2025-12-27 | 85,069,000,000 | Adi özkaynak + kontrol gücü olmayan pay = toplam özkaynak |
| ADI | 2025-11-01 | 14,176,957,000 | Geçici/itfa edilebilir ve kontrol gücü olmayan pay yok |
| CDNS | 2025-12-31 | 4,678,967,000 | Geçici/itfa edilebilir ve kontrol gücü olmayan pay yok |
| ADSK | 2026-01-31 | 9,422,000,000 | Geçici/itfa edilebilir ve kontrol gücü olmayan pay yok |

Kural, toplam bilanço eşitliği bozulursa, dönem/CIK/para birimi uyuşmazsa, geçici
veya itfa edilebilir özkaynak sıfırdan farklıysa ya da kontrol gücü olmayan payın
kapsamı çözülemiyorsa kanıtı reddeder. Denklem yeni bir veri kaynağı seçmez ve
yatırım uygunluğu onayı vermez; yalnız seçilmiş değerin özgün bildirimle tam
aritmetik mutabakatını gösterir.

Tekrar üretim:

```bash
PYTHONPATH=src python scripts/export_liability_equation_evidence.py
PYTHONPATH=src python scripts/build_current_scores.py \
  --financial docs/evidence/common-financial100/batch.json.gz \
  --current docs/evidence/common-comparative100/current-batch.json.gz \
  --prior docs/evidence/common-comparative100/prior-batch.json.gz \
  --sources tests/fixtures/valuation22-sources \
  --financial-sources tests/fixtures/liability-equation5-sources \
  --as-of 2026-11-03T05:36:21.308165+00:00 \
  --output docs/evidence/current-score100
PYTHONPATH=src python scripts/verify_scored_annuals.py
PYTHONPATH=src python scripts/verify_current_score_reproduction.py
```

Ham yanıtlar 2–3 Kasım 2026 tarihlerinde alınmıştır. Bu dışa aktarma ağ isteği
yapmaz; eski kayıtlı kanıtı yeniden oynatır. Güncel canlı 100 şirket kabulü değildir.
