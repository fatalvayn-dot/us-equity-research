# Google Finance — araştırmada eksik kaynak bulma (19.11.2026)

Kullanıcı örneği: https://www.google.com/finance/quote/AAPL:NASDAQ

## Gerçek örnek ve sınır

Google Finance'in AAPL/NASDAQ kamuya açık sayfasında
hisse fiyatı, piyasa değeri, hisse adedi, F/K, EPS, sektör,
haber/analiz ve yıllık/çeyreklik gelir tablosu, bilanço,
nakit akışları **görüntülenebiliyor**. Bu bilgi, eksik
alanların nerede olduğuna ve özgün hangi SEC/iXBRL satırına
bakılacağına karar vermeyi kolaylaştırır.

Ancak resmî veri lisans/feragat sayfasında Google, otomatik
kopyalama, indirme, kaydetme, yeniden işleme veya dağıtım
için **önceden yazılı izin** öngörüyor:
https://www.google.com/intl/en/googlefinance/disclaimer/

Google Finance finansal tablolarının kaynaklarından
S&P/Fiscal.ai; tarihli fiyat ve kur bilgileri farklı
lisanslı veri sağlayıcıları tarafından gelebilir.
Sunulan "Shares outstanding" gibi özet değerlerin
tarihleri, piyasa değeri hesaplama hissesi mi sınıf
hissesi mi olduğu ve tam SEC bildirimi accession
eşleşmesi mevcut **özgün SEC 10-Q/10-K kaynak kapısı**
olmaksızın finansal skorun değeri olamaz.

## Radar için somut uygulama kuralı

1. Yeni/eksik bir ihraççı için Google Finance arayüzü
   **manuel araştırma ve çapraz kontrol adresi** olarak
   incelenebilir. URL `https://www.google.com/finance/quote/{TICKER}:{EXCHANGE}`;
   tahmin edilen ticker-borsa adresi kaynak kimliği
   kanıtı değildir.
2. Hisse adedi, bilanço, nakit akışı, borç gibi
   alanlarda öncelik, kaynak sırası değişmeden
   özgün SEC/companyfacts ve şirket 10-Q/10-K
   bildirimlerindeki **aynı dönem/sınıf/tutar**
   doğrulamasındadır. Google rakamı SEC'e geri
   bağlanamıyorsa `unknown` bırakılır.
3. Google'daki haber veya analist tahmini
   `reported_financial_fact` veya katılım
   uygunluk belgesi değildir; öngörü/yorum
   ayrıca etiketlenir.
4. Toplu Google Finance HTML kazıması, üçüncü
   taraf scraper API ve veritabanına sayfa
   verisinin otomatik aktarımı **yok**.
   Tedarikçi lisansı/onayı varsa, yazılı izin ve
   veri sözleşmesi doğrulandıktan sonra
   ayrı geliştirme değerlendirilebilir.
5. Bu kaynak kullanımı eski 100'ün finansal
   hatalarını **kendiliğinden çözmüş sayılmaz**.
   Yeni adaylar için asıl tarama resmî SEC
   kimliği/filing kaynaklarıyla yürütülür.

**Araştırma kaynakları:**
- https://www.google.com/finance/quote/AAPL:NASDAQ
- https://www.google.com/intl/en/googlefinance/disclaimer/
- https://support.google.com/docs/answer/3093281/googlefinance?hl=en

Gerçek portföy pozisyonları kamuya açık GitHub'a
aktarılmaz. Katılım durumu netleşmemiş
varlıklara yeni yatırım emri önerisi verilmez.
