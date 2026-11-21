# LLM ajan ekibi — izin gerektiren araştırma pilotu

Bu modül dört ayrı LLM rolünü **beş sıralı çağrı** halinde bağlar: müdür planı → veri araştırmacısı → geliştirici önerisi → bağımsız denetçi → müdür raporu. Ajanların kod değiştirme, GitHub'a commit atma, internette araştırma yapma, hesap/portföy erişimi veya işlem yapma araçları **yoktur**. Verilen doğrulanmış radar verileriyle çalışırlar. Ayrı model oturumlarıdır; bağımsız süreçler veya kendi kendini eğiten ajanlar değildir.

## Çalıştırma
- Çevrimdışı birim testi: `PYTHONPATH=.:src python -m unittest tests.test_llm_team -v`
- GitHub Actions: `LLM manager team (opt-in)` iş akışı; PR'da **yalnız çevrimdışı test** çalışır.
- Gerçek API kullanımı ayrı yetkilendirme gerektirir: `OPENAI_API_KEY` secret, `RADAR_LLM_APPROVED=true` variable ve geçerli `radar-input/latest.json` dosyası. İş akışı rapor dosyası mevcut değilse hata verir; dış veriyi kendiliğinden bulmaz. **Ücretli API hizmeti kullanıcı onayı olmadan açılmaz.**
- En fazla 5 çağrı, 450 token üst sınırı / çağrı; gerçek ücret sağlayıcıya göre değişir. Ortamda yanlış veya eksik yapılandırma varsa ücretli çağrı yapılmaz.
- Sadece özet, kaynak adı, sembol, tarih ve sinyal durumları gönderilir; özel portföy, API anahtarları, ham haberler ve kaynak URL'leri gönderilmez.

## Sonraki adım
Gerçek kaynak kanıtını güvenli şekilde iş akışına aktaran, şema ve tazelik kontrolleri bulunan bir adım hazırlanmalı; ardından onaylı API ile gerçek LLM çağrısı test edilmelidir. Mevcut üç saatlik radar akışı değiştirilmedi. Model önerileri yatırım tavsiyesi veya doğrulanmış araştırma değildir; insan incelemesi gerekir.
