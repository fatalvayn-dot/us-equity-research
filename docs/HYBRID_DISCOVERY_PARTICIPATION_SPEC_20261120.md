# Adaptif Yatırım Uzmanı — hibrit keşif ve katılım kapısı (deney)

Tarih: 20 Kasım 2026. Bu belge yeni kullanıcının sıralama kararını mevcut geçmiş SEC tabanlı prototipten ayırır.

## Sıra
1. **Şirket keşfi:** Yalnız Google Finance Scraper ve yfinance ile ABD, BIST ve Avrupa aktif şirket adayları çıkarılır. `google_symbol`, `yahoo_symbol`, ülke, borsa ve kaynağın adı korunur. Yinelenenler tekilleştirilir. Kaynakların tüm aktif şirketleri sağlayabildiği henüz kanıtlanmamıştır; ilk test yalnızca sınırlı canlı keşiftir.
2. **Katılım filtresi:** Şirket faaliyetleri ve muhasebe oranları açık kaynak `bamlhs/halal-stock-analyst` MIT ekranıyla incelenir. Bu motor resmî AAOIFI veya BIST katılım endeksi sertifikasyonu değildir. Bütün zorunlu alanlar ve dönemler doğrulanmadan eski motorun eksik veriyi sıfır kabul eden varsayımı kullanılmaz. Banka ve sigorta, faaliyetten elenir.
3. **Puanlama:** Sadece `kosullu_gecti` şirketlerde deneysel gösterge puanı hesaplanır. Gerçek yatırım skoru veya yatırım önerisi değildir. Gerçek sistem puanı ve sonraki araştırma aşamaları bu kapı kabul edilene kadar aktive edilmez.

## Üç durum
- `kosullu_gecti`: açık kaynak ekranından koşullu teknik geçiş; dinî/kurumsal uygunluk sertifikası değil.
- `uygunsuz`: faaliyetten veya seçili model oranından elenen.
- `belirsiz`: eksik finansal kanıt, bozuk payda veya veri bağlantı hatası; puanlama ve yatırım önerisi **yasak**.

## Kanıt ve riskler
- Google Finance'ın `market-movers` ve `trending` listeleri tüm piyasaların şirket rehberi değildir.
- yfinance ülke bazlı tarayıcısının kapsama ve ülke filtreleri gerçek canlı testte doğrulanmalıdır.
- BIST Yahoo sembolleri `.IS`, Google `:IST`; Avrupa ticaret yerleri farklı Yahoo eklerine çevrilir, tahmine dayalı eşlemeler ayrıca denetlenmelidir.
- Kaynakların piyasa veri kullanım lisansları incelenmeden verinin toplu kamuya yeniden yayımlanmasına geçilmez.
- Motorun likidite/alacak oranları **kendine özgü** bir metodolojidir. AAOIFI veya BIST katılım onayı olarak etiketlenmez.
- `interest_income` açıkça verilmemişse 0 sayılmaz; şirket belirsizdir.
- Üç piyasa için yeterli sonuç gelmezse ön eleme tamamlandı denemez.

## Gerçek test
GitHub Actions `.github/workflows/hybrid-gate-verification.yml`: çevrimdışı 8 regresyon ve üç piyasada en fazla sekizer keşif sonucu üzerinde canlı doğrulama. Ana dalı ve gerçek portföyü değiştirmez; yatırım emri göndermez. Çıktılar Actions artifact içinde saklanır.
