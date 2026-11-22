# AAPL katılım standardı araştırması — 22 Kasım 2026

**Kaynak:** S&P Dow Jones Indices, *S&P Shariah Indices Methodology*,
Mayıs 2026, sayfa 6–7.
https://www.spglobal.com/spdji/en/documents/methodologies/methodology-sp-shariah-indices.pdf

**Bu belge yöntem incelemesidir, AAPL'nin resmî uygunluk sertifikası değildir.**

Mayıs 2026 sürümü şu kuralları yayımlıyor:

- Faaliyetler ile ilgili uygunsuz gelir (bütün faiz gelirleri dâhil) /
  toplam ticari gelir: **%5'in altında**; faaliyet alanı taraması ayrı
  yapılmalıdır.
- Borç / özsermayenin **36 aylık ortalama piyasa değeri: %33'ün altında**.
- Bu sürümün güncel 6. sayfasında ayrı bir nakit/menkul kıymet oranı
  listelenmiyor. PDF'nin değişiklik geçmişi eski üç oranlı sürümleri
  içeriyor. PDF metninden tarih ayrımı yapılmadan eski oranlar
  güncel sürüme aktarılamaz.
- İki puanlık tolerans, üç ardışık değerlendirmenin takibi ve endekse
  alınma/çıkarılma koşulları tek dönem oranından farklıdır.
- SPUS, S&P 500 Shariah Industry Exclusions endeksini izleyen
  ilgili ETF olarak resmî endeks sayfasında listeleniyor:
  https://www.spglobal.com/spdji/en/indices/equity/sp-500-shariah-industry-exclusions-index/

## Kod değişikliğinin kapsamı

Mevcut `assess_participation` önceden her standarda üç mali
kural dayatıyordu. Mayıs 2026 S&P biçimini bu nedenle temsil edemiyordu.
Artık sürümlü yöntem açıkça bildirdiğinde iki veya üç oran
destekleniyor. İkinci durumda
`not_applicable_rules.interest_cash_securities` açıkça
`not_applicable_in_reviewed_methodology` olarak tanımlanmalı.
Hiçbir oran ve tarih otomatik sıfır veya varsayılan değer yapılmaz.

Yöntem dosyasının orijinal SHA-256 kontrolü ve yayım zamanı, AAPL için
orijinal SEC finansal kırılımlar, doğru borç kapsamı, 36 aylık
özsermaye piyasa değeri paydası, uygunsuz faaliyet/faiz gelirleri,
sektör ve hisse türü kanıtları hâlâ gereklidir.

Sonuç `kosullu_esik_gecisi` olsa bile
`investment_approved=false` ve `shariah_certified=false`
kalır. Kullanıcının banka/sigorta dışlaması da değişmez.
