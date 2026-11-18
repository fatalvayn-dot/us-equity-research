# Hazır GitHub projeleri — SEC XBRL tanılama (19 Kasım 2026)

## Problem ve kanıt
18 Kasım durum dosyası: 100 adaydan 20'si puanlı; 35 değerleme, 29 eksik/tam finansal inceleme, 11 banka/sigorta dışlaması ve diğer engeller sürüyor. Kısıtlayıcı model/alan kontrolleri değiştirilmemeli. Yahoo -> SEC -> Nasdaq -> Finnhub **ilk geçerli** alan önceliği korunur.

## İncelenen hazır projeler

| Proje | Veri/kullanım | Karar |
|---|---|---|
| [dgunning/edgartools](https://github.com/dgunning/edgartools) | SEC 10-K/10-Q, özgün XBRL etiketleri, 13F; MIT | **Sınırlı, salt-okunur tanılama prototipi** |
| [ranaroussi/yfinance](https://github.com/ranaroussi/yfinance) | Yahoo fiyat/geçmiş/hisse bilgileri; Apache 2.0 kod | Mevcut Yahoo sağlayıcısını değiştirmeden araştırma; Yahoo veri kullanım koşulları ayrı |
| [openbq-org/OpenBB](https://github.com/openbq-org/OpenBB) | Çoklu sağlayıcı katmanı | Şimdilik ekleme: ağır bağımlılık ve mevcut sağlayıcı sırası ile çakışma |
| [sec-edgar/sec-edgar](https://github.com/sec-edgar) | SEC belge indirme | Mevcut SEC hattıyla mükerrer; şimdilik ekleme |

**GitHub projesi bir veri sağlayıcısı değildir.** Kod lisansı, indirilen fiyat ve finansal veri için kullanım hakkı sağlamaz. Harici bağımlılık üretim hattına varsayılan olarak yüklenmez.

## Bu daldaki uygulama
`scripts/probe_edgartools_xbrl.py` isteğe bağlı EdgarTools sorgusu yapar: ilgili şirketin en son 10-K belgesini bulur, birebir istenen kavram için gözlenen satır sayısını ve SEC accession/tarihini JSON'a yazar. `tests/test_probe_edgartools_xbrl.py` ağsız, taklit nesnelerle başarısızlık ve kanıt sözleşmesi denetler.

Deneme (bilinçli, manuel):
```bash
python -m pip install edgartools
export SEC_USER_AGENT="Research Team research@example.com"
python scripts/probe_edgartools_xbrl.py --ticker AAPL --concept us-gaap:Liabilities
```
Gerçek kimlik kullanın; örnekteki adres gerçek bir SEC kimliği değildir. Kütüphane API sürümüne göre kavram biçimi doğrulanmalıdır.

**Sınır:** Bu prototip üretim puanına veri sağlamaz; tam dönem, birim, hesap sınıfı ve kaynak hash'i doğrulanmadan mevcut kanıt modeline entegre edilmeyecek. 20/100 sonucu bu değişiklikle artmış sayılmaz. Canlı SEC/CI doğrulaması yapılmadan entegrasyon tamamlandı denmeyecek.

## Sonraki kabul kapısı
1. CI ağsız testleri geçsin.
2. Üretimde gerçekten eksik finansal alanı olan 2-3 finans-dışı adayda özgün SEC belgesiyle kavram, dönem, birim ve accession eşleşsin.
3. Tanılama sonucu üretim adaptörüne ancak kaynak sırası/ilk-geçerli kuralı, değişmez kanıt ve regresyon testleriyle bağlansın.
4. 100 adayın gerçek yeniden puanlamasında skor/engel farkı ölçülsün.

Ücretli servis, yeni izin veya işlem yetkisi kullanılmaz. Eski radar-agent deposuna dokunulmaz.
