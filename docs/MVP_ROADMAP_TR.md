# İlk kullanılabilir sürüm yol haritası — 7 Kasım 2026

Hedef pencere: 10–12 Kasım 2026. Bu bir mühendislik tahminidir, teslim garantisi
veya otomasyonun çalıştığı iddiası değildir. Kaynak erişiminin sürmesi, son durum
arşivinin alınması ve geliştirme oturumlarının yürütülebilmesi koşuluna bağlıdır.
İlk uçtan uca kabul denemesi hedefi 9 Kasım; o denemede kalan eksiklerle tarih
yeniden hesaplanır. 4 Kasım hedefi karşılanmadı. Eksik kabulü tarihe uydurmayız.

| Sıra | İş | Tamamlanma kanıtı | Hedef |
|---|---|---|---|
| 1 | Aynı yıllık belgenin altı saat sonra rapordan düşmesini önle | Eski belge + sıfır indirme bütçesiyle dönem korunur; SHA, CIK, accession, tarih kontrolleri geçer | 7 Kasım |
| 2 | Run 42309920856 arşivini denetle | ZIP SHA/CRC, SQLite, ham kaynaklar; #13 kaynak altkümesi; 39 alanın durum karşılaştırması | 7–8 Kasım |
| 3 | Güncel 100 adayın aktif adi hisse niteliğini doğrula | Sembol/CIK/sınıf/borsa kanıtı; uygunsuz ve belirsiz adaylar açıkça ayrılır | 8–9 Kasım |
| 4 | Güncel finansal alanları ve karşılaştırma dönemlerini tamamla | Dönem, birim, para birimi ve tanım tutarlı; eksikler sıfır değildir | 8–10 Kasım |
| 5 | Fiyat, sektör modeli, değerleme ve risk girdilerini bağla | Her hesaplamadan kaynağa iz; desteklenmeyen sektörde puan yok | 9–11 Kasım |
| 6 | Türkçe şirket raporu ve sıralamayı uçtan uca doğrula | Yeterli kanıtlı şirketlerde açıklanabilir skor; yetersizlerde gerekçe; tekrarlanabilir CLI ve CI | 10–12 Kasım |

## Kabul sınırı

En az 100 gerçek ABD adi hisse adayını aynı çalışma hattından geçir.
Aktif adi hisse doğrulaması ile yalnız üstveri/belge bulunmasını ayrı say.
Kapsam dışı adayları sessizce kabul etme; 100 uygun aday hedefi için gerektiğinde
kanıtlı yeni adayları ayrı kaydet. Tam girdili şirketleri sektörüne uygun modelle
puanla; tüm 100 şirkete zorla skor üretme. En az bir gerçek şirketin bütün
kabul zincirini geçmesi ve tüm adayların durumlarının açıklanması gerekir.
Bu koşul tek başına yeterli değildir: PROJECT_BRIEF kapsamı ve bütün diğer
kabul kriterleri de sağlanmalı. Canlı kaynak ve fixture sonuçlarını ayır.
Eksiksiz rapor, yeniden çalıştırma komutu, kaynak arşivi ve başarılı testleri sun.
Backtest, gölge portföy, gerçek işlemler ve evren genişletme bu kabulün dışında.

## Açık bağımlılıklar

Son arşivlere kimlik doğrulamalı indirme erişimi bu oturumda sağlanmadı;
GitHub bağlı araçları metadata okuyabiliyor, ikili dosya indiremiyor.
Work zamanlayıcısının bağımsız geliştirme başarısı doğrulanmadı. Bu nedenle
gelecekteki kesintisiz çalışma varsayımıyla kesin tarih verilmez.
Toplayıcının denetlenmiş dilim sınırı arşiv kontrolü tamamlanmadan yükseltilmez.
