# Development status

## 5 Kasım 2026 — Otomasyon ve kesintili kaynak teşhisi (PR incelemesinde)

Yönetim denetimi: Tek merkez görev saatlik zamanlı olmasına rağmen son koşu
`failed` kaydedilmiş ve görev kapalıydı. Kesin çalışma hatası bu kayıttan
çıkarılamıyor; saatlik otomasyonun sürekli bir sunucu işlemi olmadığı teyit
edildi. Görev yeniden açıldı ve çalışma talimatı her oturumda tek sınırlı
değişiklik, kalıcı checkpoint, kilit denetimi ve kanıt raporu üzerine
daraltıldı. Bu değişiklik otomasyonun sonraki koşusunun başarılı olduğunu
tek başına kanıtlamaz.

Veri erişim engeli: GitHub Actions 42002017777 koşusunda yalnız 3/6
kaynak erişilebildi; kaynak tanısı SEC uçlarını ayrı gösteriyor. Mevcut
`live-acceptance.yml`, SEC kimlik dizini, submissions ve companyfacts
üçünün eşzamanlı erişimini tüm veri toplamanın ön şartı yapıyordu.
Oysa ilk metadata aşaması submissions yanıtıyla kısmen ilerleyebilir.
Yeni dar kapı yalnız `sec_submissions` erişimini önkoşul yapıyor;
diğer kaynakların yokluğunu tanıda koruyor. Finansal doğrulama,
adi hisse sınıfı ve toplam MVP kabulü için hiçbir kapı kaldırılmadı.
SEC submissions da erişilemezse işlem yine güvenli biçimde başlatılmaz.

Bu dalda değişenler: canlı kabul Actions kapısı ve ilgili sözleşme testi.
Yerel regresyon ve GitHub CI sonucu henüz doğrulanmadı; PR birleşimi
başarılı CI sonrasına bırakılacak. 24/100 son kalıcı metadata sayımıdır;
yeni doğrulanmış finansal alan ve skor hâlâ sıfırdır.

Sonraki görev: PR testlerinin sonucunu incelemek; ardından erişilebilir
SEC submissions ortamında kayıtlı 24/100 checkpointinden devam etmek,
üstveri, finansal alan ve skor sayılarını ayrı kaydetmek.

## 5 Kasım 2026 — Canlı kabul iş akışı birleşimi ve ilk devam kontrol noktası

PR #24 main'e birleştirildi:
https://github.com/fatalvayn-dot/us-equity-research/pull/24
Kaynak commit `af45bde650f1b47ae622dc3ac5a98429bb236f11`, birleşim commit'i
`7ec7bb09ad09c805f7b87ce0979e9b7e9bb323b5` değerindedir. Aynı işi yapan
taslak PR #23 ve yinelenen PR #25 kapatıldı; eski `radar-agent` deposuna
dokunulmadı.

Foundation tests koşusu `42002017637`, Python 3.11, 3.12 ve 3.13 işlerinde
başarılıdır. Kesin kaynak committeki canlı kabul koşusu `42002017777` de
başarılı tamamlandı; GitHub yürütücüsü 3/6 kaynak grubundan yanıt aldı. Üç
zorunlu SEC kaynağı birlikte erişilebilir olmadığı için finansal toplama
başlatılmadı. Erişim kanıtı 14 gün saklanan `live-source-preflight` artifact'i
`13403240759` içindedir. Bu koşu şirket finansallarını doğrulamadı.

Yerel devam çalışması aynı 100 adayı ve yeni bir durum dizinini kullandı. 24
şirket için güncel SEC submissions yanıtı ile yıllık bildirim üstverisi
kaydedildi; tamamı `metadata_available_legal_type_pending` durumundadır.
Finansal belge ve alan aşamasına geçilmeden işlem kesildi: 24/100 şirket
üstverisi, 24 ham yanıt gözlemi, 0 finansal alan ve 0 puan. Tamamlanmış
`report.json` bulunmadığından taşınabilir kanıt dışa aktarımı açık hata ile
reddedildi; bu kısmi durum canlı kabul sayılmadı.

Yerel birleşik ağaçta iş akışı sözleşme testleri 4/4 ve tam regresyon 674/674
başarılıdır (Python 3.12.14). İlk tam regresyon çağrısı `PYTHONPATH` olmadan
51 içe aktarma hatası verdi; doğru ortamla tekrarlandı ve geçti.

Sonraki tek görev: etkin süreç bulunmadığı ve kayıtlı kira süresi dolduğu
doğrulandıktan sonra `data/live-acceptance-20261105` durum dizininden aynı
komutla devam ederek 100 şirket üstverisini tamamlamak; ardından yıllık belge
ve finansal alan aşamasının sonuçlarını ayrı sayımlarla kaydetmektir.

## 5 Kasım 2026 — GitHub Actions üzerinde devam ettirilebilir canlı toplama

Başlangıç main: `d99cf7967db61fcdb1a2860285a4a512cf17e754` (PR #22).
Açık PR yoktu. PR #22 kaynak commitinin Foundation tests koşusu
`41975883291` başarılıydı.

Mogadişu saatiyle 12:21'de altı kamu kaynağından ikisi yanıt verdi.
SEC kimlik dizini ile Nasdaq’ın kendi liste dosyası erişilebilirdi. SEC
bildirimleri, Companyfacts, Yahoo fiyatı ve Nasdaq’ın diğer borsalar listesi
zaman aşımına uğradı. Kanıt: `docs/evidence/live-source-preflight-2026-11-05-1221.json`.
Bu yoklama şirketlerin finansal verisini doğrulamadı.

Yeni iş akışı erişim kanıtını ayrı saklar. Üç SEC adresi erişilebilir olduğunda
aynı depodan açılan ilgili PR'da 100 adayın bildirim üstverisi ile en fazla 5 yeni
yıllık belge ve 30 finansal alan denenir. Elle başlatılan çalışmada belge ve
alan bütçesi seçilir. Önceki durum paketi verilirse mevcut kontrol noktaları
kullanılır. Veri toplama ve kanıt aktarımı iş akışında ayrı adımlardır.

Güncel 100 şirket kabulü bekliyor. Mali veri toplamasının ardından güncel
liste/adi hisse teyidi, karşılaştırma, piyasa verisi ve puanlama da doğrulanmalı.

## 5 Kasım 2026 — Canlı kabul öncesi kaynak erişimi

Başlangıç main: `3226b2b3cf8b391ef09469070193123b31321292` (PR #21).
Açık PR yoktu. Ana dal CI çalışması 41963433843 başarılıydı.
`feat/live-source-preflight` dalında canlı kabul için gerekli kamu adreslerini
mevcut HTTP istemcisiyle yoklayan `scripts/check_live_sources.py` eklendi.
Yanıt alınırsa zaman, uzunluk ve SHA-256 kaydedilir. Bu araç içerik doğrulaması
yapmaz. Hatalarda istemcinin sınıflandırmasını ve varsa HTTP kodunu kaydeder.
Bir adres yanıt vermezse süreç 1 çıkış kodu döndürür ve raporu saklar.

Mogadişu saatiyle 08:42'de SEC kimlik, SEC bildirim, SEC Companyfacts, Yahoo
fiyat ve iki Nasdaq Trader liste kaynağı yoklandı. İki liste için ikinci resmi
adres de denendi. Sekiz deneme zaman aşımına uğradı. Bu oturumda erişilen
kaynak 0/6, canlı verisi doğrulanan şirket 0/100 ve kabul durumu beklemede.
Kanıt: `docs/evidence/live-source-preflight-2026-11-05.json`.
SEC HTTP istemcisi, Nasdaq, fiyat ve MVP kapsamındaki 83 yerel test geçti.

Erişimi olan çalışma ortamında aşağıdaki komutla yeniden ölç:

```sh
PYTHONPATH=src python scripts/check_live_sources.py \
  --user-agent "$SEC_USER_AGENT" --output data/live-preflight.json
```

Ardından `docs/evidence/common100/candidates.json` ile README'deki canlı
`mvp-run` komutunu yeni durum dizininde çalıştır. Kesinti olursa aynı durum
dizininden devam et. Güncel liste, karşılaştırma ve değerleme kanıtlarını ayrı
aşamalarda tamamla. PR #21'in 18 puanlı, 82 puansız raporu tarihli prototip
olarak kalır.

## 5 Kasım 2026 — Özgün SEC bilanço denklemiyle yükümlülük doğrulaması

Dal: `feat/liabilities-equation-proof`; başlangıç main
`37e41efe5d5e5af1a16f9d0dd3b3c8c8d2adc7cc` (PR #20 birleşimi). Başlangıçta
açık PR yoktu; Actions `41930220540` Python 3.11/3.12/3.13 üzerinde 666 testle
başarılıydı. AGENTS, proje özeti ve önceki durum okundu. Türkçe rapor sistemi
yeniden yazılmadı; eski radar-agent deposuna dokunulmadı.
PR: https://github.com/fatalvayn-dot/us-equity-research/pull/21
Kaynak commit: https://github.com/fatalvayn-dot/us-equity-research/commit/8956660acb39e3188721aa58ef144f89bc36f12b
Kaynak ağacı `45900b14bed3d867538a5795c631b6931c7d5b8d`, 670 testin geçtiği
yerel ağacın birebir aynısıdır. Kaynak CI:
https://github.com/fatalvayn-dot/us-equity-research/actions/runs/41962692911 —
Python 3.11, 3.12 ve 3.13 üzerinde 670 test ile CLI durum kontrolü başarılı.

v0.35.0, SEC Companyfacts içinde literal `us-gaap:Liabilities` bulunmayan beş
desteklenen şirket için özgün yıllık iXBRL bildiriminden dar bir bilanço denklemi
kanıtı üretir. CIK, dönem, USD, boyutsuz olgu, toplam bilanço eşitliği ve özkaynak
kapsamı tam eşleşmelidir. Geçici veya itfa edilebilir özkaynak, açıklanamayan
kontrol gücü olmayan pay, ayrı kapsam ya da negatif sonuç kanıtı reddeder. Bu yol
yalnız literal olgu temiz biçimde yoksa çalışır; ilk geçerli kaynak seçimini
değiştirmez ve otomatik muhasebe ikamesi sayılmaz.

Kayıtlı özgün bildirim mutabakatı: AMD 13.927.000.000 USD, ADI 14.176.957.000
USD, CDNS 4.678.967.000 USD, ADSK 9.422.000.000 USD ve INTC 85.069.000.000 USD.
INTC toplam özkaynağı ayrıca 114.281.000.000 USD adi özkaynak ile
12.079.000.000 USD kontrol gücü olmayan payın toplamı olarak doğrulandı. Beş
seçilmiş Nasdaq değeri SEC denklemiyle tam eşleşti; reddedilen şirket yoktu.
Kanıt: `docs/evidence/liability-equation5` ve
`tests/fixtures/liability-equation5-sources` (manifest SHA-256
`4f776e90ae382c4e6f3075f0541fb149f7fdf344303c38438d20b5602dd7812e`).

Tarihli 3 Kasım prototipi aynı kesim anında 18 puanlı, 82 puansız ve dört zorunlu
incelemeli sonuç verecek şekilde yeniden üretildi. Beş yeni puan ADI 74, AMD 67,
CDNS 65,5, ADSK 57 ve INTC 20,5'tir. Puanların tamamındaki 180 yıllık finansal
işlenen özgün bildirimle eşleşti. JSON, Markdown ve HTML geçici klasörde bayt bayt
aynı üretildi; JSON SHA-256 değeri
`abd2b819069ccf55544eefa820acb8221634e2dcd64e67f90110ce02225d6983`.
Bu çalışma sıfır yeni HTTP isteği yaptı; 2–3 Kasım kayıtlarını kullanır ve güncel
100 şirket kabulü değildir.

İlk odaklı test çağrısı test modülü yolunu içermediği için içe aktarma aşamasında
durdu; `PYTHONPATH=src:tests` ile düzeltildi. Sonraki rapor denemesinde yinelenen
`raw_sha256` anahtarı, HTML sunumunda doğrudan doğrulamaya özgü alan beklentisi ve
tekrar üretim çıktısında datetime serileştirmesi ayrı ayrı görüldü ve giderildi.
İlk 41 odaklı testte eski 87 puansız kart beklentisinin tek satırı kaldı; 18/82
sözleşmesine güncellendi. Son odaklı koşu 41/41 (38,365 saniye), tam yerel
regresyon 670/670 geçti (295,268 saniye, Python 3.12.14). CLI durum kontrolü ve
`git diff --check` başarılı. Kaynak commitin üç sürümlü uzak CI'ı başarılıdır;
bu durum kaydını içeren son commit de birleşmeden önce ayrıca doğrulanacaktır.

Kalan engel: PLTR için doğrulanmış güncel adi hisse adedi yok; ON girdisi geçersiz.
Bu iki durum puansız kalmalı. Sonraki tek görev, yeni bir durum klasörü ve çalışmanın
yapıldığı zamana ait kaynaklarla devam ettirilebilir 100 şirket uçtan uca kabulünü
çalıştırmak; başarı, eksik ve hata sayılarını eski kayıtlarla karıştırmadan kaydetmek.

## 5 Kasım 2026 — Ek tercihli sembolleri olan adi hisselerin kesin sınıf doğrulaması

Dal: feat/share-class-corroboration; başlangıç main
48ae648975d1ca362ff9d331a82625bfea4ebefd (PR #19). AGENTS, proje özeti,
durum, uzak main, açık PR ve Actions incelendi. Açık/çakışan PR yoktu; PR #19
Türkçe raporları tamamlamış ve 662 testli CI ile birleşmişti. Türkçeleştirme
yeniden yapılmadı. Eski radar-agent deposuna dokunulmadı.
PR: https://github.com/fatalvayn-dot/us-equity-research/pull/20
Kaynak commit: https://github.com/fatalvayn-dot/us-equity-research/commit/90d3426ac0b864be6767ecc135096ace153cef59
Kaynak ağacı 18abf252413da6cb89d34e7926c91359347601c7, 666 testin geçtiği
yerel 9d5fa46 ağacıyla birebir eşittir. Kaynak CI:
https://github.com/fatalvayn-dot/us-equity-research/actions/runs/41929668290 —
Python 3.11/103.164s, 3.12/147.351s ve 3.13/142.878s üzerinde 666 test ve
CLI durum kontrolü başarılı. Son belge commitinin CI sonucu ayrıca kontrol edilecek.

v0.34.0, SEC submissions içinde adi hisse sembolünün yanında tercihli veya başka
adi hisse dışı sembol bulunmasını otomatik sembol uyuşmazlığı saymaz. İstenen
sembol özgün dönemsel bildirim kapağında açıkça adi hisse olmalı; diğer her sembol
aynı kapakta tercihli/depositary/borç benzeri adi hisse dışı menkul olarak kesin
eşleşmelidir. İkinci bir adi hisse, bilinmeyen başlık, eksik kapak eşlemesi veya
birden çok olası eşleşme reddedilir. Sembol noktalaması dönüştürülmez. SEC
submissions ile kapak farklı yazım kullanıyorsa yalnız tek eşleşmemiş adi hisse
dışı çift kabul edilir ve iki özgün sembol ayrı ayrı kanıtta tutulur.

Gerçek sınırlı doğrulama ORCL ve MCHP için 11 yeni kamu GET isteği yaptı:
www.sec.gov 3, data.sec.gov 4, Yahoo 4. İki kesin CIK, iki fiyat ve iki yıllık
fiyat geçmişi geçerliydi. İlk koşuda MCHP geçti; ORCL, submissions `ORCL-PD`
ile kapak `ORCL PRD` yazımı farklı olduğu için geçmedi. Dar ve denetlenebilir
kapak kuralından sonra aynı 11 ham yanıtla sıfır GET tekrarında iki adi hisse
sınıfı da doğrulandı. MCHP ek `MCHPP` depositary/preferred sembolü kapakta birebir;
ORCL iki özgün etiketi ve tek-eşleşme gerekçesini saklar. Ham kaynak aralığı
2026-11-04T22:44:05.147133+00:00–22:44:41.798655+00:00; başlık/kimlik bilgisi
yok, 11 gözlemli sıkıştırılmış kaynak SHA-256 değeri
0e581a6cce000afd65b851fb859552629796a96ef3d5fdfa7b60cc9ab68ffd3b.
Kanıt: docs/evidence/share-class2 ve tests/fixtures/share-class2-sources.

Odaklı 72 birim/entegrasyon/kayıtlı-veri testi geçti (27.986s). Eski tarihli
7 şirket kanıtı değiştirilmedi; yeni kural altında ORCL, özgün kapak yanıtı yoksa
`pending_source_collection` kalır. Tek sembollü eski 13 puanın JSON çıktısı
birebir korunur. İlk tam regresyonda 666 testten 665'i geçti; ortak örnek çıktısına
iç doğrulama için eklenen `listed_security` alanı eski kayıtlı JSON sözleşmesini
değiştirmişti. Alan yalnız yeni doğrulayıcı açıkça istediğinde üretilecek şekilde
daraltıldı; finansal sayı veya sınıf sonucu değişmedi. Son tam yerel regresyon
666/666 geçti (133.482s, Python 3.12.14); CLI ve `git diff --check` ayrıca
başarılı. Kaynak commitin uzak CI'ı başarılı; bu durum kaydını içeren son commitin
CI'ı birleşmeden önce ayrıca çalıştırılacak.
Bu iki şirketlik doğrulama tam 100 şirket kabulü veya yatırım onayı değildir.

Kalan engel: PLTR için doğrulanmış güncel adi hisse adedi yok; ON girdisi geçersiz.
Beş desteklenen adayın literal Liabilities bağımsız teyidi eksik. Sonraki tek görev,
özgün güncel bildirimlerde toplam yükümlülüğü oluşturan kalemleri kavramsal ve
aritmetik olarak ayrı bir kanıt politikasıyla doğrulamak; güvenli değilse adayları
puansız bırakmak. Ardından güncel, devam ettirilebilir 100 şirket kabulü çalıştırılacak.

## 5 Kasım 2026 — Türkçe radar ve raporlar

Dal: feat/turkish-reports; başlangıç main 2136438acb64c2e49319006a239a78fb1c3ef53d
(PR #18). AGENTS, proje özeti ve önceki durum okundu. Başlangıçta açık PR yoktu;
main üzerindeki son Foundation tests çalışması 41824775204 başarılıydı.
Kullanıcının Türkçe dil kararı AGENTS ve PROJECT_BRIEF içine kaydedildi.
PR: https://github.com/fatalvayn-dot/us-equity-research/pull/19
Kaynak commit: https://github.com/fatalvayn-dot/us-equity-research/commit/0de9fd773a89fa00cae8161d5f6a999b56fa7380
Uzak e5c38077ea07c1ef3dbb8a04c72d98a6812f6c92 ağacı, 662 testin geçtiği yerel
a81d1b5 ağacıyla birebir eşittir. Son belge commitinin CI sonucu birleşmeden önce
kontrol edilecek; bu kayıt tek başına uzak CI başarısı iddiası değildir.
Eski radar-agent deposuna dokunulmadı.

Radar ve finansal HTML ekranları ile araştırma, finansal, fiyat, yıllık karşılaştırma,
değerleme ve karma tarihli finansal raporların Markdown çıktıları Türkçeleştirildi.
Bileşen, model, durum, eksik veri ve kaynak hatası açıklamaları ortak sözlükten gelir.
Bilinmeyen tanılar özgün koduyla görünür; başarıya dönüştürülmez. Filtre değerleri ve
JSON sözleşmesi özgün kalır. Finansal değerlendirme, puan modeli, ilk geçerli kaynak
sırası, dönem/para birimi kuralları ve kabul kapıları değiştirilmedi.

Türkçe kayıtlı çıktılar: docs/evidence/turkish-reports/. Tekrar üretim:
PYTHONPATH=src python scripts/export_turkish_reports.py
Bu komut ağ isteği yapmaz; özgün tarihli JSON raporlarını yeniden görüntüler.
Önceki İngilizce raporlar ve özetleri tarihli kanıt olarak korunmuştur. Yedi yeni
HTML/Markdown çıktısının ve beş girdi dosyasının SHA-256 özeti manifestte yer alır.

Kontrol: tam kaynak paketinden build_current_scores ile aynı kesim zamanında yeniden
üretilen JSON, önceki current-score100 JSON kaydıyla birebir eşittir. 100 aday,
13 puanlı, 87 puansız ve dört kritik inceleme değişmedi; kaynak tarihleri korunmuştur.
Yeni canlı istek: 0. Bu çalışma güncel 100 şirket kabulü veya yatırım onayı değildir.

Hata ve düzeltmeler: ilk 658 testlik koşuda dört sunum testi eski İngilizce metni
ve eski HTML görünümünü beklediği için başarısız oldu; finansal sayılar değişmedi.
Dil beklentileri güncellendi; eski HTML kanıtının manifest doğrulaması korundu.
662 testlik sonraki koşuda 661 test geçti; fiyat raporunda kalan bir İngilizce
metin beklentisi düzeltildi.
İncelemede data-gate niteliğinin çevirisinin filtreyi bozabileceği görüldü; makine
kodu korundu ve buna özel kontrol eklendi. Türkçe dışa aktarma ilk denemede yanlış
.json yolu ve fiyat raporunun farklı tarih anahtarı nedeniyle durdu; özgün .json.gz
ve generated_at sözleşmeleri kullanılarak düzeltildi. Kaynak dosyalar değişmedi.
İlk git push otomatik onay incelemesinde reddedildi. Önceki açık GitHub geliştirme
ve PR yetkisi proje kaynaklarından doğrulandı; değişen 31 dosyada gizli bilgi
örüntüsü bulunmadı. Doğrulama sonrası normal gönderim, komut satırında GitHub
kimlik doğrulaması olmadığı için başarısız oldu. Mevcut GitHub bağlantısıyla aynı
kaynak ağacı ayrı dala aktarıldı; yeni hesap erişimi istenmedi.

Doğrulama: dört yeni Türkçe görünüm/sözlük testi ve 30 fiyat testi başarılı.
Son tam yerel regresyon: 662/662, 131.683 saniye, Python 3.12.14. CLI status
ve git diff --check başarılı. Sekiz Türkçe çıktı/manifest dosyası yeniden
üretimde birebir aynı; beş girdi ve yedi çıktı özeti doğrulandı. Uzak CI bu PR
açıldıktan sonra, birleşmeden önce tam commit üzerinde kontrol edilecek.

Devam düzeni: mevcut US Equity Research – Tek Merkez saatlik görevi
başlangıç kontrolünde duraklatılmış bulundu. Kullanıcının devam talimatına göre
Türkçe dil kuralı eklenecek ve bu PR tamamlandıktan sonra mevcut sıklıkla yeniden
etkinleştirilecek. Eski radar ve sanal portföy görevleri açılmayacak.

Sonraki görev değişmedi: yükümlülük ve hisse sınıfı doğrulama açıklarını özgün güncel
bildirimlerle çöz; ardından tam, güncel ve devam ettirilebilir 100 şirket kabulünü
çalıştır. Kapsam genişletme, geçmiş performans iddiası veya sanal portföy açma yok.

## 2026-11-03 — Current-market 22-candidate collection and 13-score common100 prototype

Branch feat/current-score-cohort from main 8060ed36dbb6d9de7844e1c75402a8d45df9650b
(PR #17). Read AGENTS, PROJECT_BRIEF, development status; checked remote main,
open PRs and Actions. No conflicting open PR, main matched, final PR #17 CI
41579639000 passed 646 tests on three versions. Legacy repository untouched;
pre-existing unrelated temporary source files preserved and excluded.
PR: https://github.com/fatalvayn-dot/us-equity-research/pull/18
Source commit: https://github.com/fatalvayn-dot/us-equity-research/commit/97c329d6812c527cfd8c09540428c484dbc92589
Source tree 328f27c7af666d922f6e8f6380f15cb0243020f7 equals local a57142e;
all 59 uploaded Git blobs independently matched before branch publication.
Code/data review: PR comment 6596469421. Source CI:
https://github.com/fatalvayn-dot/us-equity-research/actions/runs/41585839972 —
658 tests and CLI status passed on Python 3.11/131.653s, 3.12/112.885s and
3.13/142.644s. Machine-readable evidence: docs/evidence/current-score-actions.json.

v0.33.0 adds immutable score-input provenance: canonical digests, original batch
generation dates, selected-source counts and observed-time ranges, plus missing/
additional comparison identities. Future/naive batch dates or future selected
observations cannot score. Caller freshness/approval flags are not adopted.
HTML/Markdown visibly distinguish retained financials from refreshed market data;
no report generation is presented as a full-100 financial refresh. A fixed,
sanitized validation-stage code identifies the exact rejected financial operand.
No numeric point bands, sector whitelist, source priority or model gates relaxed.
A generic script builds portable gzip JSON/Markdown/HTML plus checksum manifest,
with explicit cutoff and source/output isolation; no network during report build.

Real bounded collection on the 22 input-ready common100 candidates: 103 public
GET invocations (www.sec.gov19, data.sec.gov42, Yahoo42; internal retries excluded).
22 exact SEC identities and valid prices, 20 histories, 18 original-share class
reconciliations. PLTR lacks required disclosed shares; ORCL and MCHP fail exact
ticker/class matching; ON has invalid share inputs. PLTR/ON histories remained
unstarted, not falsely attempted. Warm cache-only repeat: zero GETs and identical
accepted share/price/history values, original dates and evidence. Raw bundle:
tests/fixtures/valuation22-sources (103 observations, 33 parts, 16,801,866 compressed
bytes). No operational SQLite, credentials or request headers published.

Score report cutoff 2026-11-03T05:36:21.308165+00:00: exact common100 rows,
13 scored research hypotheses / 87 unscored / 4 critical mandatory reviews.
13 scores: MU87, INTU78, MPWR78, SWKS68, MSFT66.5, CRM66, MRVL64.5, TXN63,
NOW62, AMAT59.5, TYL55.5, AAPL53, SNPS53. These are dated model hypotheses,
not investment approval or return promises. Five additional candidates (AMD,
INTC, ADI, CDNS, ADSK) fail current SEC confirmation of literal Liabilities and
stay unscored. No alias/equation/source replacement introduced to manufacture
those scores. Diagnostic replay found the literal Liabilities concept absent in
all five current companyfacts snapshots; this is missing independent confirmation,
not evidence that Nasdaq's selected values are wrong. Recorded annual documents
also lack an accepted exact value (four concept_not_disclosed, INTC period_or_scope_mismatch).
These source facts are preserved in the PR follow-up; no new request for diagnosis. Other unqueried valuation sources remain missing/unstarted.

All 130 operands for the 13 scored companies (nine current financial fields plus
prior contract revenue each) match original annual iXBRL exact CIK/period/USD/
concept contexts, using original source bodies. No new HTTP for reconciliation.
Fresh SEC companyfacts independently confirms those values during score build.
Original annual check details: current-score100/original-annual-checks.json.
Retained financial batch remains 988 original observations; comparison remains
534 per side / 514 growth results. This run refreshes 22 market/share inputs,
not all 100 financial histories. Report JSON/HTML/Markdown, original checks and
reproduction proof: docs/evidence/current-score100/. Collection/resume evidence:
docs/evidence/valuation22/. Old pilot scores and all earlier evidence preserved.

Validation: 24 focused scoring/provenance tests passed (0.265s), 10 focused
provenance/export tests passed after final display update (0.207s), actual 100-row
13-score raw replay plus cold/warm integration tests passed (15.999s). Fixed-cutoff
CLI reproduced JSON/Markdown/HTML byte for byte; final display builder rerun also
reproduced exactly. Full local regression 658/658 passed (127.197s, Python 3.12.14), with final
rejected-stage display changes additionally checked by the focused 10-test run.
The source commit CI passed; a final exact-head CI remains required after the
output-safety follow-up. Concurrent local timings are not benchmarks. These are
offline/recorded tests and Actions, not a fresh live 100-company acceptance.

Failures/corrections: first 653-test full run had 652 pass / one old report golden
comparison failure because additive provenance was new. Updated the legacy test
to separately assert the new audit and still compare EVERY old score/evidence field
unchanged; targeted replay passed. Subsequent 655-test full run passed (106.696s).
No observed old numeric score change. New 658-test regression includes two real-
collection tests and one safe rejected-stage test. No provider access bypass or
rate/quota override used; no fake missing-data zeros or unsupported-sector points.
The final follow-up atomically replaces report.json.gz and refuses to follow an
existing output symlink into retained raw evidence. Its focused two-test regression
passed locally (0.360s); the complete follow-up regression passed 658/658
(217.081s, Python 3.12.14). The exact follow-up head still requires full Actions.

Remaining/next concrete task: resolve literal liabilities confirmation gaps and
unsupported share disclosures using exact original current filings with a separately
validated adapter; preserve class ambiguity exclusions. Run a fresh, resumable
end-to-end 100-company acceptance across scope/financial/current market inputs,
with full missing/unattempted/error accounting and exact CI. Current prototype is
usable as a dated research report but full MVP acceptance remains unverified.
Do not expand scope or activate portfolios before acceptance and user usefulness
assessment. No user action required.

## 2026-11-03 — Exact common100 comparative inputs (v0.32.0)

Branch feat/common-annual-comparisons from main a7dc5accf719fdad405c70c1b783fc3c3090c301
(PR #16). Inspected AGENTS, PROJECT_BRIEF, status, remote main/development refs,
open PRs and Actions. Main matched, no open/conflicting PR, previous exact-head
CI 41577426677 successful. Legacy repository untouched; unrelated temporary
source-part files preserved and excluded.
PR: https://github.com/fatalvayn-dot/us-equity-research/pull/17
Source commit: https://github.com/fatalvayn-dot/us-equity-research/commit/c70fd5c89d6ba80da4851c08c88ec027cc296927
Verified source tree a83e66ad3e57f8918d49a698782d5c5a23955b5d equals local c6a5dda;
all 19 uploaded blobs independently matched their committed Git SHAs.
Source CI: https://github.com/fatalvayn-dot/us-equity-research/actions/runs/41579347214
All 646 tests and CLI status passed: Python 3.11/65.153s, 3.12/106.344s,
3.13/66.190s. Code/data review recorded in PR comment 6595624934.
Final documentation-head CI is checked before merge; no local/CI/live conflation.

Added candidate-driven comparative_replay and a bounded-scope offline script
accepting multiple original document cohorts and hash-validated public bundles.
Uses explicit aware as-of, exact symbol/CIK joins, exact document URL/hash/time,
latest available-at-cutoff companyfacts observations and existing strict annual
planner. No fiscal calendar guesses, tag aliases, source date rewrites or network
transport. Conflicting same-URL/timestamp bytes and overlapping document issuers
reject. Future observations cannot supply current operands. Source providers
retain Yahoo->SEC->Nasdaq->Finnhub first-valid behavior; later providers not
queried after SEC success. No environment credential access. Recorded replay
age is explicitly unrestricted inside this replay only; live six-hour policies
remain unchanged. Source/query dates and all arithmetic operands remain visible.

Exact new common100 plan: 100 identities retained on both sides, 96 ready annual
pairs; 534 current + 534 prior accepted values. 514 literal growth calculations,
20 nonpositive bases with unavailable growth ratio. GEV/SNDK/BLK fail original
annual-period verification; RY lacks a literal supported US-GAAP comparable pair.
All four stay visible, with no fabricated values/scores. New 17 issuers contribute
101 accepted values per side; 202/202 paired values matched exact original annual
iXBRL CIK/period/USD/concept contexts. All checks and original URLs/hashes/dates
are retained. This reconciles recorded public bodies; zero new HTTP requests,
not fresh live or historical-vintage acceptance. No new financial-model, common-
share or investment approval. No scores/ranks from this work. Old pilots preserved.

Artifacts: docs/evidence/common-comparative100/ (current/prior batches/plans,
report, explicit unresolved candidates, audit, original checks and reproduction
proof). Repeated fixed-cutoff CLI produced byte-identical numerical/audit outputs.
All 202 original-value checks were separately rerun with byte-identical reconciliation
JSON; every manifest input/output checksum passed. README provides exact rerun command. They feed existing comparison/score
interfaces without replacing main financial observations or weakening model gates.

Tests: 14 focused tests passed (2.205s); full local 646/646 passed (98.747s,
Python 3.12.14). Covers wrong identity/currency, missing/conflicting raw references,
future observations, exact date/hash selection, stale recorded replay labeling,
empty/unresolved candidates, no network, ordered source stop, deterministic
synthetic rerun and source/output isolation. Actual ADBE/INTU/TYL annual bodies
reproduce 36 paired operands; full 100 artifact reproduces all 514 calculations.
Local tests are not Actions or live acceptance. Exact-head CI checked before merge.

Failures/corrections: initial replay incorrectly let live BatchRunner six-hour
freshness mark 433 old retained pairs stale, leaving 101 per side. Explicit
replay-only age policy corrected this; no live TTL relaxed or observation time
changed. An inspection command tried to read the still-uncreated output folder;
it was corrected after the collection finished. No source or user file removed.
First collection/warm behavior here is offline only, never counted as new live work.

Remaining blocker: latest sufficient financial operands, independently confirmed
critical facts, refreshed share counts/quotes/history and full current scored
100-company acceptance/CI are still required. Next concrete code task: refresh
valuation sources for supported-model candidates in the exact common100 plan,
join these current/prior batches, reconcile critical annual operands, produce
explained research scores and an explicit end-to-end acceptance report. Keep
special-sector/unknown and incomplete scores withheld. MVP remains unaccepted.

## 2026-11-03 — New 17-company financial collection and mixed 100-cohort continuation

PR: https://github.com/fatalvayn-dot/us-equity-research/pull/16
Source commit: https://github.com/fatalvayn-dot/us-equity-research/commit/3ff708b1dffe97d338d7f239d2ebea617f1602ad
Source tree de3be0af1f6ee68869da8d0b519c2383311a00ce matches local 6a4350c;
each uploaded Git blob SHA independently matched before branch publication.
Source CI: https://github.com/fatalvayn-dot/us-equity-research/actions/runs/41576906725
631 tests and CLI status passed: Python 3.11/109.290s, 3.12/124.608s,
3.13/111.637s. Manual review additionally required cached responses to pass
transport origin/credential validation and original maximum response-byte bounds.
These checks now apply before any cached body can be returned; oversized cached
metadata remains invalid_data with zero GETs and zero accepted facts. One added
regression raises final suite size to 632; final local 632/632 passed
(93.212s, Python 3.12.14), and exact final-head CI is checked before merge. No copied secret, header or operational database in published evidence.

Branch feat/common-financial-cohort from main
1610fdeccb928d2dee15d9e77819c4810e73c59b (PR #15). Read main/open PRs/Actions,
AGENTS, PROJECT_BRIEF and status; no open/conflicting PR at start, prior exact
Actions 41566957370 passed 614 tests on all three supported Python versions.
Legacy untouched. Existing unrelated temporary source-part files preserved.

v0.31.0: mvp-run accepts public raw seed bundles. A six-hour policy skips stale/
future observations and reuses only original fresh-in-policy bodies, without
rewriting source times. First-valid Yahoo->SEC->Nasdaq->Finnhub selection remains.
Seed counts and archived transport reuses are separate from actual GET calls.
Writable state cannot be placed inside a source bundle; checksum errors cannot
initiate network calls. Completed runs explicitly finalize full metadata.

New financial-cohort CLI selects exact symbol/CIK entries across supplied dated
batches, refuses duplicate/ambiguous identities and wrong symbols, preserves
all original field values/periods/currencies/attempts/source/query dates and
keeps missing firms unresolved. Caller points/approvals cannot be adopted.
Input hashes and cohort generation dates are retained. JSON/HTML/Markdown
explicitly identify mixed dated inputs, not a new all-100 live scan. CLI input
and batch/report destinations cannot overwrite each other. No score/rank or
sector/model/investment approval is created by financial assembly.

Actual new-list gap: 17 identities in the common100 plan absent from the old
financial batch. Run attempted all 238 field jobs: 186 facts (SEC168, Yahoo14,
Nasdaq4), 141 arithmetic results, 52 pending jobs. All 17 have verified annual
starts/ends and selected facts; all financial/identity/unit references archived.
Cold run made 42 public transport GET invocations (internal retries/private
Finnhub excluded), reused 35 archived fresh-in-policy responses from 37 eligible
seeds; 2 dated Nasdaq membership seeds skipped outside six-hour policy.
No seed was presented as a fresh HTTP retrieval. Immediate zero-work resume used
zero public GETs, kept 186 facts/141 calculations and identical accepted fact
values, original source dates and evidence. First as_of 2026-11-03T03:50:01.038329+00:00.

New delta archive: tests/fixtures/common-financial17-sources/ (42 observations,
18 parts), with reused originals in common-extra-sources. No operational SQLite
published. Reports and traceability: docs/evidence/common-financial17/. All 186
selected values independently re-extract from the three providers' exact raw
responses. Original SEC document checks on ADBE/INTU/TYL matched 26 selected
values; one ADBE literal contract-revenue input absent in selection and original
remained unavailable. No tag substitution or zero fill.

100-candidate continuation selects 83 retained old issuers plus 17 new ones:
988 facts, 704 arithmetic results, zero scores. Reproducible mixed batch/report,
portable HTML and source hashes: docs/evidence/common-financial100/. The old
83 observations are NOT refreshed by merging. This does not establish a new
live-100 acceptance, latest comparative periods, current prices, valuation,
supported special-sector models or a new ranked report. Old dated two-score
pilot remains a separate artifact; no transferred/invented score.

Failures/recovery: first raw re-extraction test passed serialized date strings
to the strict FactRequest constructor; corrected the fixture to decode dates.
A concurrently started 630-test run reported this same test error; corrected
focused raw replay then passed (186/186, 6.619s). No observed financial mismatch.
Completed metadata/report had 17 issuers while one progress JSON showed 11;
rebuilt complete metadata from hash-verified submissions checkpoint bodies,
with no new requests/date changes, and added explicit final metadata snapshot
plus export count refusal. The original count and recovery are archived in
metadata-finalization-audit.json. No partial metadata was accepted as full proof.

Tests: 27 focused unit/seed/cohort/MVP tests passed (5.448s), corrected 630/630
full local regression passed (92.522s, Python 3.12.14). One additional recorded
original-document test makes final suite 631; source-head 631/631 full local regression
passed (94.134s, Python 3.12.14). Exact-head CI checked before merge. These are offline/recorded tests, not live CI.

Next concrete task: derive and collect exact current/prior annual periods for
the 17 new issuers and align the retained comparisons to this exact 100-company
plan. Refresh raw valuation/share/history inputs for eligible supported models,
reconfirm critical annual operands, then produce explained scores and a real
end-to-end acceptance report. Continue to withhold special-sector/unknown and
incomplete scores. Do not call this mixed continuation a completed MVP.

## 2026-11-03 — Source-bound 100-common-share sample (latest)

PR: https://github.com/fatalvayn-dot/us-equity-research/pull/15
Source commit: https://github.com/fatalvayn-dot/us-equity-research/commit/10111dc5324ab0c3f8f86df85d884cc225c8da7e
Published source tree de47302e07df4f104c70af62eb0eebcdb4bcddfa matches local a5399f4.
Source CI: https://github.com/fatalvayn-dot/us-equity-research/actions/runs/41557895303
All 613 tests and CLI status passed: 3.11/93.392s, 3.12/103.394s, 3.13/99.444s.
Final addition retains the new-plan price100 artifacts plus one exact raw-price
integration test (final suite 614). Targeted 2 tests passed in 3.849s; full final
head CI is checked before merge. Source/local full 613 must not be called 614.
Manual review: primary class cannot be joined across contexts/symbols/venues;
known date/exchange variants do not guess periods/classes. Sample approval is
separate from financial/model/legal approval, and all scores remain unavailable.
Source artifacts preserve original times; listed as-of limitations stay explicit.

Branch feat/source-bound-common-sample from main
0e3c513a86eca99b7e510b893793dba17e476406 (PR #14). Read AGENTS, PROJECT_BRIEF,
status, main/open PRs and Actions; no open/conflicting PR at start; exact-head
Actions 41546619377 passed 595 tests on three Python versions. Legacy unchanged.
Unrelated pre-existing temporary files preserved and excluded from staging.

Implemented v0.30.0 registered-common-sample-v1 and common-sample CLI. Rebuild
membership from original two Nasdaq directory bodies and exact SEC identity,
then current-in-policy SEC submissions and original latest annual registered
class/symbol/report-period/primary-exchange evidence. No caller approval flag
can admit an entry. Explicit fund/shell contraindications and unsupported
investment-company SIC routes remain under review; absent flags stay unknown.
The narrow sample gate never sets scope/legal/model/investment approval or a
score, nor guarantees immediate tradability or the full active universe.

101 candidates examined: existing 83 corroborated covers plus 18 explicit
replacement candidates. 100 source-bound common-class/listing matches selected;
TER remains under review because its original cover triggers the existing
unsupported/conflicting-structure guard. TYL was an explicit reserve, not a
relaxation or symbol substitution. Pool, exact 100 identities, per-company raw
URLs/hashes/dates and Markdown audit: docs/evidence/common100/. Original old
100-candidate financial/price reports and unresolved names remain preserved.
Development sample is technology-biased, not market-representative or a tested
investment strategy. No scores/financial completeness added by sample admission.

Live source work: 18 replacement SEC metadata + 18 original annual filings +
1 fresh SEC directory = 37 public observations; two original Nasdaq membership
files retained at 2026-11-02 observation times within the four-day policy.
Initial 17-name collection used 35 GET invocations; TYL reserve added 2; final
warm repeat used zero and retained identical evidence events. Raw extra bundle:
tests/fixtures/common-extra-sources/ (39 total observations), alongside original
tests/fixtures/mvp100-sources/. No copied credentials, headers or SQLite in Git.
A preliminary fresh Nasdaq retrieval failed api_error; individual endpoint
outcomes were not retained from that failed preliminary attempt. Do not count
recorded membership as a fresh successful Nasdaq download or hide that limit.

Date parsing now handles explicit four-digit month-first numeric and supported
English full/short title/upper-case month presentations. Unknown transforms,
invalid dates, two-digit numeric years and spoofed date-transform namespaces
cannot admit sample rows. Definitions checked against XBRL registry 3/4 primary
specifications linked in README. Primary exchange matching accepts documented
case/spelling variants only; exact company/class symbol matching remains.
Shared legal contraindication parsing factored without changing legacy scoring.
Public raw archive allowlist adds only official Nasdaq Trader text origins;
credential-bearing URLs remain rejected. CLI protects candidate and bundle paths.

Failures/recovery: first stricter base pass admitted 70/83 because 13 real Nasdaq
exchange labels used known case/name variants; explicit documented label matching
resolved these, without accepting NYSE Arca or changing CIK/symbol matching.
An operational source-index SQLite file failed integrity_check during rebuilding;
it was preserved. Source reconstruction now reads/hash-validates original Git
bundles directly, with no reliance on that corrupt operational cache. The
100-selection result was produced from original bytes, not repaired cache data.

Tests: 613/613 full local regressions passed (206.012s, Python 3.12.14), including
18 new unit/CLI/actual-cover replay tests. Earlier full 611 passed (143.431s).
These concurrent local timings are not performance benchmarks. Four actual
replacement covers (ADBE, INTU, TYL, unresolved TER) replay to exact report rows;
100 artifact identity/class/hash invariants and zero-GET proof checked. Existing
financial/valuation/scoring regressions retained. Exact-head CI checked before
merge; no live CI or full-MVP acceptance claim. Full common-sample CLI replay
then reproduced both report and candidate plan BYTE FOR BYTE, with zero network
calls. Proof: docs/evidence/common100/cli-reproduction.json.

A separate actual price-run now covers this exact new 100-company plan:
100/100 valid USD regular-session observations, 100 Yahoo quote GET invocations
plus one fresh SEC identity GET. All selected source/identity references were
archived. Immediate zero-budget repeat retained 100/100 with zero new quote or
identity GETs and identical values, source times and identity evidence. Sources:
tests/fixtures/common-price100-sources/ (101 observations); dated reports,
initial/resume proof and rerun command: docs/evidence/common-price100/, README.
Initial generated_at 2026-11-03T01:09:40.306623+00:00; no perpetual current-price
or executable-price claim. A new targeted integration test reconstructs all 100
prices from their exact raw bodies/identity and checks source currency/times;
full final-head CI is required. Earlier 613-test local full run predates this
one added test; do not mislabel it as a local full 614-test run.

Remaining/next concrete task: use docs/evidence/common100/candidates.json for
financial metadata/document/14-field and comparable-period collection, then
valuation/history refresh and scored report. Old 843 facts/576 calculations and
two dated pilot scores belong to the old candidate batch; they cannot establish
coverage for the 17 new selected companies. Preserve special-sector/unverified
model review and critical-financial gates. A new complete financial 100-company
acceptance run and CI remain necessary before MVP delivery. Fresh price
coverage was verified above at its recorded cutoff, not accepted indefinitely.

## 2026-11-03 — Candidate-driven bounded source collection and Salesforce recovery

PR: https://github.com/fatalvayn-dot/us-equity-research/pull/14
Source commit: https://github.com/fatalvayn-dot/us-equity-research/commit/ae1d4cd3825d4176474843f71799ce005a89c708
Tested source tree 668bf03ddf6588f034dc8cd9bf89637ee52b2766 matches local 59e09d5.
Source CI: https://github.com/fatalvayn-dot/us-equity-research/actions/runs/41546191295
All 595 tests and CLI status passed: Python 3.11/103.460s, 3.12/97.527s,
3.13/95.194s. Exact final documentation head is checked before merge.
Manual review: hard budget counts actual GET invocations, leases renew before
source steps, failures do not become missing, identity/exchange mismatches block
company-specific queries, classes require original disclosure, unselected historic
numeric defects cannot replace latest values, and latest-invalid fallback is
rejected. Source artifacts hold public bytes/URLs/times only; no SQLite or headers.

Branch feat/bounded-valuation-collection from main 7e1d2be3fc68088b14c974ac307c90b3fdef8a7b
(PR #13). Read PROJECT_BRIEF, status and AGENTS; remote main matched, no open
PR at start; exact-head Actions 41539190808 passed 577 tests on three versions.
Legacy untouched. Existing unrelated temporary source files preserved.

Implemented v0.29.0 collect-valuation-sources CLI for 1–100 exact unique symbol/
CIK candidates, with a hard 0–501 GET-invocation budget across all source legs,
zero-budget cache-only mode including directory, per-URL cooldown checkpoints,
leased/renewed state and original response archive/bundle. Shared 0.6-second
request spacing; 10-second request timeout, 25-second budget and two maximum
internal attempts. A GET invocation is not an individual retry. Missing, rate
limit, access denial, timeout, invalid identity and unstarted-budget states are
separate. Exact US-exchange identity is required before company-specific GETs.
Independent share, price and history legs cannot approve one another. No annual
financial refresh, financial-source priority change, capital-action/sector/
active-common-share acceptance, score or investment approval is implied.

Real bounded sample: MSFT, AMD, ORCL, AMAT, TXN, QCOM, CRM. Original selection
requested ten symbols but only these seven existed in the retained candidate
batch; the run and every artifact honestly use seven. Initial run made 32 GET
invocations (www.sec.gov 6, data.sec.gov 13, Yahoo 13), retaining 32 bodies:
7 exact identities/prices, 6 histories, 5 original-share reconciliations,
ORCL symbol mismatch and CRM invalid share data. Initial warm repeat made zero
GETs with unchanged share/price/history evidence. No all-100 acceptance claim.

Investigation found CRM's current DEI shares were rejected because of a 2011
unselected shares-unit row containing 133.9. Updated disclosed_shares to select
the latest available date cohort before numeric validation, quarantine invalid
unselected numeric rows with accession/date evidence and never correct/use them.
The latest invalid/conflicting count still rejects; it cannot fall back to an
older valid count. Structural, unit, chronology and exact primary-filing checks
remain. A follow-up made 3 new GETs (CRM metadata, original 10-Q, history):
6 dated-share reconciliations, 7 prices and 7 histories. Its cache-only repeat
made zero GETs with all original evidence unchanged. Combined 35 public source
observations retained, not a full financial-batch or score refresh. ORCL metadata
lists ORCL and ORCL-PD, so existing single-class model correctly remains blocked.
Source cutoffs and both before/after attempts: docs/evidence/collection7/;
portable raw bundle: tests/fixtures/collection7-sources/. README gives rerun CLI.

Tests: 15 new collector tests initially passed, then 16 including actual seven-
company raw replay; two added numeric-cohort tests ensure historic quarantine
and refusal to fall back from an invalid latest count. An initial stale-cache
test failed because its synthetic owner exceeded its 15-minute lease; fixed the
test to acquire a new lease for the next run, retaining strict runtime exclusion.
27 focused valuation/recorded checks passed after the numeric-cohort change.
Earlier full 592-test regression passed (72.804s, Python 3.12.14). Final full
595/595 passed (71.463s, Python 3.12.14), including 18 new tests. Exact-head
CI is checked before merge; these are offline regressions, not live CI acceptance.

Remaining blocker/next code task: collect and reconcile the original current
common-share covers for the remaining 17 sample candidates, or replace only
unsupported candidates with explicit verified common stocks; bind accepted
listing evidence to a 100-company plan. Then use bounded collector for missing
valuation/history inputs and refresh required annual/comparative batches for a
true end-to-end 100-company acceptance. Multi-class/ORCL-PD economics require a
separate model; do not drop preferred shares into a common-share price ratio.
Original unresolved covers (from docs/evidence/mvp100/documents.json): SPCX,
XOM, NVS, HSBC, AZN, MUFG, TM, WFC, IBM, C, TD, TTE, DIS, VZ, NVO, UBS,
BBVA. Several have raw documents but unresolved period/class; others have no
original document or no annual in the recent window. These are triage states,
not proof of inactivity or non-common status. Inspect exact original documents
and listing instrument evidence before replacing a candidate.
Old two-score pilot remains dated; no extra company score is claimed here.

## 2026-11-03 — Publish scored pilot and protect HTML source evidence

PR: https://github.com/fatalvayn-dot/us-equity-research/pull/13
Published source commit: https://github.com/fatalvayn-dot/us-equity-research/commit/21935908f498efbf0169c10da713e538579bac31
Tested source tree 51119acd8e5fc94ef2592f5ea3ad1488a2f26f0e matches local
25ba568 exactly. Main remained bb6b21c, no other open PR at session start;
prior Actions 41518212940 passed. Read PROJECT_BRIEF, status and AGENTS.

Source CI: https://github.com/fatalvayn-dot/us-equity-research/actions/runs/41538732876
All 576 tests and CLI status passed on Python 3.11 (82.209s), 3.12 (85.780s),
3.13 (84.965s). Current-session local baseline: 576/576, 69.481s on 3.12.14.
These are offline recorded-source/unit/integration regressions, not CI live
financial collection. Source replay retains the pilot's original cutoff and
2 scored/98 unscored/4 critical-review counts; no new live 100-company claim.

Manual review of scoring admission, literal financial definitions, critical
risk precedence, dated-share assumptions, history statistics, HTML escaping,
CLI paths and reproduction found a concrete defect: HTML destinations were
omitted from the source-bundle overwrite guard. Fixed all three destinations
(JSON/Markdown/HTML), including bundle root and nested paths for both SEC and
market bundles. One added regression checks 12 combinations with byte-preserved
sentinels and refusal before any report write. Targeted test passed (0.989s).
No source evidence was overwritten. Final local regression passed 577/577
(69.754s, Python 3.12.14); exact final-head CI is checked before merge.
Unrelated temporary files preserved and excluded from publication.

Remaining blocker: original 100-candidate sample has only 83 common-cover
matches, 97 valuation bundles remain unqueried and sector model coverage is
limited. Next implement bounded configurable source collection for an explicit
verified 100-common-share plan, then actual end-to-end acceptance. Do not
normalize missing scores or claim all-100 coverage from this two-score pilot.
Legacy repo untouched; no paid access, credentials, orders or portfolio work.

## 2026-11-03 — First explained research scores and portable ranked pilot (latest)

Branch: feat/explainable-research-score, based on main
bb6b21ca09c9806fd24b4544cd94c5f39539e601 (PR #12 merge). Read main, current
PROJECT_BRIEF/status/AGENTS, comparative/valuation/provider code; no open or
conflicting PR at start. Prior exact-head Actions 41518212940 successful.
Main/remote checks and local source state agreed. Legacy untouched; no paid
service, new permission, broker, portfolio, access workaround or automation.

Completed v0.28.0: technology-research-v1 with explicit SIC 3571/3674/7372 routes,
six 20/20/20/15/15/10 components and versioned published threshold hypotheses.
Eligibility is derived from raw operating-issuer metadata, original common-share
class/count evidence, recent US USD quote and latest available annual period.
Explicit BDC/fund/shell or unsupported/conflicting known disclosures override
an apparently supported SIC. Missing tags stay unknown, never false. Other
financial/special/unknown sector models remain unscored. All nine required annual
facts and prior comparable contract revenue are independently confirmed against
recent SEC snapshots. Caller scores/approvals/calculations cannot grant admission.

Critical financial review overrides all component points. Missing or unresolved
required evidence withholds the entire total; no available-weight normalization.
Literal contract revenue/PP&E payments remain required: no Revenues/Productive-
Assets/ProfitLoss alias. Valuation uses an explicitly labeled stress scenario:
dated disclosed shares plus one precision quantum, then 25% extra shares. This
is not an observed count, statistical confidence interval or complete capital-
change clearance. A returned split since disclosure requires review, not an
automatic share adjustment. Fair value and investment approval remain absent.

New daily-history adapter: exact issuer/symbol/USD/US exchange/window, bounded
200–400 ordered complete rows, >=300 calendar days/>=200 completed sessions,
no >10-day gaps, 15-minute source age, share-to-quote window and future rejection.
Exclude the quote day from statistics, even after the close. Observed risk uses
adjusted-close sample return volatility x sqrt(252) and last-63-session median
close x reported volume. Low liquidity (<USD5m) or >20% quote/history price
disagreement blocks totals. Absence of a split record does not clear issuance,
buybacks or all capital events. Historical statistics are not forecasts.

New score-report CLI reproduces JSON/Markdown/HTML from explicit input batches,
public source bundles and cutoff, without network calls. Input/bundle collision
protection retained. Portable Turkish HTML browser shows ranking, per-component
points, exact financial inputs/periods/source hashes and all unscored reasons.
Open docs/evidence/score-pilot/report.html. Model rules/limits:
docs/RESEARCH_SCORE_MODEL.md; reproduction and bounded live commands in README.
Status CLI now clarifies that it does not probe providers and that zero full-MVP
acceptances does not mean zero individual source checks. No false completion.

PILOT cutoff 2026-11-02T21:33:48.135379+00:00 (2026-11-03 local): retained
100-candidate financial and 80-issuer current/prior comparison batches plus
recent retained SEC source snapshots and seven new market observations. Calls:
3 Yahoo quotes, 3 Yahoo one-year daily histories and 1 SEC directory invocation,
excluding internal retries. Base 13-observation valuation bundle reused without
changing dates; overlay is tests/fixtures/score-market-sources/. One earlier
MSFT history availability probe was separate, not included in these seven calls.
No subscription CSV, credentials or authenticated endpoint used. Official SEC
SIC and Yahoo adjusted-close definitions checked; score thresholds are our
research hypotheses, not SEC/Yahoo endorsements or calibrated investment success.

Result: 100 candidates, 2 research scores (MSFT 66.5, AAPL 53.0), 98 unscored,
including 4 critical financial reviews. Both scored companies have 9 confirmed
annual inputs plus a confirmed prior revenue value; six components sum exactly
to the published total. NVIDIA's required contract revenue and PP&E inputs were
absent, so it remained unscored. Remaining 97 valuation bundles were unqueried
in this bounded pilot. These are dated annual inputs, not fresh full-100 financial
updates, TTM or a complete investment-risk review. Risk/value/strength separate.

Live helper integration was then verified in a separate state/cohort. It now
seeds dated observations and refreshes expired SEC/price data through the existing
collector, rather than permanently using six-hour-expired fixtures. That cohort
reused recent SEC/identity caches (0 GETs), fetched 3 quotes +3 histories, then
repeated with ZERO source/quote/identity/history GETs and unchanged sourced values,
times, component points, metrics and ranking. Separate replayable market bundle
and evidence: tests/fixtures/score-helper-market-sources/ and
docs/evidence/score-pilot/live-helper-validation.json. Financial annual/comparative
inputs remain recorded; new annual periods/conflicts correctly require updates.

Tests: final 576/576 full local regressions passed on Python 3.12.14 (69.131s),
including 23 new scoring/history/recorded/CLI tests. Earlier 575-test full run
also passed (65.909s). Remote matrix is checked before merge. Includes exact raw-source replay,
independent statistics-reference calculations, all six point sums, source/model
admission, financial critical-vs-favorable precedence, missing/negative/zero,
sector/legal/split/liquidity/price mismatches, future/stale/gapped/null data,
quote expiry removing scores, counter-injected approvals, escaped native/JSON
HTML and protected CLI destinations. Initial 6-test recorded run had one HTML
formatting error on JSON-serialized Decimal strings; corrected rendering to
accept both native Decimal and serialized numbers without changing finance.
All 6 then passed. No financial/statistical/primary-source reconciliation failure.
Diff and CLI checks passed. An unrelated temporary worktree file was preserved
and excluded from staging; no user changes were removed.

Remaining/next concrete task: complete a verified active 100-common-share sample
(original record has only 83 cover matches), collect missing valuation/history
sources for supported eligible issuers, refresh annual/comparative batches where
needed and perform the actual 100-company acceptance run. Keep unsupported/
special models and incomplete firms unranked; a separately verified semiconductor
literal-Revenues/productive-cash-payment model may be developed, never an alias.
These pilot scores are not a completed MVP or an investment recommendation.
Full sector coverage, qualitative risk, strategy performance and all-100 active
share acceptance remain unverified. P2/P3/P4 deferred; no invented percentage.

## 2026-11-02 — Original-filing-bound shares and valuation indications (latest)

Branch: feat/market-cap-valuation, based on main
dcb50c8d461ef7b71557ba4ef9cbb05d3d35536b (PR #11 merge). Read main status,
PROJECT_BRIEF/AGENTS and source adapters. Remote heads matched local main; no
open PR or conflicting work. Prior final-head Actions 41506243130 successful.
Legacy untouched; no new project, credential, access workaround or automation.

Completed v0.27.0: exact SEC DEI disclosed-share extraction, original primary
filing/class reconciliation and source-bound capitalization/ratio indications.
Shares are positive integral shares, not weighted-average/issued shares or
monetary fields. Latest nonfuture exact DEI observations require the explicit
share unit, filing availability, <=120-day date and <=6-hour source snapshot.
SEC submissions/accession/form/filing date/primary URL and original 10-Q/10-K
CIK, instant, non-dimensional shares unit/count and common-security cover must
agree. Multi-ticker, class-labeled, dimensional, preferred/depositary or conflicting
evidence is withheld. Precision and all source times/URLs/hashes are preserved.

Indicative capitalization = sourced Yahoo regular-session USD price times dated
original-filing-verified common shares. Three literal ratios: contract revenue,
issuer NetIncomeLoss and OCF less PP&E payments divided by the indication.
Missing operands remain absent, negative results remain negative. No Revenues,
ProfitLoss or productive-asset-payment alias. Each available annual numerator is
independently confirmed against fresh exact-period SEC companyfacts; conflicts
block rather than replace the first selected source. Original field trails and
Yahoo->SEC->Nasdaq->Finnhub priority remain intact. Derived capitalization is
not a provider market-cap observation. Fair value, sector/scope approval and
investment scores remain absent; capital changes since disclosure are unverified.

New CLI: valuation-report --input --source-bundle --as-of --output --markdown.
It evaluates provided raw observations with no network request, requires an
explicit cutoff, rejects future/stale prices and protects bundle/input paths.
Bounded three-company live verification helper reuses original-source caches
and a run lease. Portable source export excludes operational SQLite. Reproduction
commands and economic limitations: README and docs/DISCLOSED_SHARE_VALUATION.md.
SEC's official API documentation was checked; no API key is required for these
public endpoints. This is not a new investment model or a 100-share acceptance.

REAL SAMPLE, cutoff 2026-11-02T20:00:15.589376+00:00: AAPL/MSFT/NVDA, three
DEI counts matched exact original 10-Q disclosures (dated 2026-07-17,
2026-10-22 and 2026-08-21 respectively). Ten available annual values matched
fresh SEC companyfacts (AAPL 4, MSFT 4, NVDA 2); seven ratios calculated.
Financial annual periods and first-selected facts remain from the retained
recorded 100-candidate input, not a full refresh or TTM. Thirteen public source
observations: nine SEC source GET invocations, three Yahoo quote GETs and one
SEC directory GET (transport-internal retries excluded). Exact raw bundle:
tests/fixtures/valuation-sources/. Report/audit/manifest: docs/evidence/valuation-sample/.
The 100-candidate report has three indications, 97 pending source bundles (not
queried by this sample), zero rejected and zero scores. All fair values absent.

Immediate cache-only repetition: zero source, quote and identity GET invocations;
all original prices, disclosed counts, source hashes/times, metrics and indicated
capitalization values unchanged. Report evaluation cutoff advanced without
relabeling source observations as fresh. Original capture audit/cutoff retained
on export; later resume counters are separate. The initial helper looked for the
price GET count at the wrong dictionary level; corrected exported top-level
count from the preserved nested summary (3), with explicit correction trail.
No source value/timestamp changed. Replay at +16 minutes rejects all three
expired prices and cannot claim a current valuation.

Separate access diagnostics: five bounded GET invocations. Yahoo v7 quote timed
out; quoteSummary returned access_denied. First AAPL submissions attempt timed
out; MSFT submissions and Nasdaq AAPL info succeeded. Nasdaq's Common Stock
label was observed but quote currency was null, so it granted no market-cap or
scope approval. Two successful public probe bodies archived separately at
tests/fixtures/valuation-access-sources/. Direct provider market-cap values
accepted: zero. These probes are additional to, not part of, the 13-observation
sample. No quota bypass, host rotation, cookies, tokens or new access was used.

Tests: final 553/553 full local regressions passed on Python 3.12.14 (58.166s),
including 24 new valuation unit/recorded/CLI tests. Earlier 551-test full run also
passed (59.857s), followed by the 24-test targeted run (5.235s). Remote matrix is
checked before merge. Covers literal units/identity/periods, ambiguous/latest
rows, stale/future/malformed source data, primary class/precision, SEC conflicts,
calculation injection, Decimal precision, missing/negative cases, isolated bad
companies, exact recorded reconstruction and CLI bundle protection. One recorded
assertion initially expected nine available annual confirmations instead of ten
(NVDA has an additional OCF operand without complete PP&E ratio); corrected the
count, without changing validation or source values. No live share/financial
reconciliation failure. Diff/CLI checks pass; publication links follow in PR.

Remaining/next concrete task: validate the capital-change window and implement
an explicit versioned nonfinancial-sector research score model using these
source-bound inputs, with critical financial review overriding totals. Then
collect the remaining verified common-share sample and run real 100-company
acceptance. Original universe still has only 83 common-share cover matches;
100 current active common shares are not accepted. 97 new valuation source
bundles remain unqueried, special/unknown models remain unapproved, all scores
and ranks absent, and MVP acceptance remains FALSE. No 500+ expansion or P3/P4.

Publication: https://github.com/fatalvayn-dot/us-equity-research/pull/12
Source commit: https://github.com/fatalvayn-dot/us-equity-research/commit/f85867bc73d12862db6f7b3121d800d14b8d0bf4
Source Actions: https://github.com/fatalvayn-dot/us-equity-research/actions/runs/41517767392
All 553 tests plus CLI status passed on Python 3.11/3.12/3.13; all job logs
inspected (53.268/59.317/56.780 seconds). Source tree
033198f0e627c1e28fffd60bb160eeaee8fb6d67 matched the local tested tree.
Manual review checked source order vs independent confirmation, exact class/
unit/period matching, missing/negative/rounding rules, protected outputs, fresh
vs recorded evidence and the prohibition on interpreting indications as approved
scores/fair values. Documentation-head CI and merge SHA are recorded in PR #12.
The first upload-manifest read failed because the transient helper was absent;
it was recreated before any remote mutation. No repository data was lost.

## 2026-11-02 — Portable research browser and non-compensating financial review (latest)

Branch: feat/financial-risk-assessment, based on main
2a27a6dc405ccfe31ce02df2e00f9e85a25c8253. Checked remote heads and main, open
PRs (none), PROJECT_BRIEF/status/AGENTS and prior exact-head Actions
41498364737 (success, Python 3.11/3.12/3.13). No conflicting work observed.
Legacy repository untouched. User reconfirmed autonomous technical decisions
and working-prototype priority. No new permissions, service or automation.

Completed v0.26.0: portable searchable/filterable HTML research browser with
100 candidate cards, exact periods, 843 collected values, 576 calculations,
source links/hashes and explicit missing/attempted-source states. Open
docs/evidence/risk100/report.html locally. Regenerate JSON/Markdown/HTML using
the README research-report command. No server, external script or installation
is needed to inspect the saved HTML. CLI output destinations are checked for
input/output collisions and written atomically per file. Escaped issuer/source
text cannot inject markup into the page.

Added financial-review-v1: exact Assets/Liabilities balance deficit and same-
annual-period loss plus operating cash outflow require mandatory review.
Operating losses and classified current balance shortfall are watch signals.
Each check revalidates issuer, definition, currency, period, chronology and raw
source hash. Explicit annual 350–380-day periods and a 550-day period-end age
guard prevent quarterly/ancient figures passing as current annual checks.
Missing/invalid evidence remains unresolved; a critical trigger takes priority
over favorable or incomplete other checks. No insolvency finding, debt proxy,
sector approval or overall risk clearance is inferred. Original inputs and
observation times are preserved. All investment scores/ranks remain absent.

Recorded 100-candidate replay: 4 mandatory reviews (ABBV/PM/DELL/MCD reported
balance deficits), 44 unresolved quantitative screens and 52 without a trigger
in these four checks. Watch signals: 20 current balance shortfalls and two
operating losses, overlapping company categories. Zero network requests for
this reassessment. These are not a fresh financial run, original-statement
independent revalidation of all 843 values, or live acceptance. Original 83
common-share cover matches still do not establish the required current active
100-share universe. Four check outcomes are screening-policy hypotheses, not
calibrated risk probabilities. Details: docs/FINANCIAL_REVIEW.md.

Tests: final 529/529 full local regression passed on Python 3.12.14 (58.418s),
including 16 new assessment/browser/CLI tests. Earlier 528-test full regression
also passed (58.411s). Remote matrix is checked before merge. Coverage includes critical-over-missing
precedence, favorable-other-figure non-compensation, zero vs missing, exact
identity/currency/concept/period/hash, old/future data, input immutability,
invalid-company isolation, HTML escaping, CLI collision refusal and deterministic
100-candidate artifact reconstruction. Initial 13-test run had two integration
errors from decoding already typed report facts; corrected by reconstructing
Fact directly, with no financial-validation relaxation. All 13 then passed.
One trailing README blank line found by diff check was removed.

Live valuation diagnostics: four bounded single-attempt GET invocations across
two Yahoo and two Nasdaq endpoints. Both Yahoo endpoints and Nasdaq info timed
out. Nasdaq summary returned a market-cap string but lacked explicit currency
and market timestamp for that field; it was not accepted as a valuation input.
No raw response was archived for this diagnostic, so it is not replay/live
financial acceptance evidence. No access workaround was attempted. Outcomes:
docs/evidence/valuation-access-diagnostics.json. Public SEC financial-statement
guide checked as conceptual documentation; thresholds are our research policy.
The optional equity skill router's linked shared resources were unavailable;
implementation followed this repository's authorized source/model contracts.

Remaining/next concrete task: obtain source-bound market capitalization or
class-compatible share-count/price inputs with explicit units, currency and
observation times; implement versioned sector-eligible valuation and explained
score components, then finish the verified 100-share sample and real acceptance
run. No generic/special-sector score is approved by this change. The delivered
HTML is a working evidence-inspection prototype, not the accepted ranked MVP.
Commit/PR/exact CI links are recorded in the publication follow-up below and PR
discussion. Do not report local tests as Actions or recorded inputs as live data.

Publication: https://github.com/fatalvayn-dot/us-equity-research/pull/11
Source commit: https://github.com/fatalvayn-dot/us-equity-research/commit/76bd7d78574cf3607fbfd0b376871c7bdbccb27d
Source Actions: https://github.com/fatalvayn-dot/us-equity-research/actions/runs/41505752772
Source CI passed: all 529 tests and CLI status on Python 3.11/3.12/3.13.
All three job logs were inspected; test durations 33.846/62.743/63.620 seconds.
Evidence: docs/evidence/financial-review-tests.json and financial-review-actions.json.
Exact source tree 3d1ae7058b72f80676b94d0e28398adbaa736135 matched the local
tested tree. Manual review checked source/period revalidation, critical-before-
missing precedence, no risk clearance/model admission, escaped HTML content,
output collision checks and retained numeric regression counts. Source CI
and final documentation-head CI results are recorded before merge in PR #11.

## 2026-11-02 — Reference review and exact liquidity/operating inputs (latest)

Branch: feat/liquidity-operating-analysis, based on main
1338a40a830d8781acb22636dba8de96f33a49aa (PR #9 merge). Main fetched; inspected
remote heads, open and recent merged PRs, README/AGENTS/PROJECT_BRIEF/status,
provider/model/SQLite/report code and original evidence. No open/conflicting PR
at start. Prior exact-head Actions 41484828688 successful. Baseline 492 tests
passed again locally (30.073s). Legacy untouched; no new main project created.
Connector branch-search argument binding failed; remote heads were read using
git ls-remote instead. No data or repository state changed by failed reads.

TRADE28 read-only audit: pinned Jakeschincariol/day-trader-skill commit
3d0f4ef6986f4984b7c6bd46f7ff4f87744c3abd, MIT copyright 2026 Jake Schincariol,
stdlib Python >=3.8; plugin manifests and external Alpaca MCP example reviewed.
No reference installation, imports/execution, tests, broker or credential setup;
no third-party code copied. Five requested modules reviewed. Detailed source-
linked license/dependency/data/security/model decisions and independent criticism:
docs/reviews/TRADE28_REVIEW.md. Preserve stronger existing provenance/identity;
do not copy revenue/net-income alias merging, arbitrary unit fallback, inferred
Q4, loose YoY dates, symbol punctuation conversion, quota-host rotation or
missing-price/freshness defaults. Batch queries and input-bound risk gates are
future design candidates. News, technical signals, simulation and portfolio work
remain deferred. Monte Carlo resampling is not a future-success probability.
PROJECT_BRIEF records the newly approved P0/P1 and non-compensating risk priority.

Completed v0.25.0: five literal fields AssetsCurrent, LiabilitiesCurrent,
CashAndCashEquivalentsAtCarryingValue, OperatingIncomeLoss, GrossProfit. Seven
new traceable calculations: current ratio, cash-equivalents/current-liabilities,
working capital, two operating and two gross margin variants. No accounting
aliases, inferred debt/EBIT/cash aggregation or derived gross profit. Exact
instant-vs-duration operands use the same issuer/end/currency/definition/as_of
and raw-proof contracts. Instant-only reporting now calculates liquidity without
inventing annual starts. Negative working capital and operating losses remain
literal; negative balance inputs and nonpositive ratio bases are withheld.
Model/scope/investment approvals remain false, including special/unknown sectors.
A low current ratio or negative book working capital is not an insolvency finding.

MVP plan now includes 14 literal fields. An explicit annual end with unresolved
start requests five instant fields and defers nine duration fields; no guessed
dates. Default source order remains Yahoo->SEC->Nasdaq->Finnhub, first valid
stops. Unsupported local adapters do not create an HTTP request. Cached/source
recordings are not relabelled as fresh; source observation times stay unchanged.
Original 100-candidate record remains preserved. Expanded original-source replay:
470 additional field jobs, 307 accepted and 163 pending (121 SEC missing,
27 unsupported/15 invalid outcomes; lower-source availability is explicit).
Combined 100-candidate report: 843 facts and 576 arithmetic results, including
72 current ratios; 98 review-required and 2 period-unresolved companies. Original
recorded sector profiles are preserved as review labels, not fresh approvals.
No new HTTP request in this replay, and no new 100-company live acceptance.

Separate fresh connections: AAPL/MSFT/NVDA SEC companyfacts fetched in three GET
invocations; all 15 selected fields matched the exact original annual iXBRL
issuer/period/USD concepts. Six original public observations (3 fresh financial
responses +3 original annuals) stored in a bounded hash-checked source bundle.
Separate current price sample: 3/3 Yahoo prices accepted with one fresh SEC
identity GET and three Yahoo GET invocations; four raw observations archived.
Old 100-price snapshot was revalidated as recorded evidence, not treated as
current beyond its 15-minute cache freshness. All tests/CI replays are offline.

Tests: 513/513 local tests passed on Python 3.12.14, 53.691s (492 baseline +16
new unit/integration tests +5 recorded/primary-source tests). All 307 additional
facts re-extract from exact original companyfacts bytes; all 15 fresh values
reconcile to original iXBRL. Coverage includes missing/zero/negative amounts,
no total-vs-current or cash/operating aliases, wrong issuer/currency/period,
future proof, precision, instant-only report, first-valid stopping and unchanged
legacy numeric results. Four outdated plan-size/deferred-field assertions failed
across two early targeted runs (3, then 1); updated to 14 fields/five instant/
nine duration expectations without relaxing financial validation. New calculation
tests passed first run. No fresh provider/original-value mismatch. Working-tree
capture policy_version fields retain their original capture label; release bump
affects future checkpoint keys, not recorded numeric evidence. CLI and diff checks
are required before publication; corrected full matrix CI is checked before merge.
Evidence: docs/evidence/liquidity100/, current-price-sample/, liquidity-tests.json.
PR: https://github.com/fatalvayn-dot/us-equity-research/pull/10
Code commit: https://github.com/fatalvayn-dot/us-equity-research/commit/3975a0ff181f36f76efd4ae1a1426fab6b522275
Actions: https://github.com/fatalvayn-dot/us-equity-research/actions/runs/41497740509
All 513 tests plus CLI status passed on Python 3.11/3.12/3.13; all job logs
inspected (53.010/50.431/39.091 seconds). No failing matrix job. The published
tree cc30dd1a30f8a1a9b59b291b237b55526aa6ad4b matches the local staged/tested
implementation plus release metadata. Manual code review checked exact period/
unit handling, no aliases or guessed starts, negative/zero balance rules,
unsupported-provider stopping and unapproved-sector/no-score invariants.
Documentation follow-up CI is checked before merge; exact-head CI and merge
SHA are recorded in PR #10 discussion.

Remaining: 100 verified active common-share coverage is not accepted (original
83 cover matches); 439 combined attempted field outcomes remain pending, 90
duration jobs deferred for ten missing starts, and 28 fields unattempted for two
missing annuals. Alternative literal definitions are not all required by every
model; these are field-job counts, not an economic completeness threshold.
Zero sector-approved investment scores/ranks; source-bound valuation and generic
sector eligibility remain missing. No investment-ready company count established,
no fabricated overall completion percentage and MVP acceptance remains FALSE.
Next concrete code task: unify financial suitability, valuation and risk outputs;
add source-bound valuation inputs and an explicit versioned generic-sector model
with mandatory critical-risk gates before weighted scores. Unknown/special or
incomplete issuers stay unranked. Then complete the verified 100-share sample and
run the reproducible report. P2/P3/P4 cannot delay that work.

## 2026-11-02 — Live source-bound Yahoo prices for 100 candidates (latest)

Branch: feat/yahoo-market-price, based on main
9676b5c298299c418b4eea6941e34468dc3f119b (PR #8 merge). Fresh clone recovered
current GitHub sources after workspace cleanup; main and PROJECT_BRIEF/status
reviewed. No open PRs or conflicting work at start or before publication. Previous
exact-head Actions 41474627084 successful. Legacy repository untouched.

Completed v0.24.0: separate immutable MarketPrice contract, strict Yahoo chart
regularMarketPrice adapter, bounded resumable price-run CLI and portable raw
source export. Prices are USD per share, distinct from accounting periods, NAV,
adjusted closes, after-hours prices or market cap. Exact uppercase class symbols
(no punctuation alias), fresh raw SEC-directory symbol/CIK binding, explicit
matching US exchange labels, EQUITY metadata and aware market/source times are
required. Missing/invalid/old/future responses never become zero prices. Positive
Decimal values preserve exact JSON precision. First observed availability equals
original retrieval; it is not backdated to market time. Immutable approval flags
cannot be constructor-injected. EQUITY/directory membership do not prove common
share or sector-model eligibility; all companies remain unranked and in review.

Pacing/timeouts/size limits/sanitized quota/access/network errors reuse the HTTP
transport. Price response TTL is 15 minutes; SEC identity TTL one day; quote-age
limit four calendar days, explicitly separate from response age and permitting
common market closures. Original public responses are incrementally archived;
restarts retain raw bytes and observation times. Renewable run lease prevents
concurrent writers. Zero-work mode never fetches missing/expired data or identity.
The default price state directory is separate from MVP financial reports. Yahoo
valid prices stop fallback; absent/failed Yahoo outcomes expose SEC unsupported
market-quote field plus unconfigured Nasdaq/Finnhub quote adapters with no HTTP
request claimed for those entries. SEC identity fetch is counted separately.
Missing/invalid successful response bodies retain their raw source evidence.

REAL RUN on 2026-11-02: 100/100 existing candidates yielded contract-valid Yahoo
regular-session prices. SEC exact CIK/class-symbol binding and USD/exchange/time
contracts passed for every selected price; 36 NMS and 64 NYQ. Original price
observations span 16:26:53.900693–16:32:52.493309 UTC. Collection made 100 Yahoo
GET invocations and one SEC-directory GET invocation (internal transport retries
are excluded from these counters). A separate initial one-GET AAPL availability
probe preceded collection and is recorded separately; it is not an accepted
identity-validated batch input. No authenticated/paid source or new access.

All 100 price values and both price/identity source references are backed by
101 exact public observations in the portable raw bundle. Every stored report
hash and every parsed price was checked against the original source bytes.
Immediate max-new-prices=0 rerun retained all 100 original prices, market times,
retrieval times and raw hashes with ZERO price and ZERO identity GET invocations.
That rerun is cached reproduction, not another fresh live run. Evidence:
docs/evidence/price100/, tests/fixtures/price100-sources/, price-probe.json.
README gives collection/cache-only/export commands. CLI outputs source-bound
JSON and readable Markdown; operational SQLite files are not published.

Tests: 492/492 local unittest tests passed on Python 3.12.14, 32.465 seconds
(457 regressions +30 unit/CLI/integration tests +5 real-recorded regressions).
Covers exact class/CIK/endpoint, ETF/foreign/unknown exchange rejection, Decimal
precision, invalid/duplicate JSON, missing vs API/quota, explicit USD, separate
market/response/identity age and future rejection, local fallback vs HTTP,
first-valid stopping, cache restart/zero-work budgets, lease conflict, safe CLI
errors/export, retained missing-response proof and reconstruction of all 100
actual prices from both original source bodies. CLI status and diff check pass.
Earlier 484-test regression run also passed; initial 492-test run took 35.867s.
Initial PR CI 41483836238 exposed a Python 3.13 test-only exception mismatch:
dataclasses.replace rejects init=False approval injection with TypeError rather
than ValueError. The protection itself worked; the assertion now accepts both
version-specific rejection types. The 3.11 job passed, 3.13 failed one test and
the 3.12 job was cancelled. Review also clarified the future identity diagnostic
as future_observation rather than stale_identity; both reject the observation.
The full local 492-test regression rerun passed after the corrections. No terminal
live-provider failure was reported. A status-edit helper stopped before writing
because of a string/Path mix; corrected without changing source data or test results.
PR: https://github.com/fatalvayn-dot/us-equity-research/pull/9
Initial source commit: https://github.com/fatalvayn-dot/us-equity-research/commit/49b0d92ba5f37836ca73e48f73bacc9514bbbf0b
Compatibility/diagnostic fix: https://github.com/fatalvayn-dot/us-equity-research/commit/735bf48ac273b328664331bf704426831a65f811
Corrected matrix run: https://github.com/fatalvayn-dot/us-equity-research/actions/runs/41484335857
Corrected Actions 41484335857 passed all 492 tests plus CLI status on Python
3.11/3.12/3.13; all three job logs inspected (34.963/38.318/32.761 seconds).
Published corrected source tree dd393b98ab0aeafa85cb4fe10d0b0d32aa4309f9 exactly
matched the tested local source tree. Documentation follow-up CI must pass before
merge; final exact-head CI and merge SHA are recorded in PR #9 discussion.
Evidence: price-tests.json. Recorded-response CI is not a fresh live acceptance.

Remaining MVP blockers: no source-bound market-cap/share-count valuation bridge,
no accepted generic operating-sector eligibility/scoring path, only 83 registered
common-share cover matches in the original 100 financial candidates, unresolved
annual/financial fields. These 100 prices are NOT 100 accepted common-share
investment analyses. Zero scores/ranks and MVP acceptance remains FALSE.
Next concrete code task: join the existing exact financial, comparative and price
inputs into a versioned general operating-company eligibility/score contract;
obtain exact sourced valuation inputs, withhold incomplete components and keep
bank/insurance/REIT/BDC/unknown profiles in review. Test numerical thresholds,
operand provenance and missing-value behavior; then run the 100-company report.
Do not expand to 500+ or backtests before usable-MVP acceptance/user assessment.

## 2026-11-02 — Source-bound annual comparisons and growth CLI (latest)

Branch: feat/comparable-annual-inputs, based on main
77ca70c8d1927888806de607f1f7fba622af7375 (PR #7 merge). Fetched main;
no open PRs or conflicting source work; previous exact-head Actions 41454028341
successful. Reviewed PROJECT_BRIEF and DEVELOPMENT_STATUS. Legacy untouched.

Completed v0.23.0: reparse original annual document contexts, discover explicit
prior start/end dates from the same annual accession and exact accounting tag,
then emit separate current/prior research-batch plans. Discovery selects periods,
not numeric financial winners, and never counts a provider as tried. No fiscal
start inferred from fy/fp/frames or subtracting a year. Conservative comparability
requires consecutive 350–380 day full years with <=7-day length difference,
including 52/53-week years. Stub years, ambiguous periods and conflicting values
stay unresolved. Literal broader accounting concepts remain separate.

New comparative-report CLI revalidates both original ordered source trails and
exact issuer/currency/accounting contexts before calculating current/prior - 1.
SEC operands must share accession, original snapshot hash/time and filing date.
Both full operand facts and original collection attempts remain in JSON; Markdown
shows each arithmetic/missing result. Nonpositive prior bases produce no value.
No investment score/rank or general sector approval. Business-perimeter/accounting
policy comparability and special/unknown sector models still require review.
Gzip batch inputs and safe atomic report export are supported. Prior plans can
also be used for fresh ordered research-batch collection.

Recorded original-source replay: all 100 candidates considered; 80 companies
have comparison plans, 5 lack a matching literal prior-period pair and 15 are
deferred (12 without a verified annual context, 3 invalid original evidence).
347 current +347 prior facts accepted by actual adapter/resolver contracts;
Yahoo duration adapter returns local unsupported_field, SEC is valid, lower
sources stop unqueried. 334 arithmetic growth results; 13 nonpositive bases
remain unavailable. All original source observations preserved, replay cutoff is
current session time, ZERO new HTTP requests. This is recorded-source replay,
not a new live run, freshness acceptance or historical-vintage dataset. Original
100-candidate live acceptance limits from PR #7 remain unchanged. Evidence:
docs/evidence/comparative100/ (compressed full report/batches, exact query plans,
audit, Markdown, file hash manifest); raw responses reuse immutable PR #7 bundle.
Reproduce with README commands and scripts/verify_comparative_inputs.py.

Tests: 457/457 local unittest tests passed, Python 3.12.14, 47.615s (426
regressions +28 unit/CLI tests +3 real-recorded regressions). Coverage includes
52/53-week calendars, dates not inferred, stub/gap rejection, exact annual
accession, wrong identity/URL/future observation, ambiguous/conflicting values,
foreign currency, source-order/scope injection, zero/negative base, literal
semantic labels, precision/magnitude bounds, compressed CLI export/destination
collision and all 334 real-recorded calculations/694 input source references.
CLI status and git diff --check passed. Evidence: comparative-tests.json.
Initial new-test run found a duplicate test-helper argument (18 tests passed,
1 error); corrected the fixture construction; subsequent 28-test and full457
runs passed. No failed live API request or new access requirement this session.
PR: https://github.com/fatalvayn-dot/us-equity-research/pull/8
Code commit: https://github.com/fatalvayn-dot/us-equity-research/commit/61ed2678b27d1133de7387ee7553341b7c4f22cf
Actions: https://github.com/fatalvayn-dot/us-equity-research/actions/runs/41474272724
GitHub Actions passed all 457 tests plus CLI status on Python 3.11/3.12/3.13;
all three job logs inspected (24.568/20.476/32.720 seconds). This is recorded
regression CI, not a new live run. The published tree
4210bf47d52e06da97183830abb4b9c64d93b211 exactly matched the locally tested tree.
All seven report artifact hashes also passed a separate integrity check.
Documentation follow-up CI is checked before merge; exact-head CI and final
merge SHA are recorded in PR #8 discussion.

Remaining blockers: no provenance-bound current market price/class-share inputs,
no accepted generic-sector scoring/eligibility path, only 83 common-share cover
matches in the original 100-candidate run, unresolved companies/financial fields.
MVP NOT COMPLETE; target 2026-11-04 remains an objective, not guarantee.
Next concrete code task: bounded Yahoo price adapter with exact class-symbol,
SEC issuer binding, currency and market timestamp/raw evidence; recorded tests
then live small-sample validation. Connect price/prior-period inputs to an
explicit generic-sector scoring hypothesis while leaving special/unknown and
insufficient issuers unranked. Complete 100 verified common shares before MVP
acceptance; no 500+ expansion, backtest or legacy work.

## 2026-11-02 — Unified live 100-candidate pipeline and portable proof (latest)

Branch: feat/mvp-live-pipeline, based on main a8eeba8362e520e5782b6c3075d23807757aa21e
(PR #6 merge). Main was fetched and clean; no open PRs at start, prior Actions
41436814684 successful. No concurrent source work observed. Legacy untouched.
Initial code commit: https://github.com/fatalvayn-dot/us-equity-research/commit/547ba4ed4b8caca14e38a8f85371a6e489d6cae4
PR: https://github.com/fatalvayn-dot/us-equity-research/pull/7
Initial 420-test PR CI run 41446482758 passed; final 426-test evidence CI passed as recorded below.

Completed v0.22.0: mvp-run wires fresh/cached SEC metadata, exact original annual
periods, bounded resumable Yahoo->SEC->Nasdaq->Finnhub fields, exact raw-reference
archive checks, sector review labels and JSON/Markdown report. Global renewable
run lease prevents conflicting writers; SEC clients share request pacing. Cached
metadata/documents/facts retain their original observation times. Missing annuals
are unattempted companies; explicit annual ends without a verified start support
only instant Assets/Liabilities, with duration jobs explicitly deferred. No fiscal
start is guessed. Nine literal fields include separate Revenues, ProfitLoss and
ProductiveAssets payments, never aliases for narrower definitions. All economic,
scope and investment approvals remain false; special/unknown profiles stay review.

REAL RUN, 2026-11-02: fresh SEC submissions completed for all 100 candidates.
98 original annual downloads attempted: 93 available source bodies, 88 explicit
annual periods, 83 registered common-share matches, 5 invalid-data source outcomes
and 2 no-annual-in-recent-window outcomes. First six-field run completed with
450 input facts and 151 arithmetic results; 482 public GET invocations, excluding
internal retries/private Finnhub transport. Original first-run report and batch
are preserved separately, including missing-data/provider attempts. This is a
candidate run, not approval of 100 active common shares or financial acceptance.

Expanded exact-field completion resumed existing checkpoints. Final result:
100 reported candidates, 98 companies with financial queries, 96 with at least
one contract-valid financial fact, 536 facts and 272 exact arithmetic results.
812 explicit field jobs: 536 collected and 276 pending_data. Ten companies lack
a verified annual start, so 70 duration-field jobs remain unattempted. SPCX/XOM
have no annual filing in the recent window and no financial query; TD/SNDK have
financial attempts but no accepted facts. No global data absence is inferred.
Current sector routes: 81 other-industry review, 10 bank signals, 3 insurance,
5 other finance/real-estate and 1 REIT signal. Zero scored/ranked companies.
Source/period/currency/accounting/observation/hash contracts are validated; this
is not independent economic-model or financial-statement acceptance.

A zero-new-document/zero-new-field rerun retained all 536 facts and 272 arithmetic
results with ZERO public GET calls. This is a same-state cached reproduction,
not a second fresh-source live run. All selected financial/identity/unit evidence
references resolve to exact raw observations. Portable proof: 553 observations,
109,703,028 gzip bytes split into 210 bounded parts. Every part, complete bundle
and reconstructed response body hash/count was verified. Evidence contains raw
public responses/URLs/original timestamps, not operational SQLite caches, headers
or credentials. Large JSON reports are losslessly gzip-stored with stored/raw
hash manifests. Evidence: docs/evidence/mvp100/, tests/fixtures/mvp100-sources/;
reproduce with README mvp-run/export commands. Source coverage is not a claim
that every issuer's statements were independently reconciled or model-accepted.

Failure/recovery: expanded completion hit sqlite3.OperationalError (readonly
write) after preserving at least 716 field checkpoints. New connection write probe and
financial integrity_check succeeded; cause not established, no permission change
needed. Confirmed no MVP process running, recorded/released only the exact orphan
financial lease, then resumed successfully. Recovery record is persisted. CLI
now reports safe typed SQLite errors rather than raw exception detail. Initial
publication assembly encountered nested runtime SQLite files; full data/ ignore
was added before staging/upload, and no operational database was published.
Staged diff check caught trailing blank lines in generated Markdown; the renderer
and report hash manifest were corrected before publication.
Report-stage zero network count was separated from actual collection GET counts;
first report's legacy zero counter refers to report generation only.

Tests: 426/426 local tests passed on Python 3.12.14 (400 regressions +14 pipeline/
recovery tests +7 portable-bundle tests +5 recorded-real-run regressions), 27.614s.
Offline fixture integration verifies pipeline, work bounds, exact period/identity,
lease conflict/release, zero-call resume and raw archive coverage. Real-recorded
regressions reproduce all 536 facts/272 arithmetic counts, verify report hashes,
all original source references and period deferrals, and assert missing scores/
no acceptance. Recorded replay in CI is not a new live run. git diff --check
passed. Test evidence: mvp-pipeline-tests.json. GitHub Actions run 41453428330 passed 426 tests plus CLI status on each Python
3.11/3.12/3.13; job logs inspected. CI is recorded replay, not a fresh live run.
Data/code commit: https://github.com/fatalvayn-dot/us-equity-research/commit/40e586e9c1686a2533fa0e27d56171e4405a7fbd
Actions: https://github.com/fatalvayn-dot/us-equity-research/actions/runs/41453428330
Published tree ad9dcba5b14c340434be1f490588649b39496c2b matched the staged local
tree exactly. Full tree creation returned GitHub 422 timeout twice; incremental
15-entry tree batches succeeded with the same final hash. Documentation follow-up
CI is required before merging; final merge result is recorded in PR #7 discussion.

Remaining MVP blockers: only 83 common-share class matches (not 100 approved
active common shares), 2 unresolved annuals, 2 additional no-fact companies,
unaccepted generic-sector eligibility/scoring, missing required market-price/
comparable prior-period inputs. No fabricated scores and no MVP completion claim.
Next concrete code task: add provenance-bound market-price and prior-period
inputs plus a testable eligible generic-sector score contract; keep special/
unknown/insufficient issuers unranked and complete the 100 common-share selection
before acceptance. Broad sector taxonomy/backtests/500+ expansion remain deferred.

## 2026-11-02 — MVP priority reset and user-facing research report (latest)

Branch: feat/mvp-research-report, based on main ec0907754fff80027e7cdb0e2fb6dac0c09893e8
(PR #5 merge). Main fetched and clean; no open PRs; prior Actions 41433339549
successful. No concurrent main update observed. Legacy repository untouched.
PROJECT_BRIEF updated to the user's approved 48-hour usable-MVP objective,
target 2026-11-04 without guarantee. Full four-source acceptance, 500/1000/all-US,
comprehensive backtests and complete specialized models are deferred. User
usefulness confirmation is required after MVP acceptance before expansion.
No broad legal-taxonomy work was added in this session.

Completed v0.21.0: research-report CLI exports deterministic JSON and Markdown
from the actual resumable research-batch schema, requiring no network or key.
Report revalidates exact issuer, accounting definition, currency, period,
publication/retrieval cutoff, raw hash and first-valid source-attempt sequence.
Duplicate issuers cannot inflate company coverage; mixed periods or duplicate
fields cannot silently overwrite an operand. Malformed evidence invalidates the
affected company while other companies continue. Report files are atomically
replaced individually; input/output path collisions are rejected. Export exit
success is explicitly separate from MVP acceptance.

Reports show full original financial facts/source URLs/raw hashes/observed and
available timestamps, actual provider attempts (including unstarted/missing/
configuration states), exact calculation operands/formulas/values and explicit
score-component blockers. Six weights remain 20/20/20/15/15/10. No generic
sector approvals or numeric scores are manufactured: pending scope/model,
missing market prices, comparable prior periods and risk-model gaps remain
visible. Caller-injected score/scope approval cannot create a ranked company.
Out-of-scope companies never receive calculation/rank output.

Recorded eight-company example: 43 accepted contract-valid input facts, 17 exact
arithmetic results, 8 review-required companies and 0 scores/ranks. The extra
supplemental accounting fields in earlier diagnostic scripts are intentionally
not aliased into this six-field collection. Original cutoff is retained. No new
provider/financial HTTP request and no 100-company real run this session. This
is a usable report/export increment, not MVP completion. Evidence: mvp-report-
eight.json/.md. Reproduce with the README research-report command.

Tests: 400/400 local unittest tests passed on Python 3.12.14 (383 regressions +
17 new tests). CLI JSON/Markdown export and git diff --check passed. Evidence:
mvp-report-tests.json. Coverage includes recorded 43-fact replay, missing vs
unstarted, isolated invalid-company handling, wrong issuer/definition/period/
currency, future timestamps, missing hash, source-order/first-valid contracts,
coverage deduplication, scope injection and safe export destinations. No test
failure. GitHub Actions run 41436593541 passed 400 tests and CLI status on
each Python 3.11/3.12/3.13; logs inspected.
PR: https://github.com/fatalvayn-dot/us-equity-research/pull/6
Code commit: https://github.com/fatalvayn-dot/us-equity-research/commit/8607815ea4c37f7ac0111238db923433d39db65d
Actions: https://github.com/fatalvayn-dot/us-equity-research/actions/runs/41436593541
Published tree 940f56e31f8529454c5a7244d84f70d870968935 matched the locally
tested tree. Documentation follow-up CI is checked before merging; final merge
result is recorded in the PR discussion.

Remaining MVP blocker: no 100-company live financial run, no accepted generic
sector scoring/model/scope path, no required market-price/prior-period inputs.
Next concrete code task: connect bounded live 100-candidate collection and
original-response archiving to one MVP command, reporting unresolved periods as
explicit unattempted jobs; then implement a testable generic-sector score model
with explicit required inputs/eligibility, leaving special/unknown issuers in
review. Continue highest-priority pipeline/report work before specialized models.

## 2026-11-02 — Positive original registration-cover evidence (latest)

Branch: feat/registration-legal-evidence, based on main bec07410ff367dd581a84a213d6e10172c073e7b
(PR #4 merge). Main fetched, worktree clean at start, no open PRs, prior Actions
run 41421991631 successful. No concurrent main update observed. radar-agent
untouched; no authorized archive API exposed.

Completed v0.20.0: a separate registration_legal_evidence path for literal
N-2/N-2/A/N-2ASR cover labels. Caller must specify disclosure date; same-day
start/end duration, issuer CIK and DocumentType plus EntityCentralIndexKey must
share a verified non-dimensional context. No annual FY focus or fiscal-year
start is inferred. The cover label is kept distinct from the EDGAR submission
form: a POS EX amendment may contain DocumentType=N-2. No EDGAR form code is
invented from that label. Wrong issuer/date/form/endpoint, future observation,
dimensional contexts and cross-context anchor joins fail closed.

Added narrowly verified registration boolean transforms: SEC boolballotbox maps
U+2610 to false, U+2611/U+2612 to true; XBRL 2020/2022 fixed-true/fixed-false use
constant semantics. Exact namespace binding is mandatory, including rebinding
rejection. Unsupported encoding/characters remain without value. Annual parser
behavior is preserved: it still does not guess unsupported transforms. Shared
literal disclosure decoder retains duplicate/conflict/missing/nil semantics and
raw source/context/text/format evidence. No economic, legal or scope approval.

New source validation: two official SEC issuer documents downloaded successfully
with bounded 15-second requests and 6,000,001-byte reads (42,312 and 63,681 bytes).
Both original responses are saved as deterministic gzip fixtures with exact
URL/SHA/retrieval time. This is fresh retrieval of existing disclosures, not proof
of current status. CIK 0001902649: context date 2026-08-21, DocumentType=N-2/A,
BDC reported true / registered closed-end flag false. CIK 0002031545: context
date 2026-10-01, DocumentType=N-2, BDC reported false / registered closed-end true.
Four literal flags reproduced from exact original bytes. Evidence:
registration-source-manifest.json, registration-legal-replay.json and
scripts/verify_registration_legal.py. These documents are legal-disclosure test
examples, not additions to the active-common-share universe or investment list.

Old eight-annual replay remains identical: zero reported targeted disclosures,
24 unknown fields. No old missing field filled by an unrelated registration.
No financial-value HTTP requests; two new issuer-document downloads. REIT
narrative extraction remains unsupported and legal-type coverage incomplete.
No 100-company financial acceptance or accepted sector model is claimed.

Tests: 383/383 local unittest tests passed on Python 3.12.14 (365 regressions +
18 new tests). Both replay scripts and git diff --check passed. Evidence:
registration-legal-tests.json. Coverage includes original SEC positive/negative
flags, namespace-bound ballot/constant transforms, absent vs false, duplicates,
wrong endpoint/CIK/form/date, future cutoff, dimensions, annual-vs-registration
separation and original hash/time retention. Exploratory import command lacked
PYTHONPATH and failed; corrected to PYTHONPATH=src. No regression/test failure.
GitHub Actions run 41433175246 passed 383 tests and CLI status on each Python
3.11/3.12/3.13; logs inspected.
PR: https://github.com/fatalvayn-dot/us-equity-research/pull/5
Code commit: https://github.com/fatalvayn-dot/us-equity-research/commit/a4e9cfda46e2c20bc3a9cbe12d052954ec43cc74
Actions: https://github.com/fatalvayn-dot/us-equity-research/actions/runs/41433175246
Source tree 8df7e63e4ba13ecc8e5f2c34b7c7d7ece4cb3681 exactly matched the
locally tested tree. Documentation follow-up CI is checked before merge;
final merge evidence is recorded in the PR discussion.

Primary transform references checked 2026-11-02:
https://www.sec.gov/files/edgar/filer-information/specifications/xbrl-guide-2026-08-14.pdf
https://www.xbrl.org/Specification/inlineXBRL-transformationRegistry/REC-2020-02-12/inlineXBRL-transformationRegistry-REC-2020-02-12.html
https://www.xbrl.org/Specification/inlineXBRL-transformationRegistry/REC-2022-02-16/inlineXBRL-transformationRegistry-REC-2022-02-16.html

Next concrete task: obtain explicit REIT annual-report narrative evidence for
Welltower with issuer/period/source anchoring and review status, then connect
positive/unknown legal disclosures to auditable universe exclusion/review outcomes.
Keep scope approval separate and do not extrapolate old registration status.
All stage acceptance gates beyond the tested infrastructure remain incomplete.

## 2026-11-02 — Literal annual legal-status disclosures (latest)

Branch: feat/annual-legal-evidence, based on main 8f000e4fa319aeeb01bf153e0b66be436aa9556d
(PR #3 merge). Fetched main, clean worktree, no open PRs; prior Actions run
41417581200 succeeded. No concurrent main change observed. radar-agent untouched;
no authorized archive operation is exposed.

Completed v0.19.0: annual_legal_evidence extracts the literal SEC DEI
EntityInvCompanyType and CEF BusinessDevelopmentCompanyFlag /
RegisteredClosedEndFundFlag disclosures, independently and without legal/scope
approval. The old lookalike EntityInvestmentCompanyType is not an alias. Official
DEI/CEF 2026 schemas were downloaded as reference artifacts and retained with
URL/hash/download completion times; the actual DEI enum includes N-5 as well as
the literal token S-1 or S-3. Concept types and enum are checked against those
recorded primary-source schemas in tests. No made-up REIT taxonomy flag.

Evidence requires original annual HTML response at an exact issuer SEC Archives
URL, original raw SHA and aware retrieval/cutoff. DocumentType, FY focus and end
must establish one explicit non-dimensional issuer duration. Only disclosures in
those exact verified annual document contexts may supply values. Inline XBRL,
context and concept namespaces are checked; namespace rebinding, lookalike
inline elements and forged context identifiers cannot supply legal disclosures.
Source URL query/fragment and future retrieval are rejected. Source observations
are never relabeled as earlier vintage. This remains report-specific evidence,
not proof that a legal status persists to the present day.

Literal true/false/1/0 and exact investment-company enum values are retained.
Missing/nil remains unknown; conflicting duplicate values yield no value;
unsupported transforms/text/namespaces yield no value. Same-value duplicates
retain both evidence rows. Unknown continuations/exclusions/truncation fail
closed. No free-text guessing, company-name classification or SIC override.
Every legal/scope/investment approval flag remains false. REIT explicitly stays
unsupported_requires_document_review: its extraction is not completed.

Recorded replay: 8 original annual documents rehashed against existing evidence;
0 reported legal disclosures, 24 unknown tagged fields, 8 unresolved REIT fields.
This negative availability result is not evidence that these issuers are not
investment companies/BDCs/REITs. The tag-only annual approach is insufficient to
complete legal-type coverage. No new financial/issuer HTTP requests; only two
fresh official taxonomy-reference downloads. Evidence: annual-legal-replay.json,
legal-taxonomy-sources.json, scripts/verify_legal_evidence.py. Replay retained
original retrieval times. No new live legal or 100-company financial acceptance.

Tests: 365/365 local unittest tests passed on Python 3.12.14: 347 regressions +
18 new tests. git diff --check passed. Evidence: annual-legal-tests.json.
Coverage includes primary-schema contracts, true vs false vs unknown, duplicates,
exact enum tokens, obsolete tag rejection, dimensions/unrelated contexts,
namespace spoofing/rebinding, transform/nil handling, wrong issuer/form/endpoint,
future retrieval, original source provenance and withheld approvals. First
364-test run passed; final enum/dimensional/schema assertions passed at 365.
No test failure. GitHub Actions run 41421812078 succeeded with 365 tests and
CLI status on each Python 3.11/3.12/3.13; job logs inspected.
PR: https://github.com/fatalvayn-dot/us-equity-research/pull/4
Code commit: https://github.com/fatalvayn-dot/us-equity-research/commit/54169db8a53b5e0ee2d2e240c9a7a491bdfde5cc
Actions: https://github.com/fatalvayn-dot/us-equity-research/actions/runs/41421812078
Published source tree 2db428352cac3483973a325d2ad1a8808ebf66f2 matched the
locally tested tree. Documentation follow-up CI must also pass before merge;
final merge evidence is recorded in the PR discussion.

Primary references checked 2026-11-02:
https://xbrl.sec.gov/dei/2026/dei-2026.xsd
https://xbrl.sec.gov/cef/2026/cef-2026.xsd
https://xbrl.sec.gov/cef/2026/cef-taxonomy-guide-2026-03-16.pdf

Remaining gates unchanged: live four-source acceptance, legal type, accepted
sector economics, valuation/risk and 100-company financial validation incomplete.
Next concrete task: acquire positive original BDC/closed-end registration examples
and add a separate disclosure-date-bound N-2 context path (not an annual-period
inference), plus explicit REIT annual-report narrative evidence requiring review.
Do not keep retrying absent annual tags or infer absence from missing disclosures.

## 2026-11-02 — SEC sector review routing and calculation guards (latest)

Branch: feat/sector-model-guards, based on main f444ec76ad535f499a5ea92ba48948cbbaf7f1cf
(PR #2 merge). Main fetched and clean, no open PRs at session start. Prior PR
Actions run 41411047536 succeeded across Python 3.11/3.12/3.13. No concurrent
source change observed. Legacy radar-agent untouched; no archive API exposed.

Completed v0.18.0: primary-response-bound sector review routing and a guarded
calculation entry point. SEC submissions response must have exact CIK/endpoint,
valid JSON/metadata, original raw hash and aware observation timestamp. Future
metadata and observations older than six hours fail closed in the guarded path.
SIC bank/insurance/6798 REIT signals receive distinct routes; other 67xx codes
receive investment-vehicle review without claiming BDC/fund legal status. Other
6xxx codes receive finance/real-estate review. Missing/malformed SIC is unknown;
other industries still require economic model validation. Neither issuer name
nor entityType=operating bypasses a financial SIC route. Untrusted source URLs
are not persisted as evidence. No aliasing of financial facts or source fallback
order was introduced. Existing calculate() remains arithmetic-only.

calculate_with_sector_guard keeps exact-input arithmetic and its provenance
separate from interpreted_value, which is withheld while no sector model is
accepted. Specialized routes require an appropriate model; unknown profiles
require evidence; other industries require model validation. All scope, generic
cash-flow eligibility, sector model support and investment flags remain false.
This is a routing/guard implementation, not accepted bank/insurance/REIT/BDC
valuation or generic FCF methodology. SIC alone is not legal-type approval.

Recorded replay: 100 original issuer responses rehashed against the existing
source evidence; 81 other-industry review, 10 banking signals, 3 insurance signals,
5 other finance/real-estate review, 1 REIT signal. Original observation times
were retained. These are recorded responses, not newly fetched current profiles.
All 64 exact calculation variants replayed: 24 arithmetic results, 40 without
complete exact operands; zero economic interpretations or investment approvals.
No new financial/provider HTTP requests, no 100-company financial acceptance.
Evidence: docs/evidence/sector-policy-replay.json and scripts/verify_sector_policy.py.
SIC route definitions were checked against the official SEC list on 2026-11-02:
https://www.sec.gov/search-filings/standard-industrial-classification-sic-code-list
The page is a reference for code meanings; broad routing ranges are our conservative
review policy, not a SEC-supplied investment or legal classification model.

Tests: 347/347 local unittest tests passed on Python 3.12.14 (329 regressions +
18 new tests); git diff --check passed. Test evidence: sector-policy-tests.json.
New coverage includes real recorded JPM/Chubb/Welltower/Goldman metadata, missing
and malformed SIC, banking/insurance/REIT/investment signals, issuer/endpoint
mismatch, duplicate JSON, stale/future timestamps, evidence preservation, exact
cash arithmetic separated from withheld interpretation and missing operands.
No test failures. GitHub Actions run 41417365684 completed successfully, with
347 tests and CLI status passing on each of Python 3.11, 3.12 and 3.13; logs inspected.
PR: https://github.com/fatalvayn-dot/us-equity-research/pull/3
Code commit: https://github.com/fatalvayn-dot/us-equity-research/commit/5a5d3989887d4f660cafef65275c457603f3fdcb
Actions: https://github.com/fatalvayn-dot/us-equity-research/actions/runs/41417365684
Source tree 165ec8c5572a6d3c3fad17f0380ff65047c9ab81 matched the locally tested
tree exactly. Documentation follow-up CI is checked before merge; the final
merge result is recorded in the PR discussion.

Remaining gates unchanged: four-source live acceptance (Finnhub unverified),
security legal type, economic sector models, valuation/risk and 100-company
financial acceptance are incomplete; no ranking/backtest/full-universe claim.

Next concrete task: extract explicit issuer-level SEC annual-document evidence
for investment-company/BDC/REIT legal status with context/period checks; preserve
unknown when absent or conflicting, then select and validate the first sector
model independently of scope approval. Do not infer BDC absence from SIC.

## 2026-11-02 — GitHub import after access became available (latest)

Target repository is now accessible with push/admin permission. Existing main
commit de31dcbeaf131ab641e58a2601ff5f4cc28bc191 contains the initial README only;
PROJECT_BRIEF and DEVELOPMENT_STATUS were absent. Open PR #1 was inspected at
7905bac948df1e10b4184c0bcabe2c65828ed42c. Its independent quality module and five
tests are preserved verbatim in this import; its branch was not overwritten.
No Actions runs were returned for either inspected commit. No concurrent main
change was observed before branching. radar-agent remains untouched because no
authorized archive API is exposed. Repository is already public; visibility was
not changed. No repository creation, force push or unrelated-root merge used.

Imported the complete tracked v0.17.0 checkpoint (3d0c9b07b14ce788d5875ed82919d72730331cc8),
recorded public response fixtures, original test evidence, project brief and
three-version Python CI workflow onto a feature branch rooted at existing main.
Operational SQLite caches, secrets, Git bundle and temporary files are excluded.
Prior local history remains in the existing checkpoint rather than replacing
the remote root. PR #1 provenance: https://github.com/fatalvayn-dot/us-equity-research/pull/1.

Tests: 329/329 local unittest tests passed on Python 3.12.14 (324 checkpoint
regressions plus 5 preserved PR #1 tests). This is an offline regression replay,
not a new live financial verification. GitHub Actions run 41410885189 completed successfully: Python 3.11, 3.12
and 3.13 each passed 329 tests and the CLI status check. Logs were inspected.
PR: https://github.com/fatalvayn-dot/us-equity-research/pull/2
Import commit: https://github.com/fatalvayn-dot/us-equity-research/commit/5ed373198f9462d2ca70cbeb36b0f81ec1861609
Actions: https://github.com/fatalvayn-dot/us-equity-research/actions/runs/41410885189
This documentation follow-up is checked separately before merging PR #2;
its final merge result will also be recorded in the PR discussion.

No new live requests or company acceptance. Stage 1 architecture/model/test
baseline is imported; stage 2 remains partial and sector economics, valuation,
risk, 100-company financial acceptance and all later gates remain incomplete.
The previous status entries describe evidence at the time of each local run;
their GitHub-access blocker is resolved by this import. Finnhub live validation
still lacks an existing configured key. No paid service or permission requested.

Failed transport attempt: git.chatgpt-team.site requested unavailable credentials.
Public GitHub fetch plus the authorized GitHub object/ref API succeeded instead.
Published tree 3312580b94f6bc0cd045bc126acdccecc2804594 exactly matched the
local tree tested above. No force push or authentication change was needed.

Next: add sector/profile model
eligibility using primary SEC metadata; unknown/bank/insurance/REIT/BDC profiles
must not acquire generic cash-flow interpretation or investment approval.

## 2026-11-02 — Traceable exact-input financial arithmetic (latest)

Branch: feat/traceable-calculations, based on local 4f899d6 checkpoint.
Code commit: e9761d0b1393c5d5a20152aec0742c1ff21dd957 (local only).
Final checkpoint commit is in delivery CHECKPOINT.txt. Fresh target metadata
returned 404; main, open PRs and Actions cannot be inspected. No repository-create/
archive operation exposed; radar-agent untouched. No push/PR/merge/Actions run;
remote evidence links unavailable. Version 15 retained ZIP passed all CRC checks
and its status matched the clean local baseline before branching. No concurrent
Git change observed. The prior truncated-ZIP issue is resolved for this baseline.

Completed v0.17.0: frozen eight-formula arithmetic registry distinguishes exact
NetIncomeLoss/ProfitLoss and contract-revenue/total-Revenues margins, OCF margins,
and cash after PP&E vs ProductiveAssets payments. No implicit alternate field,
calendar normalization, annualization, score threshold or owner-earnings label.
Caller specifies CIK, exact duration, currency and aware cutoff. Each operand
must match its literal field/accounting identity and FactRequest chronology,
including publication and original retrieval. A raw-source SHA is required.
Full input facts/provenance and semantic-review flags accompany results.

Typed no-value outcomes cover missing fields, invalid identity/definition/period/
currency, future observation/publication, missing source evidence, nonpositive
ratio denominators, unsupported negative payment sign and excessive magnitude.
Genuine zero payments and negative profit/cash arithmetic remain valid; nothing
is floored, filled or clamped. Ratio results are dimensionless, with input
currency retained separately; subtraction results retain currency. Decimal
precision is local and sufficient for exact large-value subtraction. No global
rounding state or financial provider fallback changes a calculation.

Recorded eight-company sample: 64 explicitly requested formula variants, 24
calculated_arithmetic_only results and 40 pending_data variants. The pending
variants lack the exact requested operands, including intentional alternative
accounting families; no replacement is attempted. All eight companies have
three available arithmetic results. Inputs combine the prior source-archived
facts and separately verified literal supplemental fields. No new financial
HTTP request or live-source acceptance run. Cutoff covers original observed
facts; this is not proof of historical-vintage/backtest eligibility.
Evidence: calculation-sample.json, scripts/verify_calculations.py. Complete
inputs, exact formula/date/currency/cutoff and original source hashes are retained.

Every calculation explicitly keeps sector_model_supported, scope_approved and
investment_approved false. This layer validates arithmetic and input contracts,
not sector economics, valuation, risk ratings, statistical prediction or a
100-point score. Cash after specified payments is not presented as a universally
complete FCF or owner-earnings definition. Sector dispatch/eligibility must be
validated before ratios can support investment interpretation. Existing source,
legal-type, missing narrower fields and AMZN direct-liability gaps are unchanged.

Tests: 324/324 local tests passed on Python 3.12.14 (309 regressions + 15 contracts).
Coverage includes exact ratio/cash arithmetic, real zero vs missing, negative
profit, denominator/sign guards, exact definition vs broader alias, cross-company/
period/currency isolation, future-data cutoff rejection, provenance requirements,
isolated Decimal precision and recorded-input reproducibility for all 24 results.
Synthetic known-answer arithmetic tests and recorded replay are not sector-model
acceptance or independent validation of economic usefulness. git diff --check
passed. Evidence: calculation-tests.json. No remote Actions execution.

Failures/limits: no test failure. Forty formula variants remain without numeric
outputs because their exact required fields are unavailable. The original five
narrow field gaps remain; no amount of supplemental arithmetic fills them.
Sectors/financial institutions/REIT/BDC-specific treatment, market-price valuation,
risk models and scoring are still absent. Existing GitHub/Finnhub configuration
blockers unchanged. No paid service, new access, real-money action or new user
operation requested. Archive delivery uses the verified unique-path builder;
retained-byte comparison occurs separately after this commit.

Acceptance: stage 1 offline verified/remote CI pending; stage 2 partial and
four-source live acceptance pending. This is a stage-3 arithmetic prototype,
not accepted stage 3: valuation/risk/sector validation missing and prior gate
incomplete. No 100-company, active approved universe, scoring/backtest/full-universe
or final acceptance. Partial arithmetic success is not full-system completion.

Next concrete task: implement source-backed sector/profile eligibility and
calculation dispatch, explicitly isolating banks, insurers, REITs/BDCs and unknown
issuer types from generic cash-flow interpretation. Test profiles/readiness with
real saved SEC metadata and unsupported-sector cases before any economic score.
Continue affirmative fund/legal-type review, exact missing-field resolution and
bounded annual-source expansion. Keep all acceptance gates explicit.

---

## 2026-11-02 — Distinct accounting fields and immutable checkpoint recovery (latest)

Branch: feat/distinct-accounting-fields, based on local fe31d10 checkpoint.
Code commit: 1332a97561d8d46bebd24c4c92e55df47392d0b6 (local only).
Final checkpoint commit is in delivery CHECKPOINT.txt. Fresh target metadata
returned 404; main, open PRs and Actions cannot be inspected. No repository-create
or archive operation exposed; radar-agent untouched. No push/PR/merge/Actions;
remote evidence links unavailable. Worktree was clean before branching; no
concurrent Git edits observed.

Checkpoint issue: latest materialized version 14 ZIP and the canonical local
ZIP were both 27,687,574 bytes with ZIP header but missing/invalid central directory.
Their cause of truncation is not established. Latest ZIP contents could not be
compared with local status. Surviving Git HEAD fe31d10, source/evidence and prior
valid version 13 materialization remained intact; the prior ZIP CRC check passed
and all 296 baseline tests passed before adding new tests. Development continued
from that known local committed history, not from a guessed reconstruction of
corrupt bytes. Operational public evidence databases remain available separately.

Completed v0.16.0: immutable FieldSpec registry owns nine exact accounting fields.
Original revenue (ExcludingAssessedTax), net_income (NetIncomeLoss) and
capital_expenditure (PP&E payments) are unchanged. New independent names:
revenue_total→us-gaap:Revenues; profit_loss→us-gaap:ProfitLoss;
productive_asset_cash_payments→us-gaap:PaymentsToAcquireProductiveAssets.
SEC exact requests, CLI choices and explicit batch plans support them. No aliases,
summing or automatic equivalence to the narrower concepts were introduced.
Finnhub now explicitly rejects fields without a verified section mapping before
HTTP, preventing a new registry entry from falling through into a KeyError.
Yahoo/Nasdaq new fields remain explicitly unsupported; no unearned coverage claim.

Accounting readiness checks exact required names/definitions, instant/duration
shape and common issuer/end/currency/duration-start context. Mixed periods,
companies/currencies and incorrectly keyed facts do not become complete model
inputs. Missing narrower fields cannot be filled by broader facts in a mapping.
New definitions retain semantic-model-review flags. Even complete inputs are
model-validation-pending, with sector_model_supported and investment_approved false.
No sector valuation model, financial score or suitability approval was generated.

Recorded real-response verification: five new independently requested SEC fields
from four companies matched the exact same literal concepts in original annual
documents: NVDA Revenues and ProductiveAssets payments; GOOGL Revenues; AMZN
ProductiveAssets payments; AVGO ProfitLoss. This is a recorded-response replay at
original observation times, not a new live download. Yahoo returns unsupported,
SEC valid; deferred lower providers are never constructed. No new financial HTTP
request. Full facts include source, CIK, period, USD, filing/accession, original
observation/publication, accounting definition and raw-response hash. Original
filing URLs/hashes/timestamps/context evidence retained. Five prior narrower
fields remain pending; old sample stays 43/48. Supplemental 5/5 distinct values
must not be labelled as filling those five missing inputs or 100-company acceptance.
Evidence: distinct-accounting-fields.json and scripts/verify_distinct_fields.py.

Tests: 309/309 local tests passed on Python 3.12.14 (296 regressions + 13 contracts).
Coverage includes immutable registry, unchanged old definitions, explicit plans,
wrong-definition rejection, no alias fill, mixed company/period/currency context,
instant/duration mismatch, unsupported sources before HTTP, exact five original
matches and source stopping. git diff --check passed. Evidence:
distinct-fields-tests.json. Local tests are not Actions or live four-provider tests.

Added scripts/build_checkpoint.py to prevent upload-source path reuse: clean
committed worktree required, unique output directory, complete verified Git bundle,
known public SQLite backup/integrity checks, exclusive ZIP creation, full CRC and
commit-marker verification, plus external SHA-256 manifest. Final archive tests
and retained-copy verification happen after this status commit and are separate
from the 309 unit/regression results. Preserve the immutable upload path; verify
retained bytes before updating a convenience link. Do not infer ZIP health solely
from tests of the local Python source. Future sessions must retain this procedure.

Failures/limits: corrupt latest ZIP detected and explicitly retained as a failed
attempt; rebuilding from valid source/Git avoids silently propagating it. No test
failure. Only SEC bindings for the new literal concepts verified by recorded data;
other mappings and Finnhub live remain unaccepted. Broader labels do not establish
common-share profit attribution, tax or PP&E-only scope. AMZN direct total
liabilities still unresolved, arithmetic candidate unapproved. No new paid service,
privilege, credential exposure, real-money action or user request. Existing remote
and Finnhub configuration blockers unchanged.

Acceptance: stage 1 offline verified/remote CI pending; stage 2 partial. No sector
model/scoring, 100-company financial acceptance, legal active universe, backtest,
full-universe or final acceptance. Partial new fields do not complete stages 3–8.

Next concrete task: consume explicitly selected accounting specifications in
sector-aware financial calculations, with exact-definition/period comparability
checks and no implicit alternate-field substitution. First implement and test a
small calculation model on the verified sample while keeping source/model gates
unaccepted. Continue affirmative legal-type review, AMZN liability-scope review
and bounded expansion from the 90 unstarted annual documents. Always build/upload
from a unique verified checkpoint path and validate the retained copy.

---

## 2026-11-02 — Original duration reconciliation and accounting-concept diagnostics (latest)

Branch: feat/original-concept-diagnostics, based on local 70c194c checkpoint.
Code commit: d16fa183f4399632e5702da5702496ef005fc74c (local only).
Final checkpoint commit is in delivery CHECKPOINT.txt. Fresh target GitHub
metadata check returned 404; main, PRs and Actions cannot be inspected. No
repository-create/archive operation exposed; legacy radar-agent untouched.
No push/PR/merge/Actions execution; remote evidence links unavailable. Version 13
checkpoint matched clean local status before branching; no concurrent change found.

Completed v0.15.0: isolated original iXBRL concept inventory and duration checker.
It requires literal standard concept identity, CIK, exact start/end or instant,
non-dimensional context and explicit USD unit/namespace. Known numeric transform
namespaces, Decimal scale/sign, strict grouping and precision are validated.
Conflicting context/unit IDs, missing IDs, nil/dash, unsupported presentation,
unknown transform namespaces or competing values cannot silently yield a number.
An unsupported requested-context duplicate cannot be hidden by one parseable fact.
Absent concept, dimensional-only, period/scope mismatch and unsupported numeric/unit
cases remain distinct. Diagnostic alternatives never enter the resolver as
request-equivalent facts. No accepted data value or scoring rule was changed.

Actual original-response replay: all 27 previously collected duration values
(revenue/net income/operating cash flow/capex) for the eight-company sample matched
exact original annual facts. Of 32 duration requests, five remain uncollected;
there are zero numeric mismatches and zero unresolved original comparisons for
the 27 collected values. Combined with the previous 15 instant balance matches,
42 of the 43 collected sample values now have direct original-document numeric
matches. The remaining AMZN direct Liabilities check remains unresolved. These
are numeric checks, not complete financial/model/legal-type acceptance.
Evidence: original-concept-diagnostics.json, archived annual fixtures, exact source
URLs/hashes/original retrieval dates included. No new financial HTTP request was
made: all diagnostics reuse previously recorded original source bytes and dates.

The five gaps are now distinguished using original contexts: NVDA does not
present the requested ExcludingAssessedTax revenue or PP&E-only cash capex concepts
in the original annual document; it does present literal Revenues and
PaymentsToAcquireProductiveAssets facts. GOOGL's requested ExcludingAssessedTax
revenue appears only in dimensional contexts; consolidated Revenues is separate.
AMZN has ProductiveAssets payments, not the requested PP&E-only concept. AVGO
has ProfitLoss, not the requested NetIncomeLoss. Exact candidate amounts/context
IDs/taxonomy identities are retained, without asserting semantic equivalence or
replacing the five pending fields. This is not proof of global data absence;
other unqueried sources or custom taxonomies may contain additional evidence.

AMZN balance diagnostic: original LiabilitiesAndStockholdersEquity minus original
StockholdersEquity gives 406977000000 USD, equal to the collected Nasdaq amount.
Both operands are direct exact non-dimensional USD instant facts for 2025-12-31.
The result is explicitly an arithmetic candidate requiring scope/mezzanine review,
not a disclosed us-gaap:Liabilities fact, approved derivation or cleared original
Liabilities match. Missing potential components are never assumed zero. Prior
15/16 direct balance report remains unchanged; no retroactive success label.

Tests: 296/296 local tests passed on Python 3.12.14 (280 regressions + 16 new
contracts), including exact scale/sign/precision, dimensional/foreign-issuer
isolation, no alternate-concept mapping, contradictory and unsupported duplicates,
nil/continuation/unit/transform rejection, namespace/ID integrity, instant/duration
separation, full eight-original-source replay and unaccepted arithmetic candidate.
git diff --check passed. Evidence: concept-diagnostic-tests.json. No Actions or
new live financial/source acceptance claimed.

Failures/limits: no test failure. Five requested fields remain pending by design
because alternative concepts are not established equivalents. AMZN direct total
remains unresolved despite matching arithmetic candidate. Only constrained USD
US-GAAP numeric transforms are supported; IFRS/custom taxonomies, continuations,
long transition periods, legal type and sector models still require work. Current
collected count remains 43/48. No API quota/error response was fabricated as absence.
Existing remote/Finnhub configuration blockers unchanged; no new user action,
paid service, permission, secret exposure or real-money operation.

Acceptance: stage 1 offline verified/remote CI pending; stage 2 partial. Four-source
live acceptance/Finnhub and broad mappings remain pending. No 100-company financial,
active approved universe, sector-model/scoring/backtest/full-universe or final
acceptance. Original numeric matches do not complete stages 3–8.

Next concrete task: introduce explicitly distinct accounting field specifications
for consolidated Revenues, ProfitLoss and ProductiveAssets cash payments, without
aliasing them to the existing narrower fields. Test/provider-bind them with source
provenance and sector-model readiness rules before using them in analysis. Review
AMZN liability scope/mezzanine evidence before any approved derived liability.
Continue bounded annual-source expansion and affirmative fund/legal-type checks.

---

## 2026-11-02 — Exact raw financial response archive and original balance checks (latest)

Branch: feat/raw-response-archive, based on local 49484a2 checkpoint.
Code commit: 39953494066d7f2fc6c3bf49342dbb5045c623b5 (local only).
Final checkpoint commit is in delivery CHECKPOINT.txt. Fresh target metadata
check returned 404; main, open PRs and Actions remain inaccessible. No repository
create/archive operation exposed; radar-agent untouched. No push/PR/merge/Actions
executed; remote evidence links unavailable. Version 12 checkpoint matched clean
local status before branching. No concurrent local changes were observed.

Completed v0.14.0: ResponseArchive stores content-addressed raw public response
bytes plus separate exact URL/hash/original-time observations in transactional
SQLite. Integrity is checked on read and duplicate writes; timestamp-specific
lookup cannot substitute a later observation. ArchivedTransport captures successful
bounded unauthenticated responses without request headers. Authenticated clients,
non-public origins and credential-bearing query names are rejected before I/O.
Archive write failure now has distinct evidence_error status, not API_ERROR.
Finnhub/authenticated capture is not accepted or silently enabled.

Optional archive wiring preserves lazy Yahoo→SEC→Nasdaq→Finnhub resolution and
first-valid stopping. ArchivedCompanyFacts records original disk/memory SEC
snapshots too, with no artificial retrieval refresh or extra HTTP request.
The legacy/default resolver behavior is retained when no archive is supplied.
Scripts export content-addressed compressed bodies and complete observations;
no API credential or request header is in these artifacts.

Actual live ordered sample: fresh financial collection for the same eight
companies again yielded 43 collected/48 requested fields, five pending as before.
All 43 accepted facts now have exact archived main financial response, identity
and (where required) unit evidence at the original observation instants. Nineteen
public observations exported with raw bytes. Original SEC cached observations
were imported without changing their timestamps; Yahoo/Nasdaq current responses
were captured as requested. This proves coverage for this new run, not retroactive
recovery of every missing raw byte from prior runs. Financial report retains its
actual pre-release policy version; final package is v0.14.0. No numeric/scoring
rule or missing-data standard was relaxed to obtain coverage.
Evidence: archived-eight-financial.json, financial-response-{manifest,coverage}.json.
All-reference coverage is true for 43 facts; this is not 43 independent filing
value checks, a historical availability database or financial model acceptance.

Independent original annual iXBRL balances: 16 Assets/Liabilities comparisons for
eight companies, 15 exact Decimal matches and one unresolved original-concept
check. AMZN Liabilities (Nasdaq collected 406977000000 USD, 2025-12-31) could not
be extracted by the narrow original us-gaap:Liabilities parser. This is invalid_data
in the original-check path, not a proven numeric mismatch or an accepted match.
No accounting-identity reconstruction, tag substitution, zero or invented value
was used. Exact original source URL/hash/time/fixture accompanies each check.
Evidence: eight-original-balances.json. Five added companies now have limited
original balance evidence; income/cash-flow, legal type and sector model checks
remain unaccepted. Independent comparison reuses existing filing bytes and does
not query lower-priority financial providers after a successful field result.

Tests: 280/280 local tests passed on Python 3.12.14 (267 prior regressions + 13
contracts). Coverage: restart/exact-time retrieval, body deduplication/integrity,
credential/origin/header exclusions, archive failure classification, cached SEC
capture without network/time refresh, every exact response reference for 43 facts,
and separate unresolved balance result. git diff --check passed. Evidence:
raw-response-tests.json. No remote Actions or final acceptance run.

Failures/limits: one original-concept check unresolved as above; five financial
fields still lack exact accepted values and Finnhub remains unconfigured/live
unverified. Failed HTTP response bodies are not captured; authenticated-source
capture needs separate handling and is deliberately unavailable. Archive is an
evidence store, not provider freshness cache or a point-in-time/backtest database.
Existing GitHub/Finnhub configuration blockers unchanged. No paid service, new
permission, real-money action or new user requirement.

Acceptance: stage 1 offline verified/remote CI pending; stage 2 partial. All
100-company, legal active-universe, sector-model, scoring/backtest/full-universe
and final gates remain unaccepted. Eight-company collection and 15 matches do
not complete stages 3–8. No partial success is labelled full completion.

Next concrete task: investigate original AMZN liability disclosure and the five
unresolved exact-tag fields with explicit accounting-definition/unit evidence.
Extend original-filing numeric checks beyond instant balances, keeping unsupported
or custom taxonomies separate. Continue bounded annual-source expansion from the
90 unstarted documents and affirmative fund/legal-type corroboration; preserve
acceptance order and do not fabricate scores for incomplete companies.

---

## 2026-11-02 — Resumable annual documents and eight-company financial run (latest)

Branch: feat/resumable-filing-documents, based on local a4ec919 checkpoint.
Code commit: 8ca29c40c2c4e3af8967cd7c90187a243bf78e80 (local only).
Final checkpoint commit is in delivery CHECKPOINT.txt. Target metadata freshly
returned 404; main, open PRs and Actions cannot be inspected. Repository-create
and archive operations remain absent; radar-agent untouched. No push/PR/merge/
Actions occurred; remote evidence links unavailable. Version 11 checkpoint matched
the clean local baseline before branching; no concurrent local change observed.

Completed v0.13.0: FilingStore/DocumentRunner with exact issuer/filing/path/date
validation before network I/O, raw-byte/source-hash/original-time SQLite checkpoints,
six-hour freshness and a bounded new-request budget. Atomic per-document outcomes
are versioned and saved separately from raw sources. Current parsers recompute
from cached bytes; no old derived success silently bypasses changed code. Same-file
renewable leases block concurrent work and expired-owner writes. KeyboardInterrupt
keeps earlier committed sources/outcomes; hard kills may require lease expiry.
Missing annual metadata, unsupported formats, unstarted jobs, source errors and
independent period/share parser outcomes remain separate. Failed HTTP outcomes
are persisted but not reused as successful raw sources.

Actual original annual collection: 3 existing source fixtures were imported with
original hashes/times, then 5 new annual reports were downloaded. The eight
companies are NVDA, AAPL, MSFT, GOOGL, AMZN, AVGO, META and TSLA. All eight yield
explicit annual period pairs and exact common-share contexts. Immediate repeat
with max-new-documents=0 reused 8 raw sources, made zero transport GETs and
recomputed both parsers. Full 100-candidate queue remains visible: 8 source
checks, 90 annual documents not started, 2 without annual in recent metadata.
No legal/fund-type approval follows from those eight common-title checks.
Evidence: annual-document-{batch,resume}.json and content-addressed source fixtures.
New-document count measures GET invocations including failures, excluding internal
HTTP retries; unqueried documents are never marked attempted.

Real financial collection using explicit annual periods: 48 field requests for
8 companies; 43 collected and 5 pending. Sources of accepted facts: SEC 37,
Yahoo Assets 5, Nasdaq 1. Every fact retains exact issuer/date/definition/unit,
source URL/hash and observation/publication provenance. Pending fields: NVDA
revenue/capex, GOOGL revenue, AMZN capex, AVGO net_income. In all five, SEC exact
tag/period observations were absent, Yahoo/Nasdaq unsupported and Finnhub not
configured. This is unresolved data, not proof that all sources lack it. No zero,
substitute tag, invented score or complete-company approval was supplied.
The financial CLI returned exit 2, as expected for pending fields.

Immediate financial resume reused all 48 outcomes, with 0 new fields and 0 HTTP
GETs under a guard that would raise on any request (no substitute responses).
Original evidence times retained. Evidence: annual-eight-financial{,-resume}.json,
eight-financial-resume-proof.json and annual-eight-plan.json. The five missing
outcomes use the existing short retry delay; they are not permanent exclusions.
Eight SEC original response bodies/hashes/times are retained in expanded fixtures.
Expanded Yahoo/Nasdaq facts have URL/hash provenance, but not every new raw body
was captured during this run; complete raw replay coverage for those observations
is a next task. No independent original-filing numeric reconciliation for the
five added companies is claimed. This is collection evidence, not financial-model
or real 100-company acceptance.

Tests: 267/267 local tests passed on Python 3.12.14 (253 regressions + 14 new
contracts), including bounded restart, interruption, corrupt/stale source cache,
persisted typed 429, active lease/expired writer rejection, path/origin/future
validation, missing metadata vs unsupported document, no scope promotion, eight
recorded source replays and 48-query plan readiness. git diff --check passed.
Evidence: document-checkpoint-tests.json. No remote Actions run.

Failures/limits: no new offline test failure. Five unresolved financial fields
and the unconfigured fallback remain as described. Original bytes are retained
for all annual sources and SEC snapshots; expanded Yahoo/Nasdaq raw coverage
still incomplete. Document failure outcomes are diagnostic, not a retry scheduler;
transport failure retries use the existing bounded transport. Separate database
files do not share a lease. Existing GitHub/Finnhub-key blockers unchanged; no
new user action, paid service, privilege or real-money operation requested.

Acceptance: stage 1 offline verified/remote CI pending; stage 2 partial. Finnhub
live, broad source mappings and full source replay remain unaccepted. Stages 3–8,
100-company financial validation, legal active universe, sector models/scoring,
backtests/full-universe/final acceptance remain unaccepted. No partial result is
labelled complete.

Next concrete task: add durable raw-response capture for expanded Yahoo/Nasdaq
observations and independent original-filing numeric checks for the five added
companies. Investigate the five exact-tag gaps without substitution assumptions.
Continue annual-document collection with bounded new work from the remaining
90 records, retain legal-type/fund/sector uncertainty, and build the verified
100-company sample only after source/model acceptance gates pass.

---

## 2026-11-02 — Original annual duration contexts (latest)

Branch: feat/annual-period-contexts, based on local 30a8736 checkpoint.
Code commit: 9fca96df1b8ed3e3bb4986a71842e77913b9ef83 (local only).
Final checkpoint commit is recorded in delivery CHECKPOINT.txt. No remote
commit/PR/Actions links exist. Target metadata freshly returned 404; main, PRs
and Actions remain inaccessible. Repository-create/archive operations are still
not exposed; radar-agent untouched. Version 10 checkpoint matched clean local
status before branching. No concurrent local changes were present.

Completed v0.12.0: exact annual duration evidence from original filing contexts.
Requires non-dimensional issuer CIK, exact annual document type, FY focus and
matching DocumentPeriodEndDate in the same duration context. One unique explicit
start/end pair required; competing starts, missing starts, quarterly focus, wrong
identity, nil/truncated/future-mismatched contexts and durations over 550 days
remain unsupported. No fiscal start is calculated from a calendar or report end.
Multiple equivalent contexts can corroborate the same pair. Inline English date
normalization is shared with the registered-security parser.

Fixed an observed nested nonNumeric bug: an untracked inner CurrentFiscalYearEndDate
closed the tracked outer DocumentPeriodEndDate too soon, losing its year. A fact
stack now retains parent/child text correctly. Unsupported continuedAt/exclude
content fails rather than being guessed. The existing three quarterly filing
regressions remain successful. This remains a narrow evidence parser, not a
complete XBRL engine or a fund/legal-type classifier.

Real requests: three original annual HTML filings were freshly downloaded from
submission-derived www.sec.gov archive URLs; hashes, retrieval instants and full
compressed bytes retained. NVDA 10-K: 2025-01-27 to 2026-01-25; AAPL 10-K:
2024-09-29 to 2025-09-27; MSFT 10-K: 2025-07-01 to 2026-06-30. Context starts
are explicit and match the prior three-company extraction's annual starts.
These are the same three sample companies, not three additional accepted firms.

Initial live parse: three period contexts, zero registered-share matches; the
nested-date truncation caused invalid_data in cover validation. Original outcomes
are retained in annual-filings-live.json. After correction, replaying those same
recorded bytes with original provenance yielded three exact period pairs and
three registered common-share matches, with zero additional HTTP requests.
Corrected replay is separate: annual-filings-replay.json. No new live request is
implied by that replay. No source was relabelled or fiscal date fabricated.

Prepared annual-three-plan.json with explicit durations for income/cash-flow and
instant dates for Assets/Liabilities. All scope statuses remain pending. No
financial value requests were executed in this run; no new four-provider or
100-company financial acceptance. No fund exclusion, sector model or investment
suitability follows from a common-share title/document period.

Tests: 253/253 local tests passed on Python 3.12.14 (239 prior regressions and
14 new contracts), including explicit week-calendar starts, same-context FY,
wrong issuer, nil/dimensional/truncated content, competing starts, unsupported
continuation, nested date text, three original annual documents and an exact
six-field plan with instant/duration separation. git diff --check passed.
Evidence: annual-context-tests.json. These are not remote Actions results.

Failed attempts and limits: initial nested date parse invalid_data retained and
fixed as above. Only three of 98 annual-document candidates were requested; the
other 95 were not queried. Two earlier candidates still lack base annual records
in the recent submissions window. Legal fund/BDC/REIT classification and broad
registered-class/foreign-accounting support remain unresolved. Over-550-day
transition periods and unsupported inline transformations require later work.
Existing remote and Finnhub-key blockers unchanged. No paid service, new access,
secret exposure or real-money action. No PR/push/merge/Actions execution occurred.

Acceptance: stage 1 offline verified/remote CI pending. Stage 2 partial; Finnhub
live and broader financial mappings still unaccepted. Annual sample evidence
does not complete stages 3–8 or a 100-company financial test. Active approved
universe, sector models, scoring/backtests and final acceptance remain pending.

Next concrete task: extend bounded annual-document evidence collection to the
remaining candidate queue with persisted per-document outcomes/reuse, and add
primary fund/legal-type corroboration. Use the validated period pairs to collect
financial facts via the existing ordered resolver, retaining missing/unsupported
foreign and sector cases; keep acceptance gates and scope approvals separate.

---

## 2026-11-02 — SEC submissions and registered-share evidence (latest)

Branch: feat/sec-submissions-evidence, based on local e5ba25c checkpoint.
Code commit: 2a2cd8d53f60fb306af9f249348ba6696a9adcf6 (local only).
Final checkpoint commit is in delivery CHECKPOINT.txt. No remote commit/PR/Actions
links: target metadata freshly returned 404; main, open PRs and Actions could not
be inspected. No repository-create/archive tool exposed; legacy project untouched.
No remote push, PR, merge or Actions execution. Version 9 checkpoint matched the
clean local baseline before branching; no concurrent local changes were present.

Completed v0.11.0: bounded SEC submissions adapter with exact CIK/origin checks,
strict complete column alignment, duplicate accession rejection, explicit annual
report-end selection, safe primary-document URLs, raw entity/SIC labels and
original source bytes/hash/time. Six-hour SQLite metadata cache persists original
observations across restarts. Corrupt entries refresh safely. Additional history
pointers are counted but not queried; recent-window absence is not global absence.
10-K/20-F/40-F kept distinct; amendments do not create a new annual period. Legacy
non-HTML documents are labelled unsupported, never fed to an HTML parser.
Acceptance time labels are preserved raw, never used as intraday/backtest truth.

Added a narrow original-filing cover parser: exact issuer, document date/type,
and same-context registered symbol/common-title/exchange evidence, including
share-class contexts. DEI namespace is checked; supported inline English date
transformation is explicit. Non-common notes/preferred/depositary/units sharing
a ticker cannot supply common-share evidence. Raw checkbox labels are retained
without interpreting their rendered glyphs as booleans. This is corroboration,
not fund exclusion, legal-type approval, sector-model approval or a scope grant.

Real metadata collection: all 100 candidate CIK responses were downloaded and
retained as compressed fixtures on 2026-11-02. First pass: 99 parsed and TTE
invalid_data due to a legacy .paper document in older recent-window history.
After the narrow unsupported-format correction, repeated collection used 99
original-observation cache entries and one new TTE transport GET. All 100 then
matched exact symbols/CIKs; 98 have explicit annual report-end dates. Two have
no base annual in the returned recent window; they remain unresolved and older
pages were not tried. No annual start or reporting currency was inferred.
Evidence: sample100-submissions-{first-pass,live}.json and 100 raw fixtures.
This is metadata validation only; no new 100-company financial values or source
financial acceptance. Entity type operating/other and SIC descriptions are raw
labels; BDC/REIT/fund distinctions need further primary evidence/model review.

Prepared an unapproved 98-company/196-instant-query draft using only the explicit
annual ends. USD is a requested unit, not inferred reporting currency. Duration
starts remain unknown, two candidates remain queued, all scope statuses pending.
No draft financial query was executed in this run. Evidence:
sample-annual-end-plan.json, scripts/prepare_annual_end_plan.py.

Registered security corroboration: existing AAPL/MSFT/NVDA quarterly filing bytes
were replayed; all three yielded one exact common-share title/symbol/exchange
match. MSFT notes sharing its ticker were excluded from the common-title join.
Exact quarterly dates: AAPL 2026-06-27, MSFT 2026-09-30, NVDA 2026-07-26.
These differ from prior annual balance-sheet comparison dates. Original source
URL/hash/retrieval/fixture provenance is included in registered-share-replay.json.
No new live filing download or additional company financial acceptance is claimed.

Tests: 239/239 local tests passed on Python 3.12.14 (209 regressions + 30 new
contracts). Coverage includes source identity, column drift, unsafe documents,
future periods, unsupported legacy files, exact-end annual selection, snapshot
cache restart/expiry/corruption, per-class cover joins, wrong issuer/date/form,
inline dates, nil/conflicting facts, three original filings, all 100 recorded
metadata responses and the 98-company instant-only plan. git diff --check passed.
Evidence: submissions-tests.json. Local tests are not Actions or final acceptance.

Failed attempts: TTE legacy paper metadata initially rejected; fixed and retried
with new response, retaining first-pass evidence. Initial cover trial used annual
comparison dates against quarterly documents and was rejected; corrected to each
document's explicit quarterly date, never relabelled annual. Network collection
continued independently of this parser work. No fabricated zero, secret, paid
service, new privilege or real-money action. Existing remote/key blockers unchanged.

Acceptance: stage 1 offline verified/remote CI pending; stage 2 partial (Finnhub
live still unverified; limited field coverage). All 100 still require legal-type
corroboration; 98 report ends are not a completed financial analysis. Stages 3–8,
100-company financial acceptance, scoring/backtests/full universe remain unaccepted.

Next concrete task: collect bounded original annual-document evidence for the
candidate queue, corroborate registered common classes and fund/legal-type flags,
and extract explicit fiscal start/end pairs from appropriate filing contexts.
Retain foreign-accounting/financial/REIT/BDC cases for sector-specific treatment.
Then execute exact-period financial batches with missing-data reconciliation;
do not mark stage 4 accepted before preceding source/model acceptance gates.

---

## 2026-11-02 — Primary listing evidence for the 100-candidate queue (latest)

Branch: feat/listing-scope-evidence, based on local 15dbb18 checkpoint.
Code commit: 0a48728484ec062d218c6c6bb3b20e8e9336e753 (local only).
Final checkpoint commit is in delivery CHECKPOINT.txt. Remote commit/PR/Actions
URLs unavailable; no remote push, PR, merge or Actions execution occurred.

Session checks: target repository metadata freshly returned 404. Main, PRs and
Actions cannot be inspected. Available GitHub tools still lack repository-create
and archive operations; radar-agent remains untouched. Library version 8 status
matched the clean local baseline before the separate feature branch was opened.
No concurrent local change was present. Existing repository/Finnhub-key blockers
are unchanged and do not prevent this concrete offline/live code work.

Completed v0.10.0: explicit validated HTTP Accept media type (JSON default,
text/plain for directories, HTML optional), official Nasdaq Trader HTTPS mirror
fallback, exact-source URL/hash/time preservation and separately recorded attempts.
Fallback stops after the first valid parse. Otherlisted's observed empty legacy
seven-field footer is accepted narrowly; eight-field data rows stay strict.
Fund terms in the issuer portion of a name now remain pending classification,
even when its security suffix says Common Stock.

Added scope.audit_sample and opt-in live/offline replay script. Sample symbol/CIK,
ETF/test flags, primary exchange, vendor-provided aliases, SEC identity, source
freshness and ambiguity are checked separately. Stale exclusions are not promoted
to current scope decisions. Complete listing evidence remains legal-type pending;
no approved scope, financial acceptance or investment score can be emitted.

Actual live requests on 2026-11-02: FTP-host HTTPS files still returned 503.
Official www.nasdaqtrader.com/dynamic/SymDir endpoints initially returned 406
with application/json. The same explicit endpoints succeeded with text/plain.
Nasdaq-listed response: 5,616 rows, sha256 b160a2f2814e5df68d7e414fba70f808f7ad3d20cbbdd167a8a2e38a10044168.
Other-listed response: 7,670 rows, sha256 ee0a872edece98430f3ba5a1ed6e9c683d7a1bb4b2980bdc9743c6995f264398.
Fresh SEC directory retrieval also succeeded; exact original response bytes,
URLs/timestamps and attempt outcomes are preserved in scope-primary-snapshots.json
and compressed fixtures. Both file creation labels are 1030202618:01 (2026-10-30),
with no timezone inferred. They satisfy the explicit four-calendar-day freshness
policy at the 2026-11-02 observation; intraday tradability is not verified.

All 13,286 listing rows were retained and partitioned: 4,886 common-share
candidates, 3,245 excluded instruments, 405 pending classification, 266 pending
identity, 37 test issues and 4,447 out-of-scope-exchange rows. Candidates are not
an approved active common universe. All 100 unique-CIK sample candidates matched
positive listing flags and SEC identity; all 100 remain
listing_evidence_complete_legal_type_pending. Fund legal status and affirmative
share-class corroboration are still required. No financial requests were made
for the additional 97 candidates in this run; no 100-company financial acceptance.

Tests: 209/209 local tests passed on Python 3.12.14 (193 regressions + 16 contracts).
New tests cover Accept/header injection, both source endpoints and stopping,
malformed primary fallback, strict legacy footer variant, full recorded directory
partition without lost rows, 100 exact identities, stale/colliding/mismatched
scope and fund-word quarantine. Offline replay at the recorded observation time
matched the live sample and partition counts. git diff --check passed. Evidence:
scope-tests.json, sample100-scope-audit.json, sample100-scope-replay.json.
No synthetic fixture is counted as live-source evidence. No remote CI run.

Failed attempts retained: primary endpoint 503, initial mirror 406, and first
full otherlisted parse invalid_data because the vendor footer has one fewer
empty column than its data/header. The parser was corrected only for that
observed case, then both live files and recorded-response tests passed. No
missing data was fabricated or replaced by zero. No credential or paid service.

Acceptance: stage 1 remains offline-verified/remote CI pending. Stage 2 remains
partial (Finnhub live unverified and limited financial mappings). Stage 4 is not
accepted: listing prechecks are not full financial validation. Stages 3–8,
scoring/backtest/full universe/final acceptance remain unaccepted.

Next concrete task: add SEC submissions/annual-filing evidence for legal issuer
and registered common-share class, with fund/BDC/REIT distinctions retained and
unknown evidence quarantined. Extract explicit fiscal periods for the remaining
97 candidates from validated source records, then prepare bounded financial
collection. Do not infer legal type from ETF=N or fiscal dates from a calendar.

---

## 2026-11-02 — Resumable multi-company evidence runner (latest)

Branch: feat/resumable-batch, based on local 3de8418 checkpoint.
Code commit: b7a4bfc8acff78df20d3c273ccd0cab0bc07c615 (local only).
Final checkpoint commit is in delivery CHECKPOINT.txt; remote commit/PR/Actions
links unavailable. No GitHub push, PR, merge or Actions run occurred.

Completed: v0.9.0 SQLite per-field evidence checkpoints, exact-query/policy keys,
original-observation TTL, short missing/error retry delay, checksum plus semantic
validation, bounded new work, interruption recovery and owner/expiry write leases.
Added explicit-date research-batch plan/CLI with atomic JSON output and lazy
identity/provider construction. Source failures and identity/configuration
failures stay typed; exception text and credential objects are never persisted.
Out-of-scope work is skipped. Scope-approved status is not implemented; complete
facts never imply an approved security, score, or 100-company acceptance.

Tests: 193/193 passed on Python 3.12.14 (173 regressions + 20 new contracts).
Coverage includes persisted restart, KeyboardInterrupt, expiry based on original
observation, checksum/semantic corruption, concurrent/expired writer rejection,
policy change, source failure isolation, exact plans and zero-work CLI behavior.
A synthetic 100-company/200-field test verifies bookkeeping only. No synthetic
company is counted as real validation. git diff --check passed. Evidence:
docs/evidence/batch-tests.json. Local tests are not remote Actions.

Real execution: the CLI processed 18 exact-period queries for AAPL/MSFT/NVDA.
First bounded run saved 3 fields; resumed run reused those 3 and processed 15.
Results: 16 collected, 2 pending (NVDA exact revenue and capex absent). Yahoo
was called for Assets; valid existing SEC disk snapshots were reused for SEC
financial fields. This run does not claim fresh SEC financial HTTP downloads.
First run made 2 transport GET calls, second 3. The immediate third run reused
all 18 saved outcomes with zero new fields and zero transport GET calls,
including zero identity-directory requests. Two pending outcomes remain pending
and retry after five minutes. All three reports returned exit 2 as expected.
Evidence: batch-three-{bounded,resumed,reused}.json, batch-resume-live.json.
Measurement counts HttpTransport.get invocations, not internal HTTP retry attempts.
No Finnhub financial network call or key was available/used.

Prepared a deterministic 100-unique-CIK audit queue from recorded Nasdaq screener
and exact SEC ticker joins. Explicit common/ordinary name hints select candidates;
they are not legal-class, ETF/fund, test/active or current listing proof. All 100
remain scope-pending, 3 have previously checked exact financial periods, 97 do
not. No 100-company financial test has run. Reproducible script and hashes:
scripts/prepare_sample100.py, docs/evidence/sample100-audit-queue.json.

Session checks: target repository metadata still 404; main, open PRs and Actions
cannot be inspected. No repository-create/archive operations exposed; legacy
radar-agent unchanged. Restored version 7 checkpoint matched local clean baseline
before branching; no local concurrent work was present. Existing remote/key
configuration blockers persist, with no new user action requested.

Acceptance: stage 1 offline-verified, remote CI pending. Stage 2 partial; Finnhub
live validation and broader source coverage remain unaccepted. Three-company
field/resume evidence is not completed financial analysis or a verified active
universe. Stages 3–8, including real 100-company acceptance, remain unaccepted.

Failures/limits: no test failure in this run. Two genuine exact-period/tag gaps
remain; no zero or substitute tag inserted. Batch field cache is current-evidence
only; not a point-in-time backtest. Same-file leases do not coordinate separate
checkpoint files; a hard kill can require lease expiry (15 minutes). Financial
models/scoring and sector-specific acceptance are still absent. Operational
checkpoint DB is preserved separately inside delivery archive; provider raw-cache
files are not included, so expired evidence may require new source requests.

Next concrete task: verify affirmative active listing/common-share/ETF/test
exclusion evidence for the 100-candidate audit queue using primary-source free
directories or filing corroboration; keep unresolved names quarantined. Fetch
and retain explicit fiscal-period evidence for remaining candidates, then run
bounded batches and reconcile missing fields. Do not label stage 4 complete
before earlier financial/source acceptance gates and real validation pass.

---

## 2026-11-02 — Nasdaq balance sheets and ordered research CLI (latest)

Branch: feat/nasdaq-financials, based on local 6b8f357 checkpoint.
Code commit: 757df68e4997e842c51129f76db1d9f7dbf3442d (local only; GitHub URL unavailable).
Final checkpoint commit is recorded in delivery CHECKPOINT.txt.

Completed: Nasdaq Financials API adapter for exact-date Total Assets and Total
Liabilities, with separate official per-stock unit-page validation. Explicit
visible USD Thousands evidence drives Decimal multiplier 1,000; '$' alone is
never a currency/scale proof. Added safe numeric/period/duplicate/missing handling,
unit/API/identity URL/hash provenance and separate timestamps through SQLite.
Extended the narrow original iXBRL instant checker to Liabilities; Assets wrapper
and prior regressions retained. No income/cash-flow start date or EPS scale inferred.

Added lazy four-source wiring and research-fact command. Provider factories,
transports and Finnhub environment configuration are touched only when reached
in Yahoo→SEC→Nasdaq→Finnhub order. An invalid lower-priority factory cannot block
an earlier success. Configuration failures remain distinct from data absence.
The CLI verifies identity before financial collection and emits source attempts,
cutoff and facts; it does not emit investment scores or approval.

Tests: 173/173 passed on Python 3.12.14. New coverage: 14 Nasdaq financial and
five lazy pipeline tests, including source-unit captions, symbol/period/currency,
no guessed zeros, exact original filing replay, cache provenance, lower-source
stopping and bad credential factory isolation. Diff checks passed; no test failed.
Evidence: docs/evidence/nasdaq-financial-tests.json. Remote Actions not run.

Real verification: AAPL, MSFT and NVDA Nasdaq JSON and their official financial
HTML pages fetched successfully. API values lack explicit unit scale; all three
pages explicitly declared USD Thousands. Six instant values (Assets/Liabilities)
matched original SEC filing contexts after scaling, with exact report dates
retained (AAPL 2025-09-27, MSFT 2026-06-30, NVDA 2026-01-25). Unit/header/source
checks and all original response bytes are recorded in
nasdaq-financial-live.json and the six compressed Nasdaq fixtures. These are
three limited company balance-sheet checks, not full financial analyses.

Live end-to-end CLI: AAPL research-fact returned Yahoo period_mismatch → SEC valid
and 359241000000 USD Assets for 2025-09-27. It stopped before Nasdaq/Finnhub
financial client construction; valid SEC disk snapshot reused. Identity metadata
lookup is distinct from a lower-priority financial query. Sanitized output:
docs/evidence/ordered-cli-live.json. No Nasdaq period was calendar-aligned to Yahoo.

GitHub: target metadata fresh check still 404. Main/PR/Actions inaccessible;
no remote push, PR or merge. Creation/archive capabilities remain absent; legacy
project untouched. Worktree clean and Library version 6 matched local status
before branching. Existing repository/key configuration actions are unchanged.
No new paid service, access permission or real-money action requested.

Acceptance: stage 1 offline-verified/remote CI pending. Stage 2 partial: SEC
sample financials, Yahoo Assets and Nasdaq two instant fields have live sample
evidence; Finnhub still lacks existing-key runtime configuration/live response
acceptance. Whole Nasdaq/whole-source financial models not accepted. Active
common universe, 100-company, financial models/scoring, backtest, expansion and
final acceptance remain unaccepted. Later stages are not marked complete.

Limitations: Nasdaq supports only two instant fields. No publication timestamp
in the payload; availability uses completed observation evidence. Distinct
API/unit times remain preserved. Memory TTL only for Nasdaq; persistent cache,
filing-triggered refresh and broader mappings pending. Unit captions cannot be
reused for EPS/ratios or other currencies/pages. SEC/Finnhub/Nasdaq still require
sector-appropriate financial model validation. Directory HTTP 503 and legal
fund/activity corroboration gaps remain; discovery rows are not approved scope.

Next concrete task: build a resumable multi-company evidence/readiness runner
with explicit scope status and per-field missing/unsupported/error results.
Start from the three verified samples, then prepare a 100-company sample with
positive listing/common-share identity evidence and separate unresolved scope
queue. Persist completed observations and avoid re-querying accepted source
facts or lower-priority providers. This is coverage/preflight, not 100-company
acceptance until scope, sources and financial checks are actually met. Retry
transient Trader directory access later, and run Finnhub real validation when
its existing key is configured. Import onto target main through feature PR/CI
when available, without force-pushing unrelated local history.

## 2026-11-02 — Finnhub reported-financial contracts (latest)

Branch: feat/finnhub-reported, based on local cb06e2e checkpoint.
Code commit: 5a4ef5b1440cf85c4f63ad1aa8b6a9b022837238 (local only; no GitHub URL).
Final documentation checkpoint is recorded in delivery CHECKPOINT.txt.

Completed: existing-key configuration via FINNHUB_API_KEY/FINNHUB_TOKEN,
credential-hidden repr/conflict validation, Finnhub-only token header transport,
no credential-bearing source URLs, echoed-token body rejection and typed
access/quota errors. Added reported-financial adapter contracts for six exact
GAAP concepts, CIK/period/unit/frequency/filing validation, explicit unsupported
unitless/segmented/scaled records, conservative availability and memory caching.
Added finnhub-fact CLI with no-network not_configured response when key absent.
Prepared a manual GitHub Finnhub single-field workflow using the target repo
FINNHUB_API_KEY secret; inputs are quoted via environment variables and output
is sanitized. YAML was parsed and checked locally; workflow has NOT run remotely.
The strict per-concept array parser is a contract prototype, not a verified
current API report shape: the vendor report schema is loosely typed.

Tests: 154/154 passed on Python 3.12.14, including 21 new synthetic Finnhub/header/
configuration/CLI/priority/cache/provenance/period tests and all prior source
replays. Diff checks passed. No unit test failed. Diagnostics now exit nonzero when
no valid fact is collected, so access errors cannot yield a green smoke job.
Final runtime code commit: 43b288e4eac1f0811e50e3c59d0370c39445f98a. Test evidence:
docs/evidence/finnhub-tests.json. Production runtime still has no added dependency.
Official SDK/OpenAPI references were reviewed; a temporary dev script inspected
the schema, without copying the SDK into the project.

Real preflight: neither supported environment variable is configured in this
execution environment. Finnhub network calls=0, transport_created=false,
status=not_configured, confirmed_absent=false. Evidence:
docs/evidence/finnhub-preflight.json. Do not describe this as a failed network
request, an absent financial metric, an account without a key, or live acceptance.
The user's prior key may exist elsewhere; no legacy secret was read, copied,
printed or requested in plaintext. An existing key must be made available to
this new project's runner before real Finnhub validation can happen. No paid
subscription or new permission was requested or enabled.

Other live checks: both Nasdaq Trader files retried once with bounded HTTP and
still returned HTTP 503. Safe URL/status/reason evidence is in
nasdaq-directory-retry.json. Treat as transient and keep the previously separate
6,954-row discovery snapshot; do not promote it to active-common-share acceptance.

GitHub: target metadata fresh check remains 404; main/open PR/Actions inaccessible.
No remote push, PR or merge. Creation/archive capabilities remain unavailable;
legacy project untouched. Worktree was clean; Library version 5 matched local
status before branching. Existing repository blocker has not changed.

Acceptance: stage 1 offline-verified/remote CI pending. Stage 2 remains partial:
SEC small-sample financials, Yahoo Assets, Nasdaq discovery and Finnhub synthetic
contracts. Finnhub live/account response and Nasdaq financial connection are
unaccepted. Active common universe, 100-company, financial models/scoring,
backtest, expansion and final acceptance (stages 3–8) remain unaccepted. No
investment score, recommendation, valuation or trade produced.

Limitations: Finnhub's live statement row shape, entitlement and units cannot
be established without the existing key in this runner. Contract parser rejects
unsupported legacy maps instead of guessing currency/scale. Memory TTL only;
Finnhub disk cache and filing refresh pending. Naive acceptedDate is not guessed
as UTC; conservative filing-date availability remains. Token header support is
confirmed in the official SDK, but this run performed no authenticated call.

Next concrete task: implement a bounded Nasdaq financial-statement fetcher and
inspect real period/currency/scale/issuer metadata. Add field mapping only where
that evidence is sufficient; preserve unsupported/unconfigured states elsewhere.
Retry transient Trader files on a later run and corroborate active/common/fund
scope before the 100-company sample. When an existing Finnhub key is accessible,
run a small real reported-financial reconciliation and adjust the strict parser
from observed evidence, without upgrading services. Do not ask for a new key or
new permission when an existing runner configuration suffices. Import onto target
main via a feature PR/CI when available, never force-push unrelated root history.

## 2026-11-01 — Nasdaq discovery and universe contracts (latest)

Branch: feat/nasdaq-universe, based on local 28d98db checkpoint.
Code commit: 6ff7771419446159ab80a46466f23709f04f2c45 (local only, no GitHub URL).
Delivery CHECKPOINT.txt records the final documentation checkpoint.

Completed: strict Nasdaq Trader listed/otherlisted directory parsers, source
footer/date/provenance retention, documented exchange and flag handling,
conservative instrument-name rules, exact SEC identity/exchange corroboration,
cross-directory collision protection and exhaustive row partitioning. Unknown
types/flags/identity stay pending. No final active Security is fabricated from
membership/name evidence; candidates still require independent scope checks.
Added bounded, pagination-checked Nasdaq screener discovery adapter and CLI.
Added safe enumerated HTTP/DNS/TLS/network/timeout diagnostics with HTTP codes.

Tests: 133/133 passing on Python 3.12.14, including the original financial/live
fixture regressions, 16 Trader parser/universe contract tests, discovery count/
pagination/duplicates/schema bounds, real 6,954-row replay, padded symbol
collision checks, error sanitization and CLI configuration guard. Diff checks
passed. Evidence: docs/evidence/nasdaq-tests.json. No remote CI result exists.

Real data: Nasdaq public screener returned 6,954 records; complete count and
unique-symbol checks passed. 6,560 symbols matched SEC exactly; 394 remain
unmatched (not silently discarded). Raw ETX/ECC symbols had ASCII padding;
trimmed only the surrounding padding while retaining raw_symbol and original
bytes. Response source label was 'Last price as of Oct 29, 2026'; this is not
verified listing freshness. Snapshot URL/time/SHA: nasdaq-discovery-live.json;
compressed full response: tests/fixtures/nasdaq-discovery-diagnostic.json.gz.

Real blockers/failures: both Nasdaq Trader files failed on the web directory
and documented file-host HTTPS paths. A diagnostic file-host retry, after
improved error reporting, identified HTTP 503. Nasdaq screener API worked as a
separate weaker fallback; no IP/header/auth circumvention was attempted.
First full screener parse rejected two padded symbols, and one replay test
failed. Diagnosed the saved raw response, implemented reversible ASCII trim
with normalization-collision rejection, then the complete 133-test suite passed.
No field value, period date or share-class punctuation was guessed.

GitHub: target metadata still 404. No main/PR/Actions inspection, remote push,
PR or merge possible. Creation/archive tools remain unavailable and legacy repo
unchanged. Local worktree was clean; Library version 4 matched local status
before branching. Existing repository blocker is unchanged; no repeated request.

Acceptance: stage 1 offline-verified, remote CI pending. Stage 2 remains partial:
SEC small sample + Yahoo Assets + Nasdaq discovery; Nasdaq financial extraction
and Finnhub are not accepted. Trader file access remains unverified. The public
screener lacks explicit exchange, ETF/test flag, activity and security-type
metadata, so none of its 6,954 rows is automatically a verified active-common
share. The complete active US universe is NOT accepted. 100-company and stages
3–8 remain incomplete. No score, valuation, ranking or trade was produced.

Limitations: Trader name rules create candidates, not legal fund-type proof;
funds may use common-share descriptions. No complete halt/delisting or historical
universe dataset. Screener labels/total counts do not solve those gaps. Its
symbol padding normalization preserves raw evidence. Nasdaq financial data is
still absent from the field resolver, explicitly unconfigured rather than tried.

Next concrete task: add Finnhub provider contracts and explicit existing-key
configuration with sanitized access/quota handling; probe only if already
configured, without buying services or granting new access. Also implement a
small Nasdaq financial-statement adapter only if period/unit/identity evidence
is sufficient. Retry transient Trader files on a later run; do not substitute
screener discovery for active-common-share acceptance. Reconcile pending scope
and SEC identities before building the 100-company research sample. When target
repo exists, import onto main via feature PR and CI, without force-pushing the
unrelated local root history.

## 2026-11-01 — Yahoo Assets and ordered live fallback (latest)

Branch: feat/yahoo-sec-fallback, based on local 4c7e9fc checkpoint.
Code commit: 522f003ee07d53a2f014bef1d122f123e471bb46 (local only; no GitHub URL).
Final checkpoint commit is recorded in delivery CHECKPOINT.txt.

Completed: Yahoo annualTotalAssets adapter with exact date/currency/symbol and
fresh SEC symbol/CIK binding. Facts retain vendor field, Yahoo response checksum,
identity proof URL/time/hash and conservative first-observed availability.
Yahoo duration and other financial concepts explicitly report unsupported_field.
Added period_mismatch status for same-month wrong-day observations. Successful
Yahoo snapshots are reused in memory; identity proof survives SQLite roundtrip.

Fixed live collection chronology: the earlier fixed-cutoff API rejected newly
fetched responses when retrieval followed request creation. Added cutoff-free
FactQuery and resolve_current: prepare only the next source, set cutoff after
its response, validate, and stop before preparing later sources on success.
The fixed historical FactRequest path never advances its cutoff. SEC adapter
and SEC diagnostic CLI use the live preparation boundary without eager lower
priority source fetches. Existing historical protections remain tested.

Tests: 106/106 passed on Python 3.12.14. Tests cover first-valid stopping before
SEC prepare/fetch, cutoff timing, unchanged fixed historical cutoff, provider
failures, period mismatch, identity evidence, currency/numerics, unsupported
fields, cache reuse and full three-case recorded Yahoo→SEC integration replay.
Original SEC/filing regression evidence is retained. Diff checks passed.
Evidence: docs/evidence/yahoo-tests.json and docs/evidence/yahoo-sec-live.json.

Real validation: three Yahoo requests succeeded. AAPL Yahoo date 2025-09-30 did
not match requested SEC period 2025-09-27, and NVDA similarly had a different day;
both fell back to SEC. MSFT matched exact date 2026-06-30 and stopped at Yahoo.
All three numeric Assets values matched earlier original-filing checks. SEC
fallback used existing valid disk snapshots, with zero additional SEC HTTP
requests. This validates three Assets cases, not a complete company analysis
or every Yahoo financial field. Original response bytes are in the Yahoo *.gz
fixtures with date/URL/hash in the evidence report.

Failed attempts/corrections: raw GitHub-source browsing returned DisabledError;
the upstream GitHub page worked. The initial live-report comparison used string
representations, falsely flagging MSFT scientific versus integer formatting as
a mismatch; corrected to Decimal equality and covered by real-response replay.
No source values were changed. AAPL/NVDA period differences were deliberately
not corrected, calendar-aligned or silently accepted. No unit test failed.

GitHub: target repo fresh metadata check still 404; main/PR/Actions inaccessible.
No remote push, PR or merge. Creation/archive tools remain absent; legacy repo
untouched. Local worktree was clean and Library version 3 matched status before
branching. Existing repository blocker is unchanged, not a new user request.

Acceptance: stage 1 offline-verified/remote CI pending. Stage 2 partial: SEC
small-sample financial extraction plus Yahoo Assets with ordered fallback;
Nasdaq/Finnhub and broader Yahoo mappings pending. 100-company and stages 3–8
remain unaccepted. No score, ranking or investment recommendation produced.

Limitations: Yahoo endpoint is undocumented; no credential/cookie/proxy bypass
was used. Only assets supported; no inferred duration start, accounting alias
or calendar date adjustment. Yahoo publication time is unknown, so retrieval
is used as first-observed availability. Yahoo cache is memory-only; SEC retains
its six-hour disk cache. Identity requires a fresh SEC snapshot (one day).
No complete live universe or historical vintage dataset has been accepted.

Next concrete task: implement Nasdaq source integration and verify active
common-share universe metadata without admitting ETFs/funds/warrants/preferred
or unknown instrument types. Test source error handling and record real endpoint
results. Then extend exact Yahoo mappings only with reliable period/definition
evidence; keep unsupported fields explicit and verify Nasdaq/Finnhub before
calling stage 2 complete. Import checkpoint onto target main via feature PR
when repository becomes available, without force-pushing unrelated history.

## 2026-11-01 — SEC companyfacts and source-filing reconciliation (latest)

Branch: feat/sec-companyfacts, based on local 6aae3302 checkpoint.
Code commit: 8b72d157b7fcc1678a42d07f2ce3c0c0dde0384c (local only; GitHub URL unavailable).
Final checkpoint commit is recorded in the delivery archive CHECKPOINT.txt.

Completed: six exact US-GAAP financial mappings, instant/duration and currency
validation, filing accession/date/raw SHA provenance, precise Decimal JSON,
conservative availability, current-vintage historical rejection, and atomic
six-hour company snapshot disk/memory cache with integrity verification.
Existing field resolver preserves Yahoo priority and reports it unconfigured
in SEC-only diagnostics. Added sec-fact CLI and SQLite filing-metadata roundtrip.
Added narrow original-iXBRL Assets verifier and compressed recorded fixtures.

Tests: 88/88 passed on Python 3.12.14, including original regression suite,
period/unit/identity/future/missing/unsupported handling, cache restart/expiry/
corruption, priority tests, replay of three full companyfacts snapshots and
three original filing documents. Diff check passed. Cached live-data CLI check
passed without another SEC download. Evidence: docs/evidence/companyfacts-tests.json
and docs/evidence/sec-fact-cli.json. No failed test attempt in this session.

Live data: AAPL, MSFT and NVDA companyfacts retrieved successfully. Exact selected
periods yielded 16/18 requested monetary fields; two NVDA annual concepts
(revenue excluding assessed tax and the selected property/plant/equipment cash
payment tag) had no exact observation. No substitute, zero or fabricated value
was introduced. Assets for all three companies matched their original SEC
iXBRL filing contexts. Some contexts are comparative balances in later 10-Qs;
these are identified by the actual accession, not mislabeled as original 10-Ks.
Other extracted fields have NOT been independently reconciled to original filings.
Timestamps/URLs/hashes/values are in docs/evidence/companyfacts-live.json;
original response/document bytes are in tests/fixtures/*.gz. There are three
limited real-data checks, not three fully accepted company investment analyses.

GitHub: new repository metadata again returned 404. Main/PR/Actions unavailable;
no remote branch, push, PR or merge. Creation/archive capabilities remain absent.
Legacy project untouched. Local worktree was clean before branching and current
Library version 2 matched its status file, so no divergent checkpoint was used.
Previously reported repository action remains unchanged; no repeated request.

Acceptance: stage 1 offline-tested/remote CI pending. Stage 2 partially
implemented: SEC directory plus financial extraction verified on a small sample;
Yahoo/Nasdaq/Finnhub financial adapters are still pending. All four sources are
not accepted. Stages 3–8, 100-company acceptance and final system completion
remain unaccepted. No score, valuation or investment recommendation produced.

Limitations and unsuccessful lookups: two exact NVDA annual fields unresolved;
only three Assets values independently checked. No general XBRL engine, no
IFRS/financial-sector model, no tag-equivalence guessing, no exact intraday SEC
acceptance timestamp, no historical vintage dataset. Filing date is conservatively
mapped to the next day at 05:00 UTC. Cache refresh uses TTL or explicit refresh;
filing-triggered invalidation and conditional GET remain pending. These limits
must not be interpreted as financial distress or exclusion from the universe.

Next concrete task: implement and test the first-priority Yahoo financial
adapter with exact issuer/period/definition provenance and explicit access/quota
failure classification; verify on a small real sample, then integrate ordered
Yahoo→SEC fallback. Keep unconfigured sources explicit. Evaluate unresolved
NVDA concepts using documented semantic mappings, without silently substituting
incompatible tags. Retain SEC asset reconciliation as regression evidence.
When the repo is available, import onto its main in a feature branch, run CI,
open PR and merge verified work without force-pushing unrelated local history.

## 2026-11-01 — SEC identity and HTTP transport (latest)

Branch: feat/sec-identity-transport, based on local 8bbd132 checkpoint.
Code commit: 07155884e4c3d81c604293dcd13c5f3faad9cbea (local, no GitHub commit URL available).
Documentation checkpoint hash is recorded in archive CHECKPOINT.txt.

Completed: HTTPS source-host restrictions, redirect refusal, identifying
User-Agent, per-socket timeout and between-read deadline checks, 2 requests/sec
in-process shared limiter, bounded retries/response sizes, Retry-After handling,
access/quota/timeout/API failure separation and sanitized errors. Added strict
SEC directory schema/identity parser, exact class-symbol matching, checksums,
CLI lookup, and real-response replay fixture.

Tests: 60/60 passing, Python 3.12.14. Evidence:
docs/evidence/sec-transport-tests.json; original 37 regression tests retained.
Unit/synthetic integration + full recorded-response replay passed. Diff check
passed. Remote CI has not run. First transport test run 58/58; CLI and
recorded-response tests increased the final total to 60/60. No failing tests.

Real validation: direct Python HTTPS succeeded at 2026-11-01T17:56:42Z.
SEC returned 522,995 bytes and 10,430 directory entries. AAPL, MSFT, NVDA,
BRK-B CIK identities checked against expected identifiers. Raw response checksum
and results: docs/evidence/sec-directory-live.json. Original response:
tests/fixtures/sec-directory-recorded.json. The SEC's own access policy and
schema were checked on its official site before implementation. No financial
metric was collected. These 10,430 entries are NOT an active-common-share count.
Security type and active status are not inferred from the SEC directory.

GitHub: fresh new-repository check still returned 404. Creation/archive tools
remain unavailable; main, PRs and Actions cannot be inspected for this target.
No remote push, PR or merge. Previously reported repository blocker is unchanged;
no repeat user action request. Legacy repository untouched. The workspace
was clean before the new branch; no other local changes were detected.

Stage 1 remains offline-verified with remote CI pending. Stage 2 has one
live-tested identity adapter, not four accepted financial connections.
Financial-model, 100-company, score, backtest, expansion and final acceptance
stages remain incomplete. Financial companies validated: 0.

Limitations: socket-operation timeout is not a hard wall-clock process kill;
read deadline checked between buffered reads. Share the same limiter across
concurrent SEC clients; independent processes need central orchestration.
The directory is not guaranteed complete/accurate by SEC and needs independent
listing/type corroboration. Current snapshot is dated, not a historical universe.

Next concrete task: implement SEC companyfacts ingestion and canonical
accounting-tag/period/unit mappings with fixture tests. Connect the existing
first-valid resolver without skipping Yahoo priority; add a controlled live
metric reconciliation for a few known CIKs, clearly short of the 100-company
acceptance gate. Also integrate filing-aware caching to prevent repeated full
downloads. When target repo becomes available, import onto its main in a feature
branch, run CI and create a normal PR without force-pushing unrelated history.

## 2026-11-01 — offline foundation checkpoint

Branch: feat/auditable-foundation. Repository target: fatalvayn-dot/us-equity-research.

### Completed

Inspected the provided starter ZIP and retained its seven regression tests.
Added packaging metadata, immutable identity/fact/request models, exact
accounting-period/currency/identity matching, publication/retrieval cutoffs,
ordered provider resolution with typed failures, SQLite accepted-fact cache,
score weights/readiness policy, CLI status, architecture/scope/resume docs,
and a GitHub Actions test matrix. Tests: 37/37 passed on Python 3.12.14,
including synthetic resolver-to-cache integration. CLI status and diff check passed.
Evidence: docs/evidence/foundation-tests.json. Fixture tests are not live evidence.

### GitHub and commits

GitHub connection succeeded. get_repo returned 404 for the new repository;
owner repository listing returned only radar-agent. The connected tools expose
neither repository creation nor archive-setting operations; gh CLI is absent.
No new repository main, PR or Actions results could be inspected. No remote
branch, PR, commit push or merge occurred. Foundation commit: 0cbdc14db5862a9dd721f2dd598ed1187301f535 (local only).
Final checkpoint commit is recorded in CHECKPOINT.txt in the delivery archive. The archive includes a Git bundle.

radar-agent remains private, unarchived and unchanged by this session. Admin
permission was visible, but no available archive operation was exposed.

### Acceptance gates

1. Architecture/models/test infrastructure: offline tests passed; remote CI pending.
2. Four live connections: not implemented/accepted.
3. Financial models: not implemented/accepted.
4. 100-company real test: 0 companies; not started.
5. Scoring/ranking: weights only, no scores.
6. Historical testing: protective cutoff only, no backtest.
7. 500/1,000/full universe: not started.
8. Final regression/performance/live acceptance: not accepted.

### Failed attempts and limitations

- New repository metadata: 404; cannot distinguish nonexistent from inaccessible
  with absolute certainty. Accessible repository inventory contains only old repo.
- Initial Library attribute application omitted workspace_path; corrected with
  complete required fields and succeeded. Starter content was preserved.
- One documentation patch was rejected before writing due to duplicate README
  operations; reapplied as valid separate operations.
- No real network financial response was requested. No live source was counted
  as connected or tested. No numerical acceptance threshold is validated yet.
- Cache is standalone; incremental provider integration and revision tracking pending.
- Original core API is deprecated and must not feed the new live pipeline.

### Next concrete task

Create the private target repository with an initial README using an available
repository-creation operation, then import this checkpoint into a feature branch.
Run CI, open/review PR and merge only after verification. If creation remains
unavailable, ask only for repository creation; preserve completed local work.
Next code task: implement a bounded, rate-limited HTTP transport and SEC issuer
mapping adapter with recorded-response contract tests, then run real identity
checks. Full-source connection acceptance follows only with real evidence.

### Scheduled continuation

The previous development automation was paused successfully. A separate enabled
hourly US Equity development automation was created successfully, using timezone
Africa/Mogadishu. New task: 6ae7781d799c8191a98d1442d0d6ec58. Its prompt
references persistent checkpoint libfile_c2f0ce03b15481918f6006f57cf4e7aa.
No future run has been observed yet. Each trigger is a separate session, not
continuous execution. Suppress identical blocker notifications. Repository
creation remains the only requested user action; offline development can continue.
