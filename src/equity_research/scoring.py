"""Explainable, limited-sector research hypotheses, not investment approval."""
from .turkish import label, calculation_label
from dataclasses import asdict
from datetime import date,datetime
from decimal import Decimal,localcontext

from .cache import encode
from .companyfacts import SecCompanyFacts,companyfacts_url
from .comparative import build_comparative_report
from .fields import SPECS
from .filingcheck import filing_derived_liabilities
from .market_history import parse_history,history_url
from .models import Fact,FactRequest,aware
from .policy import SCORE_WEIGHTS
from .score_inputs import score_input_provenance
from .reporting import build_report
from .sec import DIRECTORY_URL
from .submissions import parse_submissions,submissions_url
from .valuation import build_valuation_report
from .providers import ProviderFailure,Status
from .legal_evidence import registered_legal_contraindications as _legal_contraindications

MODEL_VERSION='technology-research-v1'
MODELS={'3571':'electronic_computers_v1','3674':'semiconductors_v1',
        '7370':'internet_data_services_v1','7372':'prepackaged_software_v1'}
# Explicit, provisional research bands. These are hypotheses, not backtested
# performance thresholds. Financial/balance-sheet, legal and market gates stay
# identical for every supported operating-company model.
PROFIT_MARGIN_BANDS={
    '7370':[('.25',15),('.15',10),('.08',5),('0',2)],
    '7372':[('.30',15),('.20',10),('.10',5),('0',2)],
}
INDUSTRIAL_PROFIT_BANDS=[('.20',15),('.10',10),('.05',5),('0',2)]
REQUIRED=('assets','liabilities','current_assets','current_liabilities','net_income',
          'operating_income','operating_cash_flow','capital_expenditure','revenue')
SHARE_UPLIFT=Decimal('.25')




def _at_least(value,bands):
    return next((Decimal(str(points)) for minimum,points in bands if value>=Decimal(str(minimum))),Decimal(0))


def _at_most(value,bands):
    return next((Decimal(str(points)) for maximum,points in bands if value<=Decimal(str(maximum))),Decimal(0))


def confirm_score_field(fact, companyfacts, payload, *, annual, original, as_of):
    """Apply the score's exact SEC confirmation to one selected annual fact."""
    spec = SPECS[fact.field]
    request = FactRequest(fact.issuer_id, fact.field, fact.period_start, fact.period_end,
                          'USD', 'currency', spec.accounting_definition, as_of)
    verified = SecCompanyFacts(None)._extract(request, spec.tag, companyfacts, payload)
    if verified is not None:
        if verified.value != fact.value:
            raise ValueError('current SEC confirmation mismatch')
        return dict(field=fact.field, selected=asdict(fact), confirmed=asdict(verified))
    if fact.field != 'liabilities':
        raise ValueError('current SEC confirmation missing')
    if (original is None or original.url != annual.source_url
            or not aware(original.retrieved_at) or original.retrieved_at > as_of):
        raise ValueError('original annual liabilities proof required')
    proof = filing_derived_liabilities(original.body, cik=fact.issuer_id, period_end=annual.report_end)
    if Decimal(proof['value']) != fact.value:
        raise ValueError('derived liabilities confirmation mismatch')
    return dict(field=fact.field, selected=asdict(fact),
                confirmation_method='original_filing_balance_equation',
                confirmation={**proof, 'source_url':original.url,
                              'retrieved_at':original.retrieved_at, 'raw_sha256':original.sha256})


def build_score_report(batch,current_comparison,prior_comparison,responses,*,as_of):
    """Rebuild evidence and all components; incoming scores/approvals are ignored.

    Model coverage is deliberately restricted to three explicit SEC SIC routes.
    A score ranks research hypotheses, not purchases. All six components need
    verified inputs; critical review cannot be offset by any component points.
    """
    if not aware(as_of):raise ValueError('aware scoring cutoff required')
    sources = {}
    for response in responses:
        if response.retrieved_at>as_of:continue
        old=sources.get(response.url)
        if old is None or response.retrieved_at>old.retrieved_at:sources[response.url]=response
        elif old.retrieved_at==response.retrieved_at and old.sha256!=response.sha256:raise ValueError('conflicting raw observations')
    financial=build_report(batch)
    no_comparisons = all(
        isinstance(period, dict) and period.get('schema_version') == 1 and period.get('companies') == []
        for period in (current_comparison, prior_comparison)
    )
    comparative = {}
    if not no_comparisons:
        comparison = build_comparative_report(current_comparison, prior_comparison)
        if datetime.fromisoformat(str(comparison['as_of'])) > as_of:
            raise ValueError('future comparison')
        comparative = {c['issuer_id']: c for c in comparison['companies']}
    provenance=score_input_provenance(batch,current_comparison,prior_comparison,as_of=as_of)
    valuations=build_valuation_report(batch,sources.values(),as_of=as_of)
    by_valuation={c['issuer_id']:c for c in valuations['companies']}
    companies=[]
    for company in financial['companies']:
        cik,symbol=company['issuer_id'],company['symbol'];gate=company['financial_assessment']['quantitative_gate']
        row=dict(issuer_id=cik,symbol=symbol,status='review_required',model_version=MODEL_VERSION,
            model_id=None,components={k:dict(weight=w,score=None) for k,w in SCORE_WEIGHTS.items()},
            total_score=None,rank=None,blockers=[],model_scope_eligible=False,investment_approved=False,
            financial_review=company['financial_assessment'],valuation=None,market_risk=None,
            limitations=['research_threshold_hypotheses_not_validated_return_prediction',
                'qualitative_filings_news_governance_and_full_capital_changes_not_cleared'])
        companies.append(row)
        if gate=='critical_review_required':
            row.update(status='critical_review_required',blockers=['critical_financial_review']);continue
        if gate=='invalid_evidence':row['blockers']=['invalid_financial_evidence'];continue
        # A model-unsupported issuer cannot become scoreable by collecting
        # more prices. Check its observed SEC category first so that the
        # missing-valuation queue contains only potentially modeled issuers.
        # Unavailable/malformed metadata is not treated as evidence of an
        # unsupported SIC: its existing valuation/source gate still applies.
        metadata_for_scope=sources.get(submissions_url(cik))
        if metadata_for_scope is not None:
            try:
                scope_snapshot=parse_submissions(metadata_for_scope,cik)
            except (ProviderFailure, ValueError, KeyError, TypeError, ArithmeticError):
                scope_snapshot=None
            if (scope_snapshot is not None and
                    (scope_snapshot.entity_type_label!='operating'
                     or scope_snapshot.sic_label not in MODELS)):
                row['sector_evidence']=dict(sic=scope_snapshot.sic_label,
                    entity_type=scope_snapshot.entity_type_label,
                    source_url=metadata_for_scope.url,
                    raw_sha256=metadata_for_scope.sha256,
                    retrieved_at=metadata_for_scope.retrieved_at)
                row['blockers']=['specialized_or_unmodeled_sector']
                continue
        value=by_valuation[cik]['valuation']
        if value is None:
            row['blockers']=['valuation_source_evidence_required']
            row['valuation_diagnostics']={k:by_valuation[cik][k] for k in ('status','missing_source_urls','missing_evidence','provider_status','failed_validation_stage','failure_detail','source_observations') if k in by_valuation[cik]}
            continue
        validation_stage='metadata_and_sector'
        try:
            metadata=sources[submissions_url(cik)];snapshot=parse_submissions(metadata,cik)
            row['sector_evidence']=dict(sic=snapshot.sic_label,entity_type=snapshot.entity_type_label,
                source_url=metadata.url,raw_sha256=metadata.sha256,retrieved_at=metadata.retrieved_at)
            if snapshot.entity_type_label!='operating' or snapshot.sic_label not in MODELS:
                row['blockers']=['specialized_or_unmodeled_sector'];continue
            row['model_id']=MODELS[snapshot.sic_label]
            validation_stage='original_share_filing_legal_flags'
            legal=_legal_contraindications(sources[value['disclosed_shares']['original_filing']['url']],cik)
            row['legal_disclosure_review']=legal
            if legal['blocked']:
                row['blockers']=['fund_bdc_or_shell_disclosure_requires_specialized_review'];continue
            facts={f['query']['field']:Fact(**f['fact']) for f in company['fields'] if f['fact']}
            missing=[f for f in REQUIRED if f not in facts]
            if missing or gate!='no_screen_trigger':
                row.update(status='pending_model_inputs',blockers=['complete_financial_review_required'],missing_fields=missing);continue
            annual=snapshot.latest_annual()
            if annual is None or annual.report_end.isoformat()!=company['period_end']:
                row['blockers']=['latest_annual_period_not_confirmed'];continue
            if not 350<=(date.fromisoformat(company['period_end'])-date.fromisoformat(company['period_start'])).days+1<=380:
                row['blockers']=['full_annual_period_required'];continue
            validation_stage='companyfacts_identity'
            cf=sources[companyfacts_url(cik)];payload=SecCompanyFacts._parse(cf,cik)[1];checks=[]
            for field in REQUIRED:
                validation_stage='financial_confirmation.'+field
                checks.append(confirm_score_field(facts[field], cf, payload, annual=annual,
                    original=sources.get(annual.source_url), as_of=as_of))
            peer=comparative.get(cik)
            if peer is None or peer['symbol']!=symbol or peer['status']!='review_required':
                row['blockers']=['comparable_revenue_required'];continue
            growth=next((c for c in peer['calculations'] if c['field']=='revenue'),None)
            if growth is None or growth['value'] is None:
                row['blockers']=['comparable_revenue_required'];continue
            current,prior=(Fact(**f) for f in growth['inputs'])
            if any(getattr(current,k)!=getattr(facts['revenue'],k) for k in ('issuer_id','period_start','period_end','currency','accounting_definition','value')):
                row['blockers']=['growth_current_period_or_definition_conflict'];continue
            request=FactRequest(cik,'revenue',prior.period_start,prior.period_end,'USD','currency',SPECS['revenue'].accounting_definition,as_of)
            validation_stage='prior_revenue_confirmation'
            check_prior=SecCompanyFacts(None)._extract(request,SPECS['revenue'].tag,cf,payload)
            if check_prior is None or check_prior.value!=prior.value:raise ValueError('prior revenue confirmation mismatch')
            price=value['price'];shares=value['disclosed_shares']
            history=sources.get(history_url(symbol))
            if history is None:row['blockers']=['market_history_required'];continue
            validation_stage='market_history'
            market=parse_history(history,sources[DIRECTORY_URL],cik=cik,symbol=symbol,
                share_date=shares['disclosed_on'],price_market_at=price['market_at'],as_of=as_of)
            row['market_risk']=market
            if market['split_window_status']!='no_split_record_in_returned_window':
                row['blockers']=['split_since_disclosed_count_requires_review'];continue
            if abs(market['latest_daily_close']/price['value']-1)>Decimal('.20'):
                row['blockers']=['quote_history_price_disagreement_requires_review'];continue
            if market['median_63_session_close_times_volume']<Decimal(5000000):
                row['blockers']=['insufficient_observed_trading_liquidity'];continue
            assets,liabilities,ca,cl,ni,oi,ocf,ppe,revenue=(facts[f].value for f in REQUIRED)
            if assets<=0 or cl<=0 or revenue<=0 or ppe<0:
                row['blockers']=['unsupported_ratio_base_or_payment_sign'];continue
            validation_stage='component_calculation'
            with localcontext() as ctx:
                magnitude=max(max(len(f.value.as_tuple().digits),abs(f.value.adjusted())) for f in facts.values())
                if magnitude>1000:raise ValueError('unsupported financial magnitude')
                ctx.prec=max(100,magnitude*2+20)
                leverage=liabilities/assets;liquidity=ca/cl;margin=oi/revenue;cash=ocf-ppe;cash_margin=cash/revenue
                precision=shares['decimals'];rounding=Decimal(0) if precision=='INF' else Decimal(10)**(-int(precision))
                stressed_cap=price['value']*(shares['value']+rounding)*(1+SHARE_UPLIFT)
                stressed_yield=cash/stressed_cap
                strength=_at_most(leverage,[('.3',10),('.5',7.5),('.7',5),('1',2.5)])+_at_least(liquidity,[('2',10),('1.5',7.5),('1',5),('.75',2.5)])
                valuation=_at_least(stressed_yield,[('.08',20),('.06',15),('.04',10),('.02',5)])
                growth_points=_at_least(growth['value'],[('.20',20),('.10',15),('.05',10),('0',5)])
                thresholds=PROFIT_MARGIN_BANDS.get(snapshot.sic_label,INDUSTRIAL_PROFIT_BANDS)
                profit=_at_least(margin,thresholds)
                cash_points=_at_least(cash_margin,[('.20',15),('.10',10),('.05',5),('0',2)])
                vol=market['annualized_sample_volatility'];dollar_volume=market['median_63_session_close_times_volume']
                vol_penalty=_at_least(vol,[('.60',3),('.40',2),('.25',1)])
                liquidity_penalty=Decimal(0) if dollar_volume>=50000000 else Decimal(1) if dollar_volume>=10000000 else Decimal(2)
                income_loss_penalty=Decimal(2) if ni<0 else Decimal(0)
                risk=max(Decimal(0),Decimal(10)-2*len(company['financial_assessment']['watch_flags'])-income_loss_penalty-vol_penalty-liquidity_penalty)
                points=dict(financial_strength=strength,valuation=valuation,growth=growth_points,profitability=profit,cash_flow=cash_points,risk=risk)
                if any(not score.is_finite() or not 0<=score<=SCORE_WEIGHTS[name] for name,score in points.items()):
                    raise ValueError('component outside its published weight')
                row['components']={name:dict(weight=SCORE_WEIGHTS[name],score=score) for name,score in points.items()}
                bases=dict(
                    financial_strength=dict(formula='liabilities/assets band + current-assets/current-liabilities band',
                        liabilities_to_assets=leverage,current_ratio=liquidity),
                    valuation=dict(formula='OCF less PP&E payments / stressed indicated capitalization band',value=stressed_yield),
                    growth=dict(formula='exact annual contract revenue / prior comparable annual contract revenue - 1 band',value=growth['value']),
                    profitability=dict(formula='operating income / contract revenue, sector-specific band',value=margin),
                    cash_flow=dict(formula='OCF less PP&E payments / contract revenue band',value=cash_margin),
                    risk=dict(formula='max(0, 10 - 2*watch-count - net-loss penalty - observed-volatility penalty - dollar-volume penalty)',
                        watch_flags=company['financial_assessment']['watch_flags'],net_loss_penalty=income_loss_penalty,
                        volatility_penalty=vol_penalty,liquidity_penalty=liquidity_penalty))
                for name,basis in bases.items():row['components'][name]['basis']=basis
                row['total_score']=sum(points.values())
            row.update(status='scored_research_hypothesis',model_scope_eligible=True,
                evidence=dict(financial_confirmations=checks,prior_revenue_confirmation=asdict(check_prior),growth=growth),
                metrics=dict(liabilities_to_assets=leverage,current_ratio=liquidity,operating_margin=margin,
                    ocf_less_ppe_margin=cash_margin,contract_revenue_growth=growth['value']),
                valuation=dict(indication=value,stressed_capitalization=stressed_cap,stressed_ocf_less_ppe_yield=stressed_yield,
                    assumed_share_count_uplift=SHARE_UPLIFT,rounding_allowance_shares=rounding,
                    assumption='25% extra shares plus one reported precision quantum; stress scenario, not a confidence interval'),
                rationale=['all six required components computed from verified inputs','critical financial review checked before totals',
                    'valuation uses explicit dated-share stress assumption','qualitative risk clearance and investment approval remain absent'])
        except (ProviderFailure,ValueError,KeyError,TypeError,ArithmeticError) as exc:
            row.update(status='evidence_rejected',failed_validation_stage=validation_stage,blockers=['source_period_definition_class_or_market_contract_failed'],
                provider_status=exc.status.value if isinstance(exc,ProviderFailure) else Status.INVALID_DATA.value,
                total_score=None,model_scope_eligible=False,components={k:dict(weight=w,score=None) for k,w in SCORE_WEIGHTS.items()})
    ordered=sorted((c for c in companies if c['status']=='scored_research_hypothesis' and c['total_score'] is not None),key=lambda c:(-c['total_score'],c['symbol'],c['issuer_id']))
    ranking=[]
    for i,c in enumerate(ordered,1):
        c['rank']=i;ranking.append(dict(rank=i,symbol=c['symbol'],issuer_id=c['issuer_id'],score=c['total_score'],model_id=c['model_id']))
    return dict(schema_version=1,model_version=MODEL_VERSION,as_of=as_of,score_weights=dict(SCORE_WEIGHTS),
        companies=companies,ranking=ranking,input_provenance=provenance,summary=dict(candidates=len(companies),scored_companies=len(ranking),
            critical_review=sum(c['status']=='critical_review_required' for c in companies),unscored=len(companies)-len(ranking)),
        mvp_accepted=False,hundred_active_common_shares_accepted=False,new_network_requests=0,
        limitations=['limited_SIC_model_coverage','no_strategy_performance_validation','not_investment_or_trade_approval'])


def render_score_markdown(report):
    import html
    def cell(value):return html.escape(label(value)).replace('|','&#124;').replace('\n',' ')
    lines=['# ABD Hisse Araştırması — araştırma puanları','',f"Model: {cell(report['model_version'])}; kaynak verilerinin kesim zamanı: {cell(report['as_of'])}",'',
        'Puanlar araştırma varsayımlarıdır; yatırım onayı veya doğrulanmış getiri tahmini değildir. İlk sürümün (MVP) kabulü bekleniyor.','',
        '| Sıra | Sembol | Puan / 100 | Model |','| ---: | --- | ---: | --- |']
    if report.get('input_provenance'):
        lines[4:4]=['Finansal ve karşılaştırma girdilerinin özgün kaynak tarihleri korunmuştur. Bu raporun üretilmesi 100 şirketin tüm finansal girdilerinin güncellendiği anlamına gelmez.', '']
        for name, source in report['input_provenance']['batches'].items():
            lines[4:4]=[cell(name)+': üretim zamanı '+cell(source['generated_at'])+'; seçili gözlemler '+cell(source['oldest_selected_observation'])+' ile '+cell(source['newest_selected_observation'])+'; SHA-256 '+cell(source['sha256'])+'.', '']
    for c in report['ranking']:lines.append('| '+' | '.join(cell(c[k]) for k in ('rank','symbol','score','model_id'))+' |')
    lines.extend(['','| Aday | Durum | Puanın hesaplanmama nedenleri |','| --- | --- | --- |'])
    for c in report['companies']:lines.append('| '+' | '.join(cell(v) for v in (c['symbol'],c['status'],'; '.join(c['blockers']+([c['failed_validation_stage']] if c.get('failed_validation_stage') else [])) or 'none for numeric research model'))+' |')
    from .valuation_diagnostics import diagnostic_lines
    for c in report['companies']:
        if c['total_score'] is None:
            details=diagnostic_lines(c.get('valuation_diagnostics'))
            if details:lines.extend(['','## '+cell(c['symbol']),'']+[cell(v) for v in details])
            continue
        lines.extend(['','## '+cell(c['symbol']),'','| Bileşen | Puan | Ağırlık |','| --- | ---: | ---: |'])
        for name,r in c['components'].items():lines.append('| '+' | '.join(cell(v) for v in (name,r['score'],r['weight']))+' |')
        lines.extend(['','Değerlemede bildirilen hisse adedine %25 ve bir raporlama hassasiyet birimi eklenir. Bu bir stres varsayımıdır; gözlenen hisse sayısı veya güven aralığı değildir.',
            'Finansal uygunluk, değerleme puanı ve gözlenen piyasa riski ayrı değerlendirilir. Nitel risk, yönetim ve sermaye değişiklikleri onaylanmamıştır; yatırım onayı verilmemiştir.',''])
        for field,value in c['metrics'].items():lines.append(cell(field)+': '+cell(format(Decimal(str(value)),'.6f'))+'.')
        market=c['market_risk'];valuation=c['valuation']['indication']
        lines.extend(['',cell(market['source_url'])+' · SHA-256 '+cell(market['raw_sha256'])+'.',
            cell(c['sector_evidence']['source_url'])+' · SHA-256 '+cell(c['sector_evidence']['raw_sha256'])+'.',
            cell(valuation['disclosed_shares']['original_filing']['url'])+' · SHA-256 '+cell(valuation['disclosed_shares']['original_filing']['raw_sha256'])+'.',
            'Tüm bileşen girdileri, doğrulamalar ve ilk geçerli kaynağa kadar yapılan denemeler JSON kaydında korunmuştur.'])
    return '\n'.join(lines)+'\n'
