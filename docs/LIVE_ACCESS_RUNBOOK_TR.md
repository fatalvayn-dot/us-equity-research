# Canlı veri erişim engeli: GitHub üzerinde bağımsız doğrulama

## Sorun

5 Kasım 2026 tarihinde mevcut çalışma ortamından SEC, Yahoo ve Nasdaq Trader
adreslerine yapılan sekiz HTTP isteği zaman aşımına uğradı. Bu sonuç, kaynakların
genel olarak kapalı olduğunu **kanıtlamaz**. Aynı kaynaklar GitHub barındırmalı
Ubuntu yürütücüsünden ayrıca denenmelidir.

## Uygulama

1. Depoda mevcut değilse `SEC_USER_AGENT` adlı GitHub Actions secret değerini,
   gerçek proje kimliği ve iletişim bilgisi taşıyan SEC uyumlu User-Agent olarak
   tanımlayın. Gerçek değeri kaynak koduna veya raporlara yazmayın.
2. GitHub Actions > **Live public-source connectivity diagnostic** >
   **Run workflow** ile işlemi başlatın.
3. **public-source-preflight** adlı artifact içindeki
   `data/live-preflight.json` raporunu açın.
4. `reachable_sources` ve her kaynağın `attempts[].status` /
   `attempts[].reason` alanlarını değerlendirin.
5. SEC kimlik, bildirim ve finansal kaynaklarına erişim başarılıysa,
   README'deki `mvp-run` akışını yalnız kaynak erişimi olan ortamda çalıştırın.
   Uygun zamanlı kaynaklar ve gerçek kabul ayrıca doğrulanmalıdır.

## Yorumlama

- `timeout`: bu ortamda yanıt zamanında gelmedi; kaynak verisi eksik demek değildir.
- `access_denied`: erişim engeli; şifreleme, proxy, çerez veya erişim engeli
  atlatma uygulanmaz.
- `response_received`: yalnızca HTTP yanıtı alındı. Şirket, muhasebe
  eşleşmesi, kaynak güncelliği veya 100 şirket kabulü kanıtı değildir.
- Rapor hiç oluşmadıysa ilk önce `SEC_USER_AGENT` yapılandırma hatasını
  inceleyin.

İş akışı yalnızca kullanıcı tarafından tetiklenir, ücretli servise erişmez,
yeni yetki veya gerçek alım-satım işlemi istemez. Rapor azami yedi gün saklanır.
