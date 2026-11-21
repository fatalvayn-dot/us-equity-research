# Değerleme kaynaklarını önceki çalışmadan kullanma

Finansal toplama paketindeki doğrulanmış kamu kaynakları, değerleme toplayıcısına
`--seed-bundle` ile verilebilir. Girdi dizini çalışma dizininden ayrı olmalıdır.
Paket parça ve gövde özetleri denetlenir; kaynak URL, SHA-256 ve özgün gözlem tarihi
korunur. Bu işlem yeni ağ gözlemi veya yatırım kabulü değildir.

```bash
PYTHONPATH=src python -m equity_research collect-valuation-sources \
  --candidates docs/evidence/common100/candidates.json \
  --state-dir data/valuation-current \
  --seed-bundle data/latest-evidence/live-sources \
  --user-agent "$SEC_USER_AGENT" \
  --max-new-requests 501
```

`data/latest-evidence/live-sources` yerine indirilen ve doğrulanan son kanıt
paketinin gerçek dizini kullanılır. Komut en fazla 100 aday için 501 yeni GET
çağrısına izin verir; ulaşılabilir her verinin bulunacağını garanti etmez.
Yeni çağrı yapmadan yalnız mevcut kaynakları sınamak için sınır `0` verilir.
Birden fazla paket için `--seed-bundle` tekrarlanabilir.

Altı saatten eski veya gelecekte tarihli gözlemler başlangıç arşivine alınmaz.
16 MB üstü gövdeler reddedilir. İçeri alınan bir gözlem ayrıca kendi aşamasının
kurallarından geçer: fiyat ve piyasa geçmişinde 15 dakika sınırı, fiyat zamanı,
kimlik ve hisse sınıfı kontrolleri aynen uygulanır. Örneğin 16 dakikalık bir
fiyat gövdesi arşive girse bile güncel fiyat olarak kullanılamaz.

`report.json` içindeki `seed_summary` içeri alınan, eski/gelecek tarihli ve fazla
büyük gözlemleri ayrı sayar. Bu sayaç doğrulanmış şirket veya puan sayısı değildir.
Eksik kaynaklar mevcut istek bütçesiyle tamamlanır; bütçe bittiğinde ilgili aşama
beklemede kalır. Finansal veri sırası, model kabulü ve puanlama kuralları değişmez.
