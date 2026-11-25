# Avrupa katılım filtresi: MSCI Europe IMI Islamic (20 Kasım 2026)

## Kullanıcı kararı
ABD/BIST/Avrupa aktif şirket evreni Google Finance + yfinance hibrit yöntemle bulunur. Avrupa için katılım filtresinin birincil kaynağı MSCI Europe IMI Islamic Index, kodu 762539. Tam MSCI resmî bileşenleri doğrulanamazsa bir İslami ETF'nin halka açık portföyü yalnız araştırma amaçlı yedek kanıttır; **resmî MSCI Europe IMI Islamic üyeliği yerine geçmez.** Yalnız doğrulanmış resmî uygunluk 3. aşama puanlamasını açabilir.

## Kaynaklar ve bulgular
- MSCI indeks sayfası https://www.msci.com/indexes/index/762539/msci-europe-imi-islamic-index; 30 Eylül 2026 görünümünde 428 bileşen raporlanmıştır. Bu bir **toplam sayıdır**, bileşen CSV'si değildir.
- GitHub Actions GitHub IP'sinden MSCI sayfası `Challenge Validation` döndürmektedir; `msci.com/constituents` de reCAPTCHA. Tam resmî üye listesi indirilemedi.
- HSBC MSCI Europe Islamic Screened ETF (ISIN IE000AGFZM58) https://www.assetmanagement.hsbc.co.uk/en/institutional-investor/funds/ie000agfzm58, **farklı MSCI Europe Islamic Universal Screened Select** endeksini izler. Fonun açık ürün sayfası var, tam ve makine okunabilir portföy tablosu henüz teyit edilmedi.
- iShares MSCI World Islamic UCITS ETF (ISIN IE00B27YCN58) için `latest-holdings.csv` HTTP 400; denenen iki `.ajax` bağlantısı HTML döndürdü. Dünya fonunun Avrupa payları bulunsa bile MSCI Europe IMI Islamic listesinin tamamı değildir.
- MSCI indeks verilerinin tekrar dağıtım koşulları araştırılmadan ham bileşen listesi kamuya açık GitHub'a yüklenmez.

## Uygulama
- `experiments/hybrid_gate/europe_msci_gate.py`: resmî tam dosyada başlık, tarih, ISIN tekilliği, indeks adı ve beyan edilen sayı denetimi; ayrı ETF portföyü kanıt sınıfı; eksik/ambiguous kimliğe otomatik onay vermeme.
- `experiments/hybrid_gate/run.py`: Avrupa bölümü varsayılan olarak açık kaynak genel oran filtresini kullanmaz. **Tam resmî MSCI bileşen dosyası olmadan hiçbir Avrupa şirketine koşullu katılım geçişi veya puan verilmez.**
- `.github/workflows/europe-msci-gate.yml`: canlı kaynak erişim denemesi, çevrimdışı regresyon ve düşük hacimli hibrit kaynak testi.

## Kabul durumu
- Yalnız kural ve engel denetimi testleri başarılıysa **yapısal entegrasyon** tamam; resmî tam liste canlı olarak alınmadan **gerçek Avrupa katılım taraması kabul edilmez**.
- Kullanıcı portföyü, para hareketi ve gerçek emir yok.
- Sonraki tek iş: kaynak sahibinden resmî, güncel, tam MSCI Europe IMI Islamic bileşen dosyasına yasal erişim; varsa resmî fonun doğrulanabilir portföy CSV'sini alternatif destek olarak ayrıştırma.
