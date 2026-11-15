# Adaptif Yatırım Uzmanı – iş bölümü ve veri devir protokolü

Tarih: 2026-11-15. Ana uygulama katmanı GitHub Actions + GPT Work araştırma çıktısı + Adaptif Yatırım Uzmanı karar değerlendirmesidir.

## Sorumluluk ve gerçek sınırlar

- **GitHub Actions**: Veri gözlemi, zaman damgası, eksik veri bayrakları, açık/hatasız çalışma kanıtı ve `analyst-handoff.json` artifact'i. Fiyat değişimi = emir sinyali değildir.
- **GPT Work**: Bir ana araştırma/geliştirme sorusu, kaynaklı bulgular, veri iyileştirmesi, deney veya test; ayrı PR, CI sonucuyla. Sonuç özetini Türkçe üretir. Bu iş planlı Work oturumu kurulmadıkça kendiliğinden gerçekleşmez.
- **Adaptif Yatırım Uzmanı**: Son başarılı `Adaptif yatırım uzmanı veri özeti` Actions koşusunun `adaptive-analyst-daily-evidence` artifact'ini ve Work teslimatını **ayrı ayrı** okur; piyasa olaylarının makro iletimini, şirket değerlemesi, katılım ve portföy risklerini değerlendirir. AL/TUT/AZALT/SAT/BEKLE kararını tarihlendirir. Gerçek emir kullanıcı onayı dışında gönderilmez.
- **Gerçek Midas portföyü**: Yalnız özel kullanıcı kaynağından okunur. Kamuya açık GitHub'a adet, alış maliyeti, nakit bakiyesi, hesap kimliği eklenmez.
- **Asistanın bağımsız sanal portföyü**: `data/analyst/independent_paper_portfolio_eur10k.json`. Bu dosya yalnız asistanın kamuya açık **kurgusal** 10.000 EUR deneyidir. Hiçbir kullanıcının gerçek verisini içermez.

## Günlük devir kontrolü

1. GitHub Actions'ta son başarılı `adaptive-analyst-daily.yml` koşusunu bul. Başarılı CI eski/tarihsiz veri demek değildir.
2. `analyst-handoff.json` ve zaman damgalarını oku; veri 4 günden eskiyse, kaynak erişilemediyse veya piyasalar kapalıysa açıkça belirt. `research-packet.json` ile olguların URL'lerini karşılaştır.
3. Work'ün *gerçekten tamamladığı* son PR/raporu ayrıca kontrol et; Actions veri paketi Work teslimini doğrulamaz.
4. Jeopolitik veya makro gelişmeler için kaynak tarihi, beklenen iletim, fiyatın önceden tepkisi, alternatif senaryo ve olası karşıt işaretleri yaz.
5. Katılım ve finansal oranları **tek tanımlı bir standarda** göre kontrol et. Sınırda olanı `WATCH_NO_BUY` yap; standartlar arası geçiş tamponunu keyfî kullanma. Uygun olmayanı reddet; bilinmeyeni uygun sayma.
6. Gerçek ve sanal portföy için ayrı karar ve performans kaydı oluştur. İşlem öncesi gerçekçi fiyat, kur, komisyon, lot, risk ve yatırım tezi gerekli.
7. Değişmeyen araştırmayı yeniden yapma. Kararın karşıt kanıtını ve ne zaman değişeceğini yaz.
8. Çıktıyı Türkçe ve kısa ver. Otomatik GitHub job'larının, ChatGPT'deki bir Work oturumu veya günlük insan/AI değerlendirmesi yerine geçtiğini iddia etme.

## Üç aylık bağımsız sanal test

- Başlangıç: **2026-11-15**, kapanış incelemesi: **2027-02-15**.
- Başlangıç nakdi: **10.000 EUR**. Bu tarih itibarıyla hiçbir sanal hisse gerçekleşmedi.
- Üç aylık süre, teknik işleyiş ve karar disiplinini gözlemek için uygundur; **istatistiksel olarak sürdürülebilir piyasa üstü getiri kanıtı değildir**.
- 2026-11-15 tarihli üçüncü ve son ilk hedef planı başlangıç stratejisi olarak kilitlenir. Sonraki tüm değişimler tarihli sanal alım, satış, komisyon, kur ve kâr/zarar kaydıyla yapılır.
- Görüş değişikliği geçmiş portföyü silmez; iptal edilmiş plan ve önceki sürümler tarihçede kalır.
- Karşılaştırma: EUR bazında başlangıç sermayesi, SPUS toplam getirisi, seçilmiş karışık gösterge, nakit etkisi ve toplam giderler.

## Kota yaklaşımı

Kullanıcının toplam aylık ChatGPT kullanım kapasitesinin en fazla %50'si amaçlanır; gerçek kullanım ölçümü yoksa bunu sağlamış gibi raporlanmaz. Planlı Work oturumu en fazla günlük birdir; karmaşık toplu analiz GitHub Actions'a aktarılır. Günlük insan/AI rapor otomasyonu geçmişte durduruldu. Kullanıcı yeni plan oluşturana kadar otomatik ChatGPT görevini kendi kendine yeniden açma.
