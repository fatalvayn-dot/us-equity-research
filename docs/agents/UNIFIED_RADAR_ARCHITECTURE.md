# Birleşik radar → adaptif uzman: tek şirketlik kanıtlı pilot

Durum: Uçtan uca **araştırma iskeleti**. Tam finansal analiz, katılım onayı, haber tahmini ve yatırım kararı değildir.

## Tek otorite / tekrarların azaltılması

1. Fiyat adaptörleri: mevcut `scripts/market_radar_pilot.py`; yfinance → Yahoo Chart → (tanımlı ABD sembollerinde) Stooq.
2. Teknik referans sinyali: aynı dosyadaki `signal()`; yeni ve rakip momentum hesabı yazılmadı.
3. Denetimli tahmin kaydı mantığı: `scripts/market_radar_agents.py:process()`; burada kalıcı tahmin defteri değiştirilmez.
4. LLM görev devri: mevcut `scripts/llm_team.py:orchestrate()`; 5 çağrı, `openrouter/free`, isteğe bağlı, yalnız veri yorumu.
5. Finansal/katılım puanları: eksik kaynaklı olduklarından `blocked/unknown`; başka modülden kanıt olmadan puan ya da AL emri üretilmez.

## Tek şirket yürüyüşü

`PYTHONPATH=.:src python -m unittest -v tests.test_unified_single_issuer`

Canlı fiyat denemesi (ücretsiz, salt okunur; kaynak erişilebilirliği garanti değil):

`PYTHONPATH=.:src python scripts/unified_single_issuer.py --symbol AAPL --out unified-single-issuer.json`

Çalıştırmanın raporu `source/as_of/forecast/gates/summary/llm` içerir. Sahte fiyatla çalıştırma yalnız testtir. Gerçek LLM kullanımı ancak `RADAR_FREE_LLM_ENABLED=true` ve gizli `OPENROUTER_API_KEY` ile `--llm` isteğinde olur; ücretsiz kotanın dolması başarısızlık demektir, ücretli yedekleme yok.

## Kapsam ve deprecate kararı

- `market_radar_pilot.py`, `market_radar_agents.py` ve `llm_team.py` korunur; yeni orkestratör bunları çağırır, aynı veriyi ikinci kez çekmez.
- Eski 100-şirket tarama, SEC kaynak işleri ve BIST/Avrupa prototipleri **silinmez**; kanıt ve geriye dönük uyumluluk sağlanmadan birleştirilmez.
- `market-radar-pilot.yml` ile `llm-team.yml` henüz otomatik kaldırılmaz. Birleştirme öncesi Actions/artefact kayıtları üzerinden çağrı ve veri kaybı denetimi yapılmalıdır.
- Haber, makro, mali tablo, katılım ve portföy modülleri için tek tip tarihli kaynak kanıtı olmadan yeni birleştirme kabul edilmez.
- Varsayılan hiçbir aşama işlem yapmaz, kullanıcı portföyünü dış LLM'e veya public repoya göndermez.

## Kapsamı artırma için geçitler

1. AAPL gerçek fiyat ve gerçek SEC finansal/valuation kanıtı, katılım belgesi ve veri tarihleri eklenir.
2. Tek şirket başarılı çalışınca aynı kanıtlı akış 5 ABD şirketi ile test edilir; sonra BIST XKTUM ve Avrupa kanıt kapıları eklenir.
3. Tarihli geçmiş tahminler en az 5 işlem günü sonra değerlendirilir; walk-forward ve kıyas sonuçları olmadan 'adaptif öğreniyor' denmez.

## Katılım araştırma entegrasyonu — ikinci adım

`--participation-evidence evidence.json` isteğe bağlı şirket/standart kanıtını doğrudan mevcut
`equity_research.participation_screen.assess_participation()` modülüne aktarır.
Yeni borç/gelir faiz oranı hesabı veya yeni Şeriat standardı yazılmadı.
Sembol uyuşmazlığı sert hatadır. Kaynak metaverisi, tarih ve rapor dönemi kontrolleri
ilgili modülde yapılır. Özgün SEC/KAP belge baytlarının SHA karşılaştırılması bu
CLI içinde yapılmadığından `no_live_source_verification=true` kalır.
`kosullu_esik_gecisi` sonucu bile yatırım izni veya resmî endeks üyeliği değildir.
Veri verilmediğinde `bilinmiyor`; banka/sigorta dışlaması mevcut motorun görevidir.

Sonraki kabul: Orijinal belgelerin doğrulanmış hash'leriyle şirket kimliği, faaliyet,
faizli borç/nakit, uygunsuz gelir, kullanılan standardın sürümü ve tarihleri aynı
kanıt paketinde test edilmeli. BIST için XKTUM listesi ayrı, tarihli resmî üyelik
kanıtı olmadan `uygun` sayılamaz.

## SEC finansal kaynak bağlantısı (üçüncü aşama)

AAPL için resmî SEC CIK `0000320193` ile tek şirketlik ve bütçesi sınırlı
`scripts/unified_sec_one_issuer.py`, yeni muhasebe hesaplayıcısı yazmadan
`equity_research.mvp.run_mvp()` fonksiyonunu kullanır. SEC User-Agent iletişim
bilgisi secret üzerinden verilmelidir; eksikse Actions raporu açıkça SEC aşamasını
atladığını söyler, başarılı finansal tarama iddia etmez.

`scripts/unified_single_issuer.py --financial-report <SEC_JSON> --financial-cik 0000320193`
seçeneği tek şirket CIK/sembol eşleşmesini, kaynak zamanını, kabul edilen fact
sayısını ve kaynak arşivi kapsamını kontrol eder. Mevcut SEC toplayıcısının
hesaplarının yerini almaz. `facts_observed_review_required` araştırma statüsüdür;
güncel değerleme veya katılım onayı değildir. Kaynak arşivi eksikse
`incomplete_evidence`. Sıfır veri kesinlikle sıfır finansal değer sayılmaz.

## Türkçe rapor ve ajan devri (dördüncü aşama)

`--markdown unified-single-issuer.md` ile JSON yanında Türkçe araştırma özeti
oluşturulur. Mevcut `equity_research.reporting.build_report` hesaplarını yeniden
hesaplamaz; yalnız önceden doğrulanmış SEC raporundaki kabul edilen olgu sayısı,
hesaplanan sonuç sayısı ve finansal risk ekranını taşır. Bu bir 0–100 yatırım
skoru değildir: fiyat ve SEC finansallarının tarihli tek hisse sınıfı değerleme
kanıtı, karşılaştırmalı dönem ve katılım standardı tamamlanmadı.

İsteğe bağlı ücretsiz LLM takımına yalnız filtrelenmiş **kamusal** finansal
araştırma durumları ve katılım sonucu iletilir. Ham finansal belgeler, fon/
portföy bilgileri, keyfi açıklamalar, hesap bakiyeleri, kaynak URL'leri veya
SEC arşivindeki ham metinler gönderilmez. Ajanların beş çağrısı mock testte
sınanır; **gerçek OpenRouter uç noktası başarılı denenmediği müddetçe**
çalıştığı iddia edilmez. Varsayılan LLM ve alım kararı kapalıdır.

## AAPL kamu haber RSS gözlemi (deneme)

`scripts/unified_single_issuer.py --aapl-news` seçeneği sabit, herkese açık
Google News AAPL RSS arama adresini **mevcut** `market_radar_pilot.news_digest`
ile okur. Yeni veri toplama sağlayıcısı yazılmaz; kaynak başarısızsa
`rss_source_unavailable`, başarılıysa `rss_headlines_only_no_causal_model`.
Başlıkların sayısı ve sabit risk anahtar kelimelerinin kaç kez göründüğü
Türkçe rapora aktarılır. Ham başlık/URL LLM'e gönderilmez; yalnız sayılar
ve erişim durumu aktarılır.

Haber akışında güvenilir `pubDate` yayım/erişim zamanları, kaynak çapraz
doğrulaması, olaya fiyat etkisi bağlantısı ve walk-forward olay modeli
olmadığından canlı yatırım yön tahmini veya otomatik emir **açılmaz**.

Bu kaynak taraması test akışında tek haber bağlantısıyla yapılır; ücretli haber servisi veya işlem erişimi gerektirmez.
