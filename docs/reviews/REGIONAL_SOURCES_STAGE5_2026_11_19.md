# 5. Aşama – BIST ve Avrupa veri kaynakları ön incelemesi (19.11.2026)

## Amaç

ABD prototipindeki `Yahoo > SEC > Nasdaq > Finnhub` ilk-geçerli kaynak
sırası **değişmez**. Bu doküman BIST/Avrupa finansal rapor ve EUR bazlı
karşılaştırma için kaynak tanılama planıdır; herhangi bir canli hisse fiyatı
veya şirket skoru üretmez. #135–#138 nihai kabul aşamaları açık.

## Somut kaynak kimliği örnekleri

| Piyasa | Şirket | Hisse kodu | Doğrulanmış kamusal erişim | Tanılama |
| --- | --- | --- | --- | --- |
| BIST | ASELSAN | ASELS | https://kap.org.tr/tr/sirket-bilgileri/ozet/866-aselsan-elektronik-sanayi-ve-ticaret-a-s | KAP şirket özet sayfası |
| BIST | TÜPRAŞ | TUPRS | https://www.kap.org.tr/tr/sirket-bilgileri/ozet/1105-tupras-turkiye-petrol-rafinerileri-a-s | KAP şirket özet sayfası |
| BIST | BİM | BIMAS | https://www.kap.org.tr/tr/sirket-bilgileri/ozet/4028e4a140e95be70140ee1b7b030119 | KAP şirket özet sayfası |
| Almanya | SAP SE | SAP | https://www.sap.com/investors/en.html | Şirket yatırımcı ilişkileri |
| Almanya | Infineon Technologies AG | IFX | https://www.infineon.com/about/investor | Şirket yatırımcı ilişkileri |
| Almanya | Deutsche Telekom AG | DTE | https://report.telekom.com/annual-report-2025/ | Şirket yıllık rapor portalı |

Bu URL'ler **finansal kalemler için orijinal bildirim kanıtı değildir**.
Her şirket için ayrı bildirim URL'si, orijinal ham içerik SHA-256,
yayımlanma anı, finansal tablo yılı/dönemi, konsolide/konsolide olmayan
kapsam, varsa yeniden düzenlenen değer ve raporlama para birimi gerekir.
Türkiye'de KAP, IFRS/TFRS ve yüksek enflasyon muhasebesi dönemsel
karşılaştırmayı değiştirebilir. Avrupa için ESEF/iXBRL etiketi, yerel resmî
OAM başvurusu ve şirketin kendi raporu arasında karşılaştırılmalıdır.
Tek bir IFRS kavramı tüm sektörler için otomatik eş anlamlı sayılamaz.

KAP şirket profilleri ve resmî açıklamalar:
https://www.kap.org.tr/en/about/general-information
https://www.kap.org.tr/tr
Avrupa ESEF/OAM açıklamaları:
https://www.esma.europa.eu/issuer-disclosure/electronic-reporting
https://finance.ec.europa.eu/financial-markets/company-reporting-and-auditing/company-reporting/transparency-requirements-listed-companies_en

## Fiyat verisi ve lisans

Borsa İstanbul gerçek zamanlı/gecikmeli/gün sonu piyasa verileri lisanslı
dağıtıcılar üzerinden yayımlanır. Tarihsel fiyat verisi DataStore'dan
sağlanır; şartları araştırılmadan API kazıma veya lisanslı feed'i
kopyalama yapılmaz.

- https://www.borsaistanbul.com/en/data/data-dissemination
- https://www.borsaistanbul.com/en/data/historical-data-sales

## ECB EUR kur araştırması

ECB EXR serisi euro **bazlı** referans kuru sağlar:
- USD için `EXR.D.USD.EUR.SP00.A` = EUR başına USD.
- TRY için `EXR.D.TRY.EUR.SP00.A` = EUR başına TRY.
- Resmî örnekler: https://data.ecb.europa.eu/help/api/data-examples
- Referans saatleri: https://www.ecb.europa.eu/stats/policy_and_exchange_rates/euro_reference_exchange_rates/html/index.en.html

`regional_evidence.py`, sadece gerçek ham ECB CSV baytları verildiğinde
satır kimliği, tarih, birim, tekrar, pozitif değer ve SHA-256'yi inceler.
Referans gününün başlangıcında yayınlanmış gibi varsayılmaz. Gerçek
yayımlanma saati denetlenmeden geçmiş teste fiyat kurunu taşımaz.
ECB referans kuru Midas uygulama işlem kuru değildir; kur spreadi
hesaplanmış sayılmaz.

## Kesin sınırlar ve kabul

- Bu PR'de 6 gerçek şirket için **kaynak keşfi** var; 0 yeni doğrulanmış
  bilanço, 0 gerçek FX gözlemi, 0 lisanslı fiyat ve 0 katılım onayı.
- KAP endeks listesinde görünen katılım endeksi üyeliği, finansal oranları
  geçmiş tarihte teyit edilmiş kalıcı yatırım uygunluğu sayılmaz.
- Bankalar ve sigortalar tarama evreni dışında tutulur.
- Avrupa Midas komisyonu emir başı **1,50 EUR**. Türkiye borsasında işlem
  maliyeti teyitsizse sıfır kabul edilmez. Kaldıraç/opsiyon/gerçek işlem yok.

**Sıradaki tek iş:** Her pazarda 2–3 şirketin orijinal dönem bildirim
dosyası/ifrs taxonomy ve yayımlanma anını denetlemek; gerçek denetim
kanıtları sağlanmadan otomatik puanlama ve üretim kabulüne geçmemek.
