# LLM ajan ekibi — izin gerektiren araştırma pilotu

Bu modül dört ayrı LLM rolünü **beş sıralı çağrı** halinde bağlar: müdür planı → veri araştırmacısı → geliştirici önerisi → bağımsız denetçi → müdür raporu. Ajanların kod değiştirme, GitHub'a commit atma, internette araştırma yapma, hesap/portföy erişimi veya işlem yapma araçları **yoktur**. Verilen doğrulanmış radar verileriyle çalışırlar. Ayrı model oturumlarıdır; bağımsız süreçler veya kendi kendini eğiten ajanlar değildir.

## Çalıştırma
- Çevrimdışı birim testi: `PYTHONPATH=.:src python -m unittest tests.test_llm_team -v`
- GitHub Actions: `LLM manager team (opt-in)` iş akışı; PR'da **yalnız çevrimdışı test** çalışır.
- Gerçek API kullanımı ayrı yetkilendirme gerektirir: `OPENROUTER_API_KEY` secret, `RADAR_FREE_LLM_ENABLED=true` variable ve geçerli `radar-input/latest.json` dosyası. İş akışı rapor dosyası mevcut değilse hata verir; dış veriyi kendiliğinden bulmaz. **Ücretli API hizmeti kullanıcı onayı olmadan açılmaz.**
- En fazla 5 çağrı, 450 token üst sınırı / çağrı; gerçek ücret sağlayıcıya göre değişir. Ortamda yanlış veya eksik yapılandırma varsa ücretli çağrı yapılmaz.
- Sadece özet, kaynak adı, sembol, tarih ve sinyal durumları gönderilir; özel portföy, API anahtarları, ham haberler ve kaynak URL'leri gönderilmez.

## Sonraki adım
Gerçek kaynak kanıtını güvenli şekilde iş akışına aktaran, şema ve tazelik kontrolleri bulunan bir adım hazırlanmalı; ardından onaylı API ile gerçek LLM çağrısı test edilmelidir. Mevcut üç saatlik radar akışı değiştirilmedi. Model önerileri yatırım tavsiyesi veya doğrulanmış araştırma değildir; insan incelemesi gerekir.

## Ücretsiz sağlayıcı kararı — 21 Kasım 2026
- Seçim: OpenRouter ücretsiz model yönlendiricisi, sabit model kimliği `openrouter/free` ve sabit uç nokta `https://openrouter.ai/api/v1/chat/completions`.
- Ücretli modele geçiş veya model adıyla fiyatlı rotaya yönlendirme **kodda engellendi**; `RADAR_LLM_MODEL` değişkeni dikkate alınmaz.
- İlk pilot için en fazla 5 model çağrısı; ücretsiz kota dolarsa hata ve görev durması, ücretli yedekleme yoktur.
- OpenRouter hesabında kredi satın alma, otomatik yükleme veya faturalı kullanım açılmamalı. Anahtar yalnız GitHub Actions Secret `OPENROUTER_API_KEY` içine girilir. Değişken `RADAR_FREE_LLM_ENABLED` tam olarak `true` yapılmadan API çağrısı yoktur.
- Güncel ücretsiz sınırlar ve politika: https://openrouter.ai/collections/free-models ; ücretsiz yönlendirici: https://openrouter.ai/openrouter/free .
- Ücretsiz sağlayıcılar gönderilen metinleri saklayabilir veya model eğitimi için işleyebilir; bu nedenle yalnız kamuya açık/filtrelenmiş özet gönderilir.
- **Gerçek ücretsiz API denemesi** yalnız kullanıcı anahtarı konduğunda doğrulanabilir. Çevrimdışı mock başarıları canlı çağrı başarısı değildir.
