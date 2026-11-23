# Kalıcı eksik veri altyapısı — aşamalı teslim (23 Kasım 2026)

## Hedef
ABD, BIST ve Avrupa'da binlerce şirket için tekrarlanan manuel aramayı kaldırmak. Her taramanın eksik alanları şirket kimliği + dönem + muhasebe tanımı temelinde tekilleştirip bütçeli, tekrarlanabilir araştırma görevlerine dönüştürmek. Eksik veriye sıfır atamak, hesap kapsamı farklı GAAP etiketini otomatik eşleştirmek, katılım veya yatırım onayı vermek yasak.

## Tamamlanan ilk ortak bileşen
`scripts/plan_missing_financial_data.py` beşli pilot kodundan bağımsızdır. `companies[].missing_required_facts[]` biçimindeki kaynak eksikliği kayıtlarını okuyabilir; her görevde piyasa, sembol, özgün ihraççı kimliği, eksik alan, dönem, gerekli muhasebe tanımı, sağlayıcı denemeleri ve kaynak araştırma yönü korunur. SHA256 tabanlı kararlı görev anahtarı, kayıt tekilleştirme, aynı şirket kimliği çelişki kontrolü, önceki doğrulanmış kanıt anahtarıyla tekrar işten kaçınma, 500 varsayılan / 10.000 azami görev sayısı, maliyetli veya başarısız sonsuz yeniden denemeyi engelleyen `provider_cooldown` sınıflaması ve okunabilir Türkçe rapor vardır.

Çalıştırma: `PYTHONPATH=.:src python scripts/plan_missing_financial_data.py --gaps <kaynak-eksik-raporu.json> --limit 500 --out <plan.json> --markdown <plan.md>`.

Aynı tür yeni veri kaynağı geldiğinde mevcut modelin Yahoo > SEC > Nasdaq > Finnhub ilk-geçerli önceliği **değiştirilemez**. Raporun `primary_source` alanı, eksik alan araştırmasının ilk incelenecek resmî belge kaynağıdır; üretim finansal değer seçimi sırası değildir.

## Henüz tamamlanmayanlar
1. Yalnız ABD beşli canlı Actions veri raporu yeni ortak planlayıcıya bağlandı. 100 ve 10.000 şirketin **canlı** kabulü yapılmadı.
2. SEC CompanyFacts + özgün XBRL, KAP ve ESEF indirme/yenileme worker'ları, rate-limit ve kalıcı checkpoint ile ayrı test/PR gerektirir. Bu sürüm **ağ isteği yapmaz**.
3. Sınıflandırılmış görevin `verified_exact` durumuna geçmesi için CIK/ISIN, accession, taksonomi, birim, dönem ve özgün kaynak hash denetleyen ayrı validator gerekir. Önbellek girdisi, puanlama girdisine dönüşmez.
4. Muhasebe kapsamı farklı olan NVDA/AMZN, multi-class GOOGL gibi durumlarda sürümlü sektör/GAAP metodolojisi ve regresyon kanıtı sağlanmadan skor üretilmez.
5. Sonraki genel geliştirme: Aşama 2, kaynaklardan otomatik `fact` kanıt toplama ve retry bütçesi olan worker; sonra 100 şirket testinde başarı ve veri kapsamı ölçümü.

Kabul koşulu: tekil şirket/alan/dönem kaynak zinciri, rate-limit ve cache ölçümü, gerçek SEC/KAP/ESEF kanıtı, 100 şirket geçmiş/gerçek testleri, hash doğrulama, dürüst eksik durum, maliyet bütçesi ve korunan yatırım uygunluğu kuralları. Bu belge prototip planlayıcısını tüm sistem tamamlandı diye göstermemelidir.
