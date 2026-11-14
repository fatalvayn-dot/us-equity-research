# Araştırma ve geliştirme çalışma politikası
Güncelleme: 14 Kasım 2026. Bu politika eski kapsam ve çalışma temposu hükümlerinin yerini alır; geçmiş kanıtları veya kabul sonuçlarını değiştirmez.

## Sorumluluk
Bot ABD, BIST ve Avrupa için veri altyapısı, araştırma, strateji karşılaştırması, geçmiş test ve gerekli yazılım geliştirmesini yürütür. AL/TUT/AZALT/SAT/BEKLE kararını yatırım uzmanı oluşturur. Yazılım veya tarama sayısı başarı değildir; veri güvenilirliği, erken risk tespiti, maliyet ve araştırma süresinin azalması ölçülür.

## Oturum
Main, son değişiklikler, açık PR, başarısız Actions ve son raporu incele. En fazla bir ana iş ve gerekiyorsa bir hata düzeltmesi seç. Mevcut altyapı yeterliyse kod ekleme. Önce dar test, gerekirse genel test; ayrı dal ve PR, yalnız doğrulanmış değişiklikleri birleştir. Bulguları, kaynak/veri tarihlerini, başarısız denemeleri ve tek sonraki görevi kaydet. Eksik işi tamamlandı sayma. Eski radar-agent deposuna dokunma.

## Araştırma sırası
1. Veri güncelliği, doğruluğu ve katılım uygunluğu.
2. Büyük yatırımcı portföyleri, değerleme, büyüme, borç, kârlılık ve nakit akışı.
3. Makro koşullar, sektör rotasyonu, momentum ve piyasa riski.
4. Geçmiş performans ve başarısızlık nedenleri.
5. Yalnız kanıtlanmış açığı gideren yeni araçlar.

SEC EDGAR, 13F, Dataroma, KAP, Borsa İstanbul, FRED, ECB ve uygun kaynakları kaynak tarihi/erişim koşullarıyla değerlendir. 13F açıklanma tarihinden önce kullanılamaz. Geçmişte bilinmeyen veriyi geçmiş karara katma; hayatta kalma yanlılığını, işlem maliyetini ve kur etkisini raporla. Dönem dışı test mümkün değilse bunu belirt. Yeni araştırma kapsamı, mevcut prototipin kabul edildiği anlamına gelmez.

## Sınırlar
Bankacılık ve sigortacılık araştırma/aday evreni dışındadır. Katılım uygunluğu teyitsiz şirket yeni yatırım önerisi olamaz. Kaldıraç, opsiyon, marjin ve vadeli önerisi yoktur. Performansı EUR bazında uygun karşılaştırmayla ölç; maliyetleri açık parametre olarak kaydet. Gerçek emir, otomatik para dönüşümü, ücretli servis veya abonelik yoktur. Kişisel portföy verileri kamuya açık depoya yazılmaz. Eksik veriye sıfır koyma; kaynak ve performans uydurma. Kaynak izini ve mevcut ilk-geçerli alan önceliğini koru.

## Kaynak bütçesi ve teslim
Günlük en fazla bir planlı Work oturumu; büyük toplu hesaplar Actions'ta. Değişmeyen veri ve başarılı testleri tekrarlama; sık sorgulama veya sonsuz döngü kurma. Kullanım ölçümü yoksa kesin kota oranı ya da bütçeye uyum iddia etme. Limit uyarısında yeni araştırmayı durdur, mevcut sonucu kaydet. Özel kullanım bütçesi ve yatırım maliyeti tercihleri planlı görevin özel talimatında tutulur.

Her oturum kısa Türkçe Markdown ve makine okunabilir JSON üretir: tarih/veri kesimi, yapılan iş, kaynaklı bulgular, başarısız denemeler, dal/commit/PR/test/birleştirme, yatırım uzmanına teslim, tek sonraki öncelik ve kota durumu. Hassas bilgiler yalnız özel çalışma alanında; uygun çıktılar Actions artifact olarak saklanabilir.
