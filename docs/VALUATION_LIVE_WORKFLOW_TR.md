# Canlı değerleme kaynağı toplama — ilk prototip

Bu iş, ana 100 şirketlik SEC finansal veri toplamasından ayrıdır. Güncel
hisse sayısı, özgün hisse sınıfı belgesi, piyasa fiyatı ve fiyat geçmişi
kanıtlarını toplar. Hiçbir puanlama, sektör kabulü veya gerçek işlem yapmaz.

## Çalıştırma

1. Önce GitHub Actions **Canlı 100 şirket kabulü** çalışmasının
   `live-acceptance-evidence` artifact dosyasının mevcut olduğunu doğrula.
   Örnek doğrulanmış kaynak çalışma: `42455760184` (sequence 10,
   8 Kasım 2026). Bu sayı yeni çalışma yapılınca güncellenmelidir.
2. Actions altında **Canlı değerleme kaynakları** iş akışını `main`
   dalında manuel çalıştır.
3. `source_run_id` alanına kaynak iş akışının gerçek sayısal run ID'sini gir.
   İlk denemede `max_new_requests=51` kullan. Erişim hatası varsa
   aynı taramayı bilinçsizce büyütme.
4. Sonraki değerleme taramasında `valuation_resume_run_id` alanına bir önceki
   **değerleme** çalışmasının sayısal run ID'sini yaz. İlk çalışmada boş
   bırak. Böylece mevcut kaynak ve negatif sonuç kayıtları silinmeden
   tekrar kullanılabilir. Yeni kaynak `source_run_id` değeri finansal
   taramanın; `valuation_resume_run_id` ise değerleme taramasının ID'sidir.
5. Sonuçtaki `valuation-source-state` artifact dosyasını ve Türkçe
   Actions özetini kontrol et. `report.json` içindeki `identity_states`,
   `share_states`, `price_states`, `history_states` ayrı ayrı okunmalıdır.

Kaynak dosyalar `data/valuation-import/live-sources` altına indirilir,
SHA ve içerik bütünlüğü `read_bundle` ile denetlenir. Eski gözlemler
güncelleştirilmiş gibi gösterilmez. Değerleme verileri
`data/valuation-current` içinde tutulur; önceki finansal çalışma
veritabanlarına yazılmaz.

## Kabul kapısı

Başarılı workflow = yalnız işlemin başarıyla tamamlanmasıdır.
`mvp_accepted=false`, `investment_approved=false`, `total_score=null`
korunur. Hisse sınıfı, güncel fiyat ve finansal girdiler ayrı denetlenmeden
yatırım raporu veya öneri üretilmez. Bu paketten sonraki aşama,
sektörü desteklenen ve yeterli dokuz temel finansal kalemi olan şirketlerde
aynı kesim tarihinde karşılaştırma/değerleme/skor raporunu bağımsız
testlerle doğrulamaktır.

## Test kanıtı

`tests/test_valuation_live_workflow.py` manuel tetik, ana dal,
kaynak artifact, SEC kimliği, istek üst sınırı ve güvenli çıktı
kontrollerini kapsar. PR CI ve gerçek Actions denemesi ayrı kanıtlardır;
PR testleri başarıyla geçse bile ilk gerçek fiyat toplama henüz yapılmış
sayılmaz.
