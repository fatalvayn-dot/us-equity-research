# Public research universe — incremental radar observation

21 Kasım 2026, P1 için sınırlı veri gözlem denemesi. #158 kapsamındaki tam borsa evreni kabulü **değildir**.

## Giriş
- Tek giriş `data/analyst/public_research_universe.json` (depo sürümü ve SHA-256 kaydedilir).
- Bu dosya zaten kamuya açık araştırma sembollerini içeriyor: ABD 13, BIST 6, Avrupa 4. Liste resmi borsa üyelik teyidi değildir.
- Önceki pilotun 9 gözlemi korunur. Aynı sembol ikinci defa sorgulanmaz.
- Toplamda 28 benzersiz fiyat gözlemi denenecek; bu sayı gerçek başarılı veri sayısı değildir.
- Yeni listede üst sınır 40 şirket, pilotlarla birlikte 50 semboldür. Yanlış kimlik, para birimi, yinelenen sembol, beklenmeyen alan veya aşırı büyük dosya koşuyu durdurur.

## İşleyiş ve denetim
- Kaynak sırası: yfinance (tarihli günlük kapanış) → Yahoo Chart → uygun Stooq sembolü.
- Başarılı fiyatın kaynak etiketi saklanır; boş/veri hatası bulunan hisseyi başarılı göstermez.
- Tahmin geçmişinin anahtarı `(sembol, veri_tarihi)`; aynı işlem günü yinelenen çalışma eski kaydı değiştirmez. Eski tahminlerin gerçekleşmesi ancak 5 tam işlem günü sonrasında değerlendirilir.
- BIST ve Avrupa eklemeleri tamamlanmış borsa taraması değil, gözlemsel örneklerdir.
- Banka/sigorta dışlaması ve katılım uygunluğu bu fiyat modülünde araştırma amaçlı gözlemden yatırım adayına terfi ettirilmez. **BIST katılım filtresinde yalnız resmî XKTUM bileşen listesi** kullanılacak; bu listede üyelik doğrulanmadığı için bütün sembollerin yatırım uygunluğu `bilinmiyor`.
- Avrupa/ABD için ilgili katılım standardı ve bileşen/finansal denetim bağımsız doğrulanana kadar öneri üretilmez.
- Herhangi bir gerçek emir, nakit dönüşümü, broker yetkisi, özel portföy okuması, ücretli servis veya öz-öğrenen model yoktur.

## Kabul ölçütü
1. `tests.test_market_radar_universe` ve mevcut pilot/ajan testlerinin gerçek Actions koşusunda tamamlanması.
2. Canlı veri denemesinde kapsam sayısının ve hata nedenlerinin raporlanması. 28/28 başarı iddiası ancak kanıt varsa.
3. Üç Python sürümünde temel testler, PR sınırlı fark kontrolü, sonra ana dal birleştirmesi.
4. Ana dalda en az bir çalışmada `radar-ledger` tahminlerinin silinmeden korunduğunu doğrulama.

## Kalan P1
Resmî ABD/Avrupa/BIST aktif hisse/ETF listelerinin tam sürüm kimlikleri, tarihli dosyaları, delist/sınıf/giriş-çıkış kontrolü, hız bütçesi ve BIST XKTUM bileşen eşleştirmesi. Güncel araştırma listesi bunun yerine geçirilemez.
