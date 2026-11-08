# Canlı değerleme kaynağı toplama — ilk prototip

Bu iş, ana 100 şirketlik finansal taramadan bağımsızdır. SEC şirket kimliği,
özgün hisse sınıfı belgesi, fiyat ve piyasa geçmişi için kaynak kanıtı toplar.
Skor, sektör kabulü, alım/satım emri veya MVP kabulü üretmez.

## Otomatik çalışma

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
