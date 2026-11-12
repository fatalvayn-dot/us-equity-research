# Adaptif Yatırım Uzmanı — kaynak politikası (12 Kasım 2026)

## Araştırma hiyerarşisi

Birden fazla kaynaktan alınan verinin tarihini, kapsamını, para birimini ve
muhasebe tanımını karşılaştır. Haber sitelerinin fikrini şirketin resmî
açıklaması yerine koyma. Çok sayıda aynı haberi farklı sitelerde görmek
bağımsız doğrulama sayılmaz. Hiçbir kaynak yatırım getirisi garanti etmez.

### A. Birincil doğrulama (olay ve finansallar)
- ABD: SEC EDGAR, şirket yatırımcı ilişkileri, 10-K/10-Q/8-K.
  https://www.sec.gov/search-filings/edgar-application-programming-interfaces
- BIST: KAP bildirimleri ve resmi finansal raporlar.
  https://kap.org.tr/tr/bildirim-sorgu
- BIST piyasa istatistikleri: Borsa İstanbul.
  https://www.borsaistanbul.com/en/market-data
- Avrupa: şirketlerin investor relations açıklamaları, ilgili borsanın/ülkenin
  resmi bildirim mekanizması, ECB ve Eurostat bağlamı.
  https://data.ecb.europa.eu/help/api/data
  https://ec.europa.eu/eurostat/web/user-guides/data-browser/api-data-access/api-introduction

### B. Fırsat keşfi ve ilk haber taraması
- Yahoo Finance aktif hisseler: https://finance.yahoo.com/markets/stocks/most-active/
  **Hacim ve anormal hacim**, piyasa değeri ve fiyat değişimi araştırma
  tetikleyicisi olabilir. En çok işlem görme AL sinyali değildir.
- Yahoo Finance ekonomi/finans haberleri: https://finance.yahoo.com/news/
  Genel https://www.yahoo.com/news/ finansal yatırım için daha seyrektir.
- Midas ABD/BIST/kripto ürün sayfaları, ücretler ve Midas'ın Kulakları.
  İlgili fiyat, haber, işlem erişimi, duyuru alanları birbirinden ayrılır.
- Avrupa keşfi: https://tr.investing.com/equities/europe (PR #111 kaynak notu).

### C. Piyasa rejimi ve makroekonomi
- FRED/ALFRED: https://fred.stlouisfed.org/docs/api/fred/
  ABD faiz, enflasyon, işgücü ve ekonomik eğilim serileri. API anahtarı
  gerekebilir; yoksa veri alınmış gibi gösterilmez.
- BLS: https://www.bls.gov/audience/developers.htm
- ECB: https://data.ecb.europa.eu/help/api/data
- Eurostat: https://ec.europa.eu/eurostat/web/user-guides/data-browser/api-data-access/api-introduction
- CFTC COT: https://www.cftc.gov/MarketReports/CommitmentsofTraders/index.htm
  Haftalık büyük yatırımcı pozisyonlaması, hisse senedi için tek başına sinyal değildir.
- Borsa İstanbul piyasa ve yabancı yatırımcı istatistikleri.

### D. Profesyonel/kurumsal referans (varsayılan entegrasyon değil)
Bloomberg, FactSet, LSEG Workspace, S&P Capital IQ, Morningstar, AlphaSense:
çok yönlü finansallar, tahminler, raporlar ve transkriptler; çoğu lisans
veya abonelik gerektirir. Ulaşım izni ve maliyet açıkça onaylanmadan
gizlice API/scraper kullanma ya da ücretli kaynak bağımlılığı oluşturma.

Referanslar:
https://www.library.hbs.edu/services/help-center/resources-for-investment-management-and-financial-analysis
https://www.insead.edu/library/research-guides-finding-company-information

## Araştırma kalitesi ve maliyet kuralları
1. Kamusal fiyat akışı gecikmeli olabilir: saat ve seans olmadan işlem kararı verme.
2. Birincil kaynak yoksa `unverified` notu kullan; uydurma değer üretilmez.
3. Haberlerin ilk yayın tarihi ile olay tarihi ayrı kaydedilir.
4. Eşdeğer olmayan muhasebe alanları otomatik eşleştirilmez.
5. Haberler ve fiyatlar karar için yeterli değildir: değerleme, finansal sağlık,
   katılım, piyasa rejimi, karşıt senaryo ve işlem maliyeti değerlendirilir.
6. Midas işlem erişimi ile şirketin piyasada listelenmesi aynı şey değildir.
   Kullanıcının hesabında bulunmayan/teyit edilmemiş ürün uygun kabul edilmez.
7. Otomatik site taraması yalnızca kaynak şartları ve teknik uygunluk doğrulanırsa
   uygulanır. Kamuya açık sayfa, sınırsız/ücretsiz API izni demek değildir.
8. Her veri çekişi zaman damgası, kaynağı ve değişiklik durumunu içerir.
9. Aynı haberin tekrarları kaldırılır. Önceden araştırılan sabit veri için
   tekrar yapay zekâ kotası kullanılmaz.
10. Yeni bir kaynak, raporu veya karar kalitesini artırmıyorsa entegre edilmez.

## Entegrasyon durumu

Bu belge kaynak **seçim ve doğrulama politikasıdır**, otomatik bağlayıcı değildir.
Mevcut GitHub günlük fiyat sağlayıcısı Yahoo chart üzerinden örnek sembollerdir.
Yahoo haber listesi, Yahoo Most Active, FRED, KAP, ECB gibi kaynaklar
henüz bu belgeyle canlı API entegrasyonuna dönüşmez. Önce makul maliyet,
erişim şartları, hataya dayanıklılık ve gerçek veri testi yapılır.
