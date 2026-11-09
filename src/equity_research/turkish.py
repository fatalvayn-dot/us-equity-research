"""Turkish presentation labels. Never translate or mutate machine-readable evidence.

Unknown codes remain visible verbatim so a new diagnostic cannot become a
misleading generic success. Accounting tags, source URLs and dates stay literal.
"""
LABELS = {
    'stale_quote':'Piyasa fiyatının tarihi eski', 'stale_response':'Fiyat gözleminin tazelik süresi dolmuş',
    'stale_identity':'Şirket kimliği gözleminin tazelik süresi dolmuş',
    'stale_share_companyfacts': 'SEC CompanyFacts hisse gözleminin tazelik süresi dolmuş',
    'stale_share_disclosure': 'Bildirilen hisse adedinin tarihi güncelliğini yitirmiş',
    'class_specific_share_model_required': 'Hisse sınıflarını ayrı ele alan değerleme modeli gerekiyor',
    'future_observation':'Gelecek tarihli kaynak gözlemi',
    'unsupported_instrument':'Desteklenmeyen araç türü',
    'unsupported_or_conflicting_exchange':'Desteklenmeyen veya çelişkili borsa bilgisi',
    'currency_mismatch':'Para birimi uyuşmazlığı',
    'ambiguous_original_share_filing':'Aynı bildirim için birden fazla özgün dosya var',
    'financial_strength': 'Finansal sağlamlık', 'valuation': 'Değerleme',
    'growth': 'Büyüme', 'profitability': 'Kârlılık', 'cash_flow': 'Nakit akışı', 'risk': 'Risk',
    'assets': 'Toplam varlıklar', 'liabilities': 'Toplam yükümlülükler',
    'revenue': 'Vergiler hariç müşteri sözleşmesi hasılatı', 'revenue_total': 'Bildirilen toplam hasılat (Revenues)',
    'net_income': 'Net dönem kârı / zararı (NetIncomeLoss)', 'profit_loss': 'Bildirilen kâr / zarar (ProfitLoss)',
    'operating_cash_flow': 'Faaliyetlerden nakit akışı', 'capital_expenditure': 'Maddi duran varlık alım ödemeleri',
    'productive_asset_cash_payments': 'Üretken varlık alım ödemeleri (ProductiveAssets)',
    'current_assets': 'Dönen varlıklar', 'current_liabilities': 'Kısa vadeli yükümlülükler',
    'cash_equivalents': 'Nakit ve nakit benzerleri', 'operating_income': 'Faaliyet kârı / zararı', 'gross_profit': 'Brüt kâr',
    'liabilities_to_assets': 'Toplam yükümlülükler / toplam varlıklar', 'current_ratio': 'Cari oran',
    'operating_margin': 'Faaliyet kâr marjı', 'ocf_less_ppe_margin': 'Maddi duran varlık ödemeleri sonrası faaliyet nakdi / hasılat',
    'contract_revenue_growth': 'Müşteri sözleşmesi hasılatı büyümesi',
    'financial': 'Finansal girdiler', 'current_comparison': 'Cari dönem karşılaştırma girdileri',
    'prior_comparison': 'Önceki dönem karşılaştırma girdileri',
    'semiconductors_v1': 'Yarı iletkenler (v1)', 'prepackaged_software_v1': 'Hazır yazılım (v1)',
    'electronic_computers_v1': 'Bilgisayar üretimi (v1)',
    'technology-research-v1': 'Teknoloji araştırması (v1)',
    'valid': 'Geçerli', 'missing': 'Kaynakta bulunamadı', 'unavailable': 'Mevcut değil',
    'not_started': 'Henüz denenmedi', 'not attempted': 'Henüz denenmedi', 'unresolved': 'Çözümlenmedi',
    'unknown': 'Bilinmiyor', 'instant': 'Bilanço tarihi', 'currency': 'Para tutarı', 'ratio': 'Oran',
    'review_required': 'İnceleme gerekiyor', 'critical_review_required': 'Kritik inceleme gerekiyor',
    'critical_financial_review': 'Kritik finansal inceleme gerekiyor',
    'evidence_rejected': 'Kaynak kanıtı reddedildi', 'invalid_evidence': 'Geçersiz kaynak kanıtı',
    'scored_research_hypothesis': 'Araştırma modeli puanı hesaplandı', 'pending_model_inputs': 'Model girdileri bekleniyor',
    'no_screen_trigger': 'Bu taramada uyarı oluşmadı', 'triggered': 'Uyarı oluştu', 'not_triggered': 'Uyarı oluşmadı',
    'pending_data': 'Veri bekleniyor', 'collection_error': 'Veri toplama hatası', 'stale_data': 'Veri güncel değil',
    'collected': 'Toplandı', 'out_of_scope': 'Kapsam dışında', 'pending_scope': 'Kapsam doğrulaması bekleniyor',
    'period_unresolved': 'Dönem çözümlenemedi', 'period_mismatch': 'Dönem uyuşmazlığı',
    'not_configured': 'Yapılandırılmadı', 'unsupported_field': 'Alan desteklenmiyor',
    'invalid_data': 'Geçersiz veri', 'rate_limit': 'İstek sınırına ulaşıldı', 'api_error': 'Kaynak hizmeti hatası',
    'evidence_error': 'Kaynak kanıtı hatası', 'symbol_mismatch': 'Sembol uyuşmazlığı',
    'timeout': 'Zaman aşımı', 'access_denied': 'Erişim reddedildi', 'invalid_configuration': 'Geçersiz yapılandırma',
    'calculated_arithmetic_only': 'Aritmetik hesaplandı; model onayı yok', 'indicative_arithmetic_only': 'Gösterge hesabı; model onayı yok',
    'invalid_inputs': 'Geçersiz girdiler', 'nonpositive_denominator': 'Payda sıfır veya negatif',
    'pending_source_evidence': 'Kaynak kanıtları bekleniyor',
    'nonpositive_base': 'Önceki dönem tabanı sıfır veya negatif',
    'contract_revenue_to_indicated_cap': 'Müşteri sözleşmesi hasılatı / gösterge sermaye değeri',
    'issuer_net_income_to_indicated_cap': 'Şirket net kârı / gösterge sermaye değeri',
    'ocf_less_ppe_payments_to_indicated_cap': 'Maddi duran varlık ödemeleri sonrası faaliyet nakdi / gösterge sermaye değeri',
    'share_disclosure_can_be_rounded_and_up_to_120_days_old': 'Bildirilen hisse sayısı yuvarlanmış ve 120 güne kadar eski olabilir',
    'issuer_net_income_not_common_share_earnings': 'Şirketin net kârı adi hissedarlara ait kazanç olarak doğrulanmadı',
    'ocf_less_ppe_payments_not_complete_owner_earnings': 'Maddi duran varlık ödemeleri sonrası faaliyet nakdi kapsamlı bir ortak kazancı ölçüsü değildir',
    'not_yet_public': 'Kesim zamanında henüz kamuya açıklanmamış',
    'unverified_historical_vintage': 'Verinin geçmişte o tarihte mevcut olduğu doğrulanmadı',
    'nonpositive_prior_base': 'Önceki dönem tabanı sıfır veya negatif',
    'unsupported_balance_sign': 'Bilanço tutarının işareti desteklenmiyor',
    'unsupported_payment_sign': 'Ödeme tutarının işareti desteklenmiyor', 'unsupported_magnitude': 'Tutar büyüklüğü desteklenmiyor',
    'balance_deficit': 'Yükümlülüklerin varlıkları aşması',
    'loss_and_operating_cash_outflow': 'Dönem zararı ve faaliyet nakit çıkışı',
    'operating_loss': 'Faaliyet zararı', 'current_balance_shortfall': 'Dönen varlık açığı',
    'fund_legal_type_and_sector_model_not_accepted': 'Fon niteliği ve sektör modeli henüz onaylanmadı',
    'verified_common_share_scope_required': 'Adi hisse kapsamı doğrulanmalı',
    'accepted_sector_model_required': 'Onaylanmış sektör modeli gerekiyor',
    'source_bound_valuation_required': 'Kaynaklarla doğrulanmış değerleme gerekiyor',
    'complete_validated_score_components_required': 'Puanlama bileşenleri eksiksiz doğrulanmalı',
    'qualitative_risk_review_required': 'Nitel risk incelemesi gerekiyor',
    'qualitative_and_sector_review_required': 'Nitel risk ve sektör incelemesi gerekiyor',
    'sector_model_and_scope_review_required': 'Sektör modeli ve kapsam incelemesi gerekiyor',
    'market_price_shares_and_valuation_model_required': 'Piyasa fiyatı, hisse adedi ve değerleme modeli gerekiyor',
    'comparable_prior_period_and_model_required': 'Karşılaştırılabilir önceki dönem ve model gerekiyor',
    'validated_risk_model_required': 'Doğrulanmış risk modeli gerekiyor',
    'active_common_share_and_sector_model_review_required': 'Aktif adi hisse kapsamı ve sektör modeli incelenmeli',
    'valuation_source_evidence_required': 'Değerleme girdilerinin kaynak kanıtları gerekiyor',
    'source_period_definition_class_or_market_contract_failed': 'Kaynak, dönem, tanım, hisse sınıfı veya piyasa verisi doğrulaması başarısız',
    'invalid_financial_evidence': 'Finansal verilerin kaynak kanıtları geçersiz',
    'specialized_or_unmodeled_sector': 'Sektör için özel model gerekiyor veya model henüz yok',
    'fund_bdc_or_shell_disclosure_requires_specialized_review': 'Fon, BDC veya paravan şirket bildirimi özel inceleme gerektiriyor',
    'complete_financial_review_required': 'Finansal inceleme tamamlanmalı',
    'latest_annual_period_not_confirmed': 'Son yıllık dönem doğrulanamadı', 'full_annual_period_required': 'Tam yıllık dönem gerekiyor',
    'comparable_revenue_required': 'Karşılaştırılabilir hasılat gerekiyor',
    'growth_current_period_or_definition_conflict': 'Büyüme hesabında cari dönem veya tanım uyuşmazlığı',
    'market_history_required': 'Piyasa geçmişi gerekiyor', 'split_since_disclosed_count_requires_review': 'Bildirilen hisse tarihinden sonraki bölünme incelenmeli',
    'quote_history_price_disagreement_requires_review': 'Anlık fiyat ile geçmiş fiyat uyuşmazlığı incelenmeli',
    'insufficient_observed_trading_liquidity': 'Gözlenen işlem likiditesi yetersiz',
    'unsupported_ratio_base_or_payment_sign': 'Oran tabanı veya ödeme işareti desteklenmiyor',
    'none for numeric research model': 'Sayısal araştırma modeli için engel yok',
    'annual_input_not_latest_statement_confirmation': 'Yıllık girdi en son finansal tabloyu doğrulamaz',
    'capital_changes_since_share_date_unverified': 'Hisse adedi tarihinden sonraki sermaye değişiklikleri doğrulanmadı',
    'sector_model_and_security_scope_pending': 'Sektör modeli ve menkul kıymet kapsamı bekleniyor',
    'not_observed_current_market_capitalization': 'Güncel piyasa değeri gözlemi değildir',
    'not_fair_value': 'Adil değer değildir', 'metadata_unavailable': 'Şirket bilgileri mevcut değil',
    'no_annual_in_recent_window': 'İncelenen yakın dönemde yıllık bildirim bulunamadı',
    'annual_period_unresolved': 'Yıllık dönem çözümlenemedi',
    'future_financial_period': 'Finansal dönem gelecekte', 'stale_financial_period': 'Finansal dönem güncelliğini yitirmiş',
    'explicit_full_annual_period_required': 'Açıkça belirtilmiş tam yıllık dönem gerekiyor',
    'invalid_fact_type': 'Geçersiz finansal veri türü', 'missing_raw_source_hash': 'Ham kaynak özeti eksik',
}

# Display descriptions only: retain canonical English explanations in JSON.
from .assessment import CHECKS
_DESCRIPTIONS = (
    'Bildirilen yükümlülükler varlıkları aşıyor. Özkaynaklar, geri alımlar ve yükümlülükler incelenmeli. Bu bulgu tek başına ödeme aczi anlamına gelmez.',
    'Aynı yıllık dönemde NetIncomeLoss ve faaliyet nakit akışı negatif. Finansman ihtiyacı ve nakdin yeterli olacağı süre incelenmeli.',
    'Bildirilen faaliyet sonucu negatif. Zararın sürekliliği ve olağan dışı kalemler incelenmeli.',
    'Dönen varlıklar kısa vadeli yükümlülüklerin altında. Nakit dönüşümü ve vadeler incelenmeli. Bu kontrol ödeme aczi testi değildir.',
)
LABELS.update({check[3]: description for check, description in zip(CHECKS, _DESCRIPTIONS)})


def label(value):
    """Translate exact presentation tokens; preserve unknown/source-owned text."""
    text = str(value)
    if text in LABELS:
        return LABELS[text]
    if text.startswith('mismatch:'):
        return 'Uyuşmazlık: ' + LABELS.get(text.removeprefix('mismatch:'), text.removeprefix('mismatch:'))
    if text.startswith('financial_confirmation.'):
        field = text.removeprefix('financial_confirmation.')
        return 'Finansal doğrulama: ' + LABELS.get(field, field) + ' (' + text + ')'
    if '; ' in text:
        return '; '.join(label(part) for part in text.split('; '))
    return text


def calculation_label(row):
    """Show exact operands in Turkish without changing a formula or its values."""
    from .calculations import CALCULATIONS
    spec = CALCULATIONS.get(row.get('calculation'))
    if spec is None:
        return row['formula']
    operator = ' / ' if spec.operation == 'divide' else ' − '
    formula = operator.join(label(field) for field in spec.fields)
    if 'profit_loss' in spec.fields:
        formula += '; adi hisseye ait kâr kapsamı doğrulanmadı'
    if spec.name == 'cash_after_ppe_payments':
        formula += '; kapsamlı bir ortak kazancı ölçüsü değildir'
    if spec.name == 'cash_after_productive_asset_payments':
        formula += '; yalnız maddi duran varlık harcaması değildir'
    if spec.name == 'working_capital':
        formula += '; negatif sonuç tek başına ödeme aczi kanıtı değildir'
    if spec.name == 'cash_equivalents_to_current_liabilities':
        formula += '; yatırımlar dahil değildir'
    return formula
