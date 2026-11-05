# GitHub üzerinde devam ettirilebilir canlı kabul

## Sorun

5 Kasım 2026 tarihindeki son yoklamada SEC kimlik dizini ile Nasdaq'ın kendi
liste dosyası yanıt verdi. SEC bildirimleri, Companyfacts, Yahoo fiyatı ve
Nasdaq'ın diğer borsalar listesi zaman aşımına uğradı. Bu sonuç kaynakların genel
olarak kapalı olduğunu veya şirket verisinin eksik olduğunu kanıtlamaz.

## Uygulama

1. GitHub Actions > **Canlı 100 şirket kabulü** > **Run workflow** bölümünü açın.
2. İlk çalışmada `resume_run_id` alanını boş bırakın; belge ve finansal alan
   bütçelerini seçin.
3. İş bitince `live-source-preflight`, `live-acceptance-state` ve
   `live-acceptance-evidence` artifact'lerini inceleyin.
4. Kesilen veya bütçesi dolan çalışmada önceki koşunun kimliğini
   `resume_run_id` alanına yazın. İş akışı yalnız o koşunun durum paketini
   indirerek devam eder.
5. Üç zorunlu SEC kaynağı erişilebilir değilse finansal toplama başlamaz;
   erişim raporu yine saklanır. Yahoo veya Nasdaq erişim sorunu SEC üzerinden
   yapılabilen kısmi toplamayı engellemez.

## Yorumlama

- `timeout`: bu ortamda yanıt zamanında gelmedi; kaynak verisi eksik demek değildir.
- `access_denied`: erişim engeli; şifreleme, proxy, çerez veya erişim engeli
  atlatma uygulanmaz.
- `response_received`: yalnızca HTTP yanıtı alındı. Şirket, muhasebe
  eşleşmesi, kaynak güncelliği veya 100 şirket kabulü kanıtı değildir.
- `live-acceptance-state`: kesintiden devam etmek için çalışma verisidir.
- `live-acceptance-evidence`: kaynak kanıtının taşınabilir dışa aktarımıdır.

İş akışı zamanlanmış değildir; ücretli servise erişmez, secret veya yeni yetki
istemez ve gerçek alım-satım işlemi yapmaz. Artifact'ler 14 gün saklanır. Bir
koşunun başarılı olması tek başına 100 şirket kabulü değildir; çıktıdaki şirket,
dönem, para birimi, kanıt ve puan kapsamı ayrıca doğrulanmalıdır.
