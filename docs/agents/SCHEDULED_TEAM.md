# Zamanlanmış yatırım radarı — görevli ekip

## Başlatma ve süreklilik
\`.github/workflows/market-radar-agents.yml\` ana dala birleştiğinde GitHub Actions tarafından üç saatte bir tetiklenecek biçimde tasarlanmıştır (UTC 00:17, 03:17, 06:17, 09:17, 12:17, 15:17, 18:17 ve 21:17). GitHub cron çalıştırmaları gecikebilir veya atlanabilir. Workflow ayrıca manuel başlatılabilir. Bu, sürekli açık kalan bir sunucu değil, tekrar eden bağımsız iş oturumlarıdır.

## Görev devri
- **Müdür:** koşuyu yönetir, diğer işlevlerin durumlarını birleştirir.
- **Veri işçisi:** öncelikle Yahoo Chart, gerekirse Stooq üzerinden yedi varlığın günlük tarihli fiyatlarını almayı dener.
- **Tahmin işçisi:** 5/20 işlem günü momentum yön sinyalleri üretir; güven olasılığı hesaplamaz.
- **Haber işçisi:** isteğe bağlı \`MARKET_RSS_URL\` değişkeninden RSS başlıklarını kategoriler; fiyat sinyaline dahil etmez.
- **Geçmiş denetçisi:** beş işlem gününü dolduran geçmiş tahminleri değerlendirir.
- **Kalite denetçisi:** eski veya gelecekteki tarihleri, kuralsız alım önerisini ve kalitesiz veriyi reddeder.
- **Raporlama işçisi:** her koşu için Türkçe rapor ve JSON hazırlar.

Bu roller, ilk uygulamada deterministik Python işlevleridir. Henüz LLM tabanlı, kendi başına kod geliştirip öğrenen ajan oturumları çalışmamaktadır. Bunlar ayrıca devreye alınmalı ve test edilmelidir. Bu sınır, çalışmayan bir ücretsiz model API'sine bağımlı kalmamak içindir.

## Durum ve denetim
GitHub'da yalnız kamusal ve kişisel olmayan araştırma kayıtları için ayrılmış \`radar-ledger\` dalına, her koşudan sonra \`predictions.jsonl\`, \`evaluations.jsonl\`, \`latest.json\`, \`latest.md\` ve \`runs/<id>-<attempt>.json\` kaydedilir. Bir varlığın aynı veri tarihi için tahmini yeniden yazılmaz. Eski gerçekleşmeler değiştirilemez; yeni sonuç ayrı kayıt olur. Ayrıca 30 günlük GitHub Actions artifact üretilir.

Bir veri sağlayıcısı erişilemezse veya veri doğrulanmazsa bunu açıkça raporlar; sıfır sinyalli üretimi başarılı saymaz. Ana dala merge ve ilk canlı Actions koşusu henüz doğrulanmadan sistemin etkinleştiği iddia edilmez.

## Güvenlik ve kapsam
Otomatik emir, ücretli hizmet, portföy özel verisi, katılım uygunluğu onayı veya kaldıraçlı işlem yoktur. İlk kapsam yalnız yedi ABD hisse/ETF sembolüdür; GLD/SLV/USO spot emtia değildir. BIST, Avrupa ve küresel bütün varlıklar henüz entegre değildir. Yeni teknik araştırma için ayrı geliştirme ve bağımsız kabul kapıları uygulanır.
