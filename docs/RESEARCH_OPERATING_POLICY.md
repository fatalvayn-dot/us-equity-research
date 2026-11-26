# Kullanıcı tanımlı ürün akışı — 26 Kasım 2026

Bu güncelleme, önceki katı “her finansal girdisi tamamlanmayan adaya hiç puan verme” yaklaşımını aşama bazında netleştirir. Eksik ama kritik olmayan bilgi ilk puanlamayı veya diğer şirketlerin taramasını durdurmaz. Güvenilir olmayan veriyi sıfırla doldurmak, kaynağı uydurmak veya belirsizliği gizlemek hâlâ yasaktır.

1. Piyasa şirketlerini mümkün olduğunca keşfet; evren eksik olsa bile bulunan adaylarla ilerle.
2. Katılımı uygun / uygun değil / belirsiz olarak sınıflandır. Uygun = kabul; uygun değil = ret; hızlıca çözülemeyen belirsiz = şartlı kabul olarak sonraki aşamaya geçer.
3. Kabul ve şartlı kabul adaylara mevcut finansal veriler ve şirket haberleriyle basit ön puan ver. Eksikliği görünür kıl; ağır finansal sıkıntıyı ele, diğerlerini mevcut veriyle sırala.
4. Üçüncü aşamadan geçenleri daha derin araştır; ayrı %0–%100 yatırım uygunluğu puanı üret. Kritik veri bulunamazsa alternatif kaynakları bir kez makul biçimde ara; yalnız ilgili şirketi derin puan/öneri dışında tut, diğerlerine devam et.
5. Geçmiş dönemlerle geriye dönük backtest yapılmayacak.
6. Erişilebilen şirket, haber, yatırımcı/fon, uzman, yatırım planı ve hedef verilerini araştır; önce kısa özet, istenirse ayrıntılı şirket raporu ver.
7. Raporu olan şirket için gerekçeli AL / TUT / SAT / BEKLE seçeneği üret; gerçek emir verme.
8. Üretilen kararları tarihli kaydet ve kısa/orta/uzun vadede ileriye dönük sonuç/isabet izle. Bu, tarihsel backtest değildir.

İlk ve derin puan farklı alanlar olarak saklanır; kapsam, veri tarihi, yuvarlama ve belirsizlik açıkça gösterilir. Kullanıcının mevcut piyasa, katılım, maliyet ve kişisel veri sınırları aynen korunur. #134'teki 26.11.2026 ekinde ürün akışı, #135–#142 ise yazılım teslim issue'ları olarak ayrıştırılmıştır.

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
