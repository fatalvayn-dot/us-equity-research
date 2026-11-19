# SEC dış kaynak doğrulama köprüsü — 19 Kasım 2026

## Kullanılan eklentiler ve ayrım

- GitHub: fatalvayn-dot/us-equity-research üretim kodu; eski radar-agent kullanılmaz.
- Firecrawl Alexandria: SEC companyconcept için sadece okuma/araştırma. ChatGPT bağlantısı, GitHub Actions kimlik doğrulaması değildir.
- Deepnote: Kaynaklı verilerin araştırma ve test defterleri; üretim skoruna otomatik bağlanmaz.
- MotherDuck: my_db mevcut ama son incelemede boştu. Şema veya veri değişikliği yapılmadı; veritabanı yazımı için ayrıca açık onay alınacak.

## Yeni kod: Firecrawl SEC denetim girdisi

Komut:
python scripts/audit_alexandria_sec_concept.py --input /yerel/alexandria.json --output /yerel/inceleme.json

Bu program dış ağ çağrısı yapmaz. Firecrawl JSON çıktısında sağlayıcı=sec-gov, capabilities=filings/concept, tam SEC CIK/XBRL kavram/taksonomi/SEC URL, SEC dosya numarası, form, dönem, para birimi ve sayı türü denetlenir. Uyumsuzluk hata verir. Dosyalar kamuya açık depoya otomatik gönderilmez.

Çıktı her zaman manual_review_only ve source_raw_sha256=null olarak raporlanır. Firecrawl yapılandırılmış sonucu SEC'in özgün bayt dizisi için SHA-256 kanıtı değildir; özgün kaynak doğrulanmadan otomatik puanlama yapılamaz.

Mevcut Yahoo > SEC > Nasdaq > Finnhub ilk geçerli veri sırası, kaynak arşivi, puanlama, katılım ve sektör kontrolleri değişmez. Şahsi portföy, anahtar ve ham Firecrawl yanıtları kamuya açık depoya yüklenmez.

## MotherDuck için öneri, henüz uygulanmadı

Sadece kamusal araştırma veri alanları: issuer_id, concept, taxonomy, source_url, accession, period_start, period_end, filed_on, unit, reported_value, observed_at_ms ve review_state. Tekilleştirme şirket/kavram/dönem/accession/birim ile yapılmalı; kaynak gözlem geçmişi saklanmalı. Kişisel portföy verisi yok.

Tablo oluşturma ve veri yükleme yapılmadı. Değişiklik için açık kullanıcı onayı gerekecek.

## Test ve kabul

- Firecrawl SEC AAPL Assets 2026 10-K verisini özgün kaynak bağlantısıyla döndürdü: bu, ChatGPT eklentisinde gerçek okuma testidir.
- Bu PR, yalnız ağsız JSON sözleşmesi testleri içerir; canlı GitHub/SEC denemesi sayılmaz.
- Radarın son doğrulanmış üretim skoru 20/100; bu köprü onu artırmaz.
- Sonraki teknik kanıt: eksik finansal alanı olan 2-3 adayda SEC aslını ve kaynak SHA-256 değerini karşılaştır; gerçek avantaj varsa üretim toplayıcısına kontrollü yeni özellik ekle.
