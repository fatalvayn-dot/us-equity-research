# 6. Aşama — Katılım uygunluğu araştırma kapısı (19.11.2026)

## Geliştirilen ve özellikle yapılmayan

`src/equity_research/participation_screen.py` üç sonuçlu kaynak denetimi
yapar: `uygunsuz`, `bilinmiyor` ve `kosullu_esik_gecisi`.
**Sonuncusu katılım endeksi üyeliği, şer'i uygunluk sertifikası veya AL
tavsiyesi değildir.** Bütün çıktılarda
`qualified_for_investment=false`, `shariah_certified=false`,
`investment_approved=false`, `eligible_for_automatic_order=false`
kalır. Mevcut üretim skoru, kaynak önceliği, banka/sigorta dışlaması,
fiyat bağlantıları ve gerçek portföy değişmez. Kod ağ çağrısı yapmaz;
yalnız araştırmacının sağladığı girdilerle sözleşme doğrular.

## Kaynaklı kimlik ve yasaklar

1. ABD için SEC CIK, Türkiye için KAP kimliği, Avrupa için LEI
   **farklı isim alanlarında** ve kaynak tarihleriyle tutulur.
2. Bankacılık/sigortacılık kaynaklı sektör sinyalleri mevcut
   `excluded_banking_or_insurance()` filtresiyle birlikte
   kalıcı araştırma dışlamasıdır. Belirsiz sektör yeni alım için
   **uygun sayılmaz**. Diğer sektörler otomatik izinli kabul edilmez.
3. Hisse türü için kanıt aranır; adi hisse olmayan ETF, fon,
   REIT ve BDC gibi enstrümanlar ayrı inceleme ister.
4. Faaliyet ve gelir segmentlerinin tamamının incelenmesi ve
   kaynağın yayımlanma/erişim zamanı gerekir. İspatlanmış yasak
   faaliyet tarama dışıdır. Eksik faaliyet bilgisi `bilinmiyor`.
5. Borç, faiz getirili nakit/menkul kıymet ve izin verilmeyen
   gelir oranları **ayrı** ölçülür. Birim, rapor dönemi, tam
   pay/payda tanımı ve kaynak SHA-256 **zorunludur**.
   Uyuşmayan kalemlere sıfır atama veya otomatik eş anlamlı kavram
   seçme yapılmaz.
6. Üç eşik **kodda sabit değildir**: uygulama standardı
   (`standard_id`, `version`, yürürlük tarihi, özgün kaynak,
   gözden geçirme durumu) ve tam pay/payda tanımı açıkça
   tedarik edilmelidir. Farklı İslami endeks metodolojileri
   aynı finansal oranın farklı paydalarını kullanabilir.
   Kaynağı denetlenmemiş/etkinleşmemiş yöntemle geçiş sonucu verilmez.

Kod, sağlanan URL/hashing metadata'nın gerçek kaynağını kendi başına
indirip **doğrulamaz**; `evidence_scope` bu sınırı açıkça
bildirir. Tarihsel dönem için yeniden düzenlenen tablolar, yayım anı,
konsolide kapsam, faiz/borç tanımı ve hisse sınıfı ayrıca incelenecek.

## Borsa İstanbul için doğrulanan Ekim 2026 kuralı

Güncel birincil kaynak: Borsa İstanbul, **Ekim 2026**
[BIST Piyasa Değeri Ağırlıklı Pay Endeksleri Kural Seti](https://borsaistanbul.com/files/bist-pd-agirlikli-pay-endeksleri-ks-tr-2026-ekim-temiz.pdf),
madde **6.8 (e)–(f)**. BIST Katılım Tüm Endeksi için:

- Rehber madde 3.2 uygun olmayan faaliyet geliri / toplam gelir **%5**,
- faizli varlıklar / toplam varlıklar **%33**,
- faizli borçlar / toplam varlıklar **%33**.

Bunlar **Ekim 2026 sürümüne** aittir; eski PDF'deki
`toplam varlıklar veya ortalama piyasa değeri` alternatifini
bu sürümün hesaplama paydası gibi kullanmak **yanlıştır**.
Konsolide tablo varsa konsolide tutar kullanılır. Kurallar
mevcut endeks üyeleri için %10 eşik aşımı ve birbirini izleyen
dönemlere bağlı ayrı tolerans da içerir; bu bir **yeni aday
uygunluk onayı** olarak yorumlanmaz.

Resmî katılım sürecinde şirketin [KAP Katılım Finansı İlkeleri Bilgi
Formu (KAFİF)](https://www.kap.org.tr/tr/bist-sirketler)
ve KAFİF Komitesi incelemesi bulunur:
[Borsa İstanbul Katılım kaynak sayfası](https://www.borsaistanbul.com/endeksler/bist-pay/katilim).
Kod bu formu **henüz okumaz**; katılım endeksi üyeliği kararı
üretmez. Genel araştırma kapısı kural sürümü ve resmî
finansal değerler bağımsız teyit edilene kadar üretim için açılmaz.

## Test durumu ve sonraki kabul

`tests/test_participation_screen.py` tamamen **sentetik** numaralar
ve kurum/standart metodu kullanır. Testteki `0.33`/`0.05`
örnek eşikleri **gerçek bir standarda ait olduğu iddiası taşımaz**;
üretimde varsayılan eşik olarak kullanılmaz.

Bu prototipte **0 gerçek şirket için katılım uygunluğu onaylandı**.
Yatırım önerileri bu prototip nedeniyle açılmaz. Her bir piyasada
1–2 gerçek şirket için resmî faaliyet bölümü, borç/nakit/tahvil
finansal ayrıştırması ve uygun bir yayınlanmış standart
sürümü bağımsız doğrulanıp incelenmeden üretime bağlanmaz.
BIST/Avrupa kaynak keşfi #139 kabul edilmedi; ABD
100 adaylık kabul #137 tamamlanmadı. #140 sadece araştırma
hazırlığı olarak ilerler; önceki aşamaların bitiş şartlarını
bypass etmez.

**Sonraki tek teknik iş:** seçilen yayımlanmış katılım standardının
tarih ve finansal payda tanımlarını doğrulayıp örnek ihraççılarda
orijinal raporla eşleştirmek; kurala veya sektöre uymayanları
yatırım tavsiyesi sıralamasında görünmez şekilde gizlememek,
gerekçeli `uygunsuz`/`bilinmiyor` olarak göstermek.
