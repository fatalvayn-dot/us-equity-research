# AAPL — kamuya açık katılım endeksi gözlemi (22.11.2026)

## Doğrulanabilen kamusal kaynak

SP Funds, [SPUS fon sayfasındaki](https://www.sp-funds.com/SPUS/) 20.11.2026 tarihli
portföy tablosunda AAPL / Apple Inc. / CUSIP 037833100 için satır yayımlıyor.
O tarihte raporlanan portföy ağırlığı %14,32.

S&P Dow Jones'un [S&P 500 Shariah](https://www.spglobal.com/spdji/en/indices/equity/sp-500-shariah-index/)
sayfası katılım endeksi için ayrı bir resmî metodolojiye işaret ediyor.
SPUS fonunun takip ettiği **S&P 500 Sharia Industry Exclusions Index** ile
S&P 500 Shariah indeksleri yöntem bakımından otomatik eşdeğer sayılmaz.

## Araştırma kararı

- Kimlik: AAPL, SEC CIK 0000320193; SPUS satırında CUSIP 037833100.
- Sınıflama: `fund_holding_observed_2026_11_20`. Bu durum, bağımsız
  finansal oran taraması veya şer'i uygunluk sertifikası değildir.
- Mevcut `equity_research.participation_screen.assess_participation()`
  sonucu, orijinal finansal kaynağın SHA-256 doğrulaması, tarihli standart,
  faizli borç/nakit/uygun olmayan gelir ve faaliyet ayrımı tam sağlanana kadar
  **bilinmiyor** kalır.
- `qualified_for_investment=false`, `eligible_for_automatic_order=false`.
  Güncel fon üyeliğini süresiz statüye çevirmek yasaktır.

## Bir sonraki çalışma

Yayımlanmış ve sürümlü ABD katılım standardı ile şirketin orijinal SEC
açıklamalarındaki tam pay/payda tanımlarını eşleştir. Dosyaya kaydedilmiş
bir bağlantıyı indirilip SHA-256 olarak doğrulanmış sayma. Doğrulanmamış
eşiklere sıfır veya varsayılan yüzde atama. Aynı sınırlama Avrupa için
ayrı indeks yöntemleri ve BIST için kullanıcının resmî XKTUM üyelik kuralı
bakımından da uygulanır.
