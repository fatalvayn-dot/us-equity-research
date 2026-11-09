# Canlı değerleme kaynağı toplama — ilk prototip

Bu iş, ana 100 şirketlik finansal taramadan bağımsızdır. SEC şirket kimliği,
özgün hisse sınıfı belgesi, fiyat ve piyasa geçmişi için kaynak kanıtı toplar.
Skor, sektör kabulü, alım/satım emri veya MVP kabulü üretmez.

## Otomatik çalışma

SEC koşusu yeni kabul kanıtı üretmediğinde değerleme toplamasının
durması önlensin diye ayrıca günlük 09:17 UTC zamanlayıcısı vardır.
Zamanlayıcı, geçerli `live-acceptance-evidence` arşivi olan son
başarılı ana dal SEC koşusunu seçer. Bu, eski SEC yanıtlarının yeni
gözlem gibi kabul edildiği anlamına gelmez: özgün SHA ve tarih
korunur; 6 saatlik tohum tazelik kapısı uygulanır ve gerekiyorsa
gerçek kaynak GET isteği yapılır.

Yalnız ana dala ilk yayın sırasında istek sınırı 250, günlük
tekrarda 100 GET olur. Manuel çalıştırmanın seçili bütçe ve
kaynak ID'si aynen korunur. Tüm koşuların maksimumu 501 GET'tir.
Yeni kota ve ayrı iş akışı başarıyla tamamlanmış olsa bile bu,
skor veya yatırım kabulü anlamına gelmez.

İş akışı ilk kez ana dala alındığında, en son başarılı ve gerçek
\`live-acceptance-evidence\` paketi bulunan SEC koşusunu arayıp ilk kaynak
çalışmasını başlatır. Önceki veri paketleri orijinal tarihleriyle kullanılır;
eski fiyat otomatik güncel sayılmaz.

Ana daldaki `Canlı 100 şirket kabulü` iş akışı **başarıyla tamamlandığında**
değerleme kaynakları iş akışı tetiklenir. İş akışı önce SEC koşusunun gerçekten
`live-acceptance-evidence` artifact dosyası üretip üretmediğini GitHub API
ile doğrular. Önceki kontrol dilimi sınırına ulaşıp veri toplamayı atlamışsa
kanıt yoktur ve değerleme toplaması da atlanır.

Yalnız aynı depodaki ana daldan gelen başarılı SEC koşuları otomatik
işlenir; PR koşuları devralınmaz. İndirilen kaynak paketinin içerik ve SHA
bütünlüğü mevcut `read_bundle` denetiminden geçer. Son başarılı değerleme
koşusunun `valuation-source-state` artifact dosyası mevcutsa otomatik
yüklenir; yoksa yeni bir durum diziniyle başlanır. Tek çalışma grubu,
`cancel-in-progress: false` ve SQLite kilitleri çakışma riskini azaltır.

Otomatik çalışmanın yeni GET bütçesi **51**'dir. Veri yeniden tarih verilerek
güncellenmez; mevcut 15 dakikalık fiyat ve 6 saatlik kaynak tazelik kuralları
korunur. Başarılı iş akışı skorlu yatırım araştırması anlamına gelmez.

## Öncelikli şirketlerin takip eden koşularda doğrulanması

Kayıtlı yedi öncelikli aday yalnız ilk incelenmiş değerleme
raporu ve sabit finansal run ID ile başlatılır. İlk başarılı
öncelikli kaynak toplaması, `priority-lineage.json` içine
çalışma kimliğini, aynı raporun SHA-256 değerini, aday planının
SHA-256 değerini ve başlangıç arşivinin kimlik/özetlerini
kaydedebilir. Sonraki koşu yalnız indirilen önceki
`valuation-source-state` paketinde bu zincir güncel
raporla birebir örtüşüyorsa öncelik kullanır. Uyuşmazlık
puan veya veri kabulünü gevşetmez; kaynak bütçesi normal
rotasyonla işlenir ya da bozuk rapor durumunda çalışma
durdurulur. Bu mekanizma yeni SEC verisi veya yeni
yedi şirket puanı üretildiği anlamına gelmez.

## Manuel tekrar

İstenirse GitHub Actions > **Canlı değerleme kaynakları** > Run workflow:

- Branch: `main`
- `source_run_id`: gerçekten veri üretmiş finansal çalışmanın sayısal run ID'si
- `valuation_resume_run_id`: boşsa uygun önceki değerleme işi otomatik bulunur
- `max_new_requests`: varsayılan `51` (kontrollü alternatifler 0–501)

Örnek kaynak koşusu: `42455760184` (8 Kasım 2026, sequence 10).
Bu örnek geçmiş bir kayıttır; güncel fiyatın bugün doğrulandığını göstermez.

Çıktı `valuation-source-state` artifact dosyasında tutulur.
`report.json` içinde `identity_states`, `share_states`, `price_states`
ve `history_states` ayrı kontrol edilir. Veri toplama tamamlanmasa bile
nedenleri kayıtlarda korunur.

## Nihai puanlamaya geçiş

Bu kaynaklar ile mevcut 100 şirketlik finansal batch,
sonraki yıl karşılaştırması ve piyasa riski **aynı kaynak kesim tarihinde**
doğrulanıp birleştirilmelidir. `score-report` altı bileşenin tüm girdilerini
zorunlu kılar; bilinmeyen alanlara puan verilmez. Sektör ve hisse sınıfı
engelleri gevşetilmeden en az bir gerçek şirketin 100 puanlık hesaplama
zincirini geçtiği canlı raporla gösterilmelidir.

Test: `tests/test_valuation_live_workflow.py`. CI başarısı canlı kanıt
toplandığı veya ilk puan üretildiği anlamına gelmez.

## 100 puanlık araştırma skoruna kaynak devri

Değerleme durum paketi, kaynak alınan SEC çalışmasının sayısal ID bilgisini
`financial-source-run.json` dosyasında taşır. Sonraki
`İlk gerçek 100 puan araştırma skoru` iş akışı bu kimlikle tam olarak
aynı finansal batch ve özgün kaynak arşivini indirir. Farklı koşuların
finansal verileri sessizce karıştırılmaz.

Skor akışı, sektör modeli desteklenen, dokuz temel girdisi mevcut ve
fiyat/hisse sınıfı/geçmiş fiyatı kanıtlanmış adaylar için SEC'de açık
önceki yıl dönemini arar. Önceki yılı takvim çıkarımıyla uydurmaz.
Mevcut `research-batch` kaynak sırası ve `build_current_scores.py`
modeli kullanılır. Sonuç `first-live-score-evidence` artifact dosyasında
saklanır; puan oluşsa bile yatırım onayı ve MVP kabulü verilmez.
