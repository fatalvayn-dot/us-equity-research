# 1. Aşama — SEC özgün bayt SHA-256 ve güvenli puanlama eşleştirmesi

Tarih: 19.11.2026 · Görev #135

## Doğrulanacak iki kamusal gözlem

- **NVDA** (SEC CIK `0001045810`): `us-gaap:Liabilities`; 2026-01-25; 49.510.000.000 USD; 10-K `0001045810-26-000021`; açıklama 2026-02-25.
  Orijinal: https://data.sec.gov/api/xbrl/companyconcept/CIK0001045810/us-gaap/Liabilities.json
- **SWKS** (SEC CIK `0000004127`): `us-gaap:Liabilities`; 2026-10-02; 3.721.100.000 USD; 10-K `0000004127-26-000055`; açıklama 2026-11-10.
  Orijinal: https://data.sec.gov/api/xbrl/companyconcept/CIK0000004127/us-gaap/Liabilities.json

Mevcut MotherDuck `my_db.main.sec_evidence_staging` tablosunda iki kaynak
`source_raw_sha256=NULL` ve `exact_concept_candidate_unverified`
statüsündedir. Kullanıcı SHA-256 doğrulamaya ve yalnız bu iki satırın
güncellenmesine izin verdi. Bu doküman tek başına DB değişikliği değildir.

## Uçtan uca gerçek doğrulama

`scripts/live_stage1_sec_verification.py`, `SEC_USER_AGENT` ortam
değişkeni ile **sadece iki sabit SEC URL'sini** doğrudan HTTPS GET ile
indirir, her gövdenin özgün baytlarını saklar ve SHA-256 hesaplar.
`scripts/verify_alexandria_sec_raw.py` ile CIK, taksonomi,
kavram, tam accession/form, dönem sonu, `filed`, birim ve tutarı birebir
eşleştirir. Aynı değişmez indirilen baytlar üzerinden iki kez
replay yapar ve eş sonuçları denetler. Tekrar testi *aynı arşiv*
üzerindedir; iki bağımsız tarihsel indirme/yayım doğrulaması **değildir**.

GitHub Actions `.github/workflows/sec-stage1-original-verify.yml`,
yalnız `main` dalına bir defalık
`docs/operations/sec-stage1-verify-request.json` kaydı girilince
çalışır. Yanıtların HTTP gövdeleri, doğrulama manifesti ve SHA değerleri
geçici Actions **artifact** olarak saklanır; Git'e eklenmez.
GitHub Actions başarılı sonucu, kaynak tarama bütçesi ve doğrulanan
güncel arşiv kimliği olmadan MotherDuck statüsü değiştirilmez.

## Puanlama için koruma

`src/equity_research/sec_attestation.py` ve mevcut
`scripts/build_current_scores.py` içine eklenen isteğe bağlı
`--sec-stage1 ... --sec-raw-dir ...` desteği, her puanlama sırasında
değişmez ham SEC dosyasının SHA-256 ve özgün bilanço satırlarını
tekrar denetler. **Yalnız mevcut seçilmiş ve tam accession/dönem
eşleşen `liabilities` fact'iyle çelişki kontrolü** yapar.
Çelişki varsa skor dosyası üretilmeden hata verir; eşleşiyorsa
kaynak puanı, sektör modeli ve Yahoo > SEC > Nasdaq > Finnhub
ilk-geçerli sırası **aynen kalır**. Seçilen dönem farklıysa
`issuer_period_not_selected` olarak açıkça raporlanır;
eski bilgi yeni puan sayılamaz.

İsteğe bağlı bağlantının mevcut canlı GitHub puanlama akışında
aktifleşmesi, özgün canlı kanıt/artifact run ID ve digest
kanıtı doğrulandıktan sonra yapılmalıdır. Sonradan üretilen
bir raporun geriye dönük tarihte zaten mevcut olduğu iddia edilmez.

## Sınırlar

Bu doğrudan SEC CompanyConcept JSON API yanıtının özgün bayt
SHA-256'sıdır; ayrıca 10-K belgesinin HTML/iXBRL **tam belge hash'i
değildir**. JSON satırındaki `accn` özgün SEC 10-K'ye bağlar.
Kaynak kontrolü katılım uygunluğu, değerleme, alım-satım onayı,
arşivleri sıfırdan güncelleme veya 100/100 şirket puanı anlamına
gelmez. Kişisel portföy, erişim anahtarı veya ücretli servis yok.
