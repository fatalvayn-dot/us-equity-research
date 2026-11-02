"""Explainable, limited-sector research hypotheses, not investment approval."""
from dataclasses import asdict
from datetime import date,datetime
from decimal import Decimal,localcontext

from .cache import encode
from .companyfacts import SecCompanyFacts,companyfacts_url
from .comparative import build_comparative_report
from .fields import SPECS
from .market_history import parse_history,history_url
from .models import Fact,FactRequest,aware
from .policy import SCORE_WEIGHTS
from .reporting import build_report
from .sec import DIRECTORY_URL
from .submissions import parse_submissions,submissions_url
from .valuation import build_valuation_report
from .providers import ProviderFailure,Status
from .filing_metadata import CoverParser
from .legal_evidence import CONCEPTS,_disclosures,_boolean

MODEL_VERSION='technology-research-v1'
MODELS={'3571':'electronic_computers_v1','3674':'semiconductors_v1','7372':'prepackaged_software_v1'}
REQUIRED=('assets','liabilities','current_assets','current_liabilities','net_income',
          'operating_income','operating_cash_flow','capital_expenditure','revenue')
SHARE_UPLIFT=Decimal('.25')


def _legal_contraindications(filing,cik):
    """A known fund/BDC/shell disclosure overrides an apparently supported SIC.

    Missing tags stay unknown. Positive model eligibility instead requires the
    operating-issuer SIC, original common-share cover and current US quote.
    This screen is not a legal opinion or permanent absence-of-fund certification.
    """
    p=CoverParser(extra_concepts=CONCEPTS.values());p.feed(filing.body.decode('utf-8'));p.close()
    if p.conflict or p.context is not None or p.fact_stack:raise ValueError('invalid legal disclosure context')
    contexts=[key for key,c in p.contexts.items() if not c['dimensional'] and c.get('scheme')=='http://www.sec.gov/CIK'
              and c.get('identifier','').strip().zfill(10)==cik]
    flags=_disclosures(p,contexts,allow_transforms=True)
    blocked=any(r['status'] not in ('reported','unknown') or (r['status']=='reported' and r['value'] not in (False,None))
                for key,r in flags.items() if key!='reit')
    shell=[]
    for f in p.facts:
        if f['name']=='entityshellcompany' and f['context'] in contexts and f['nil'] not in ('true','1'):
            shell.append(_boolean(' '.join(f['text'].split()),f['format'],p.namespaces))
    if len(set(shell))>1:raise ValueError('conflicting shell status')
    return dict(disclosures=flags,shell_status='reported' if shell else 'unknown',
        shell_value=shell[0] if shell else None,blocked=blocked or any(shell),
        source_url=filing.url,raw_sha256=filing.sha256,legal_type_approved=False)


def _at_least(value,bands):
    return next((Decimal(str(points)) for minimum,points in bands if value>=Decimal(str(minimum))),Decimal(0))


def _at_most(value,bands):
    return next((Decimal(str(points)) for maximum,points in bands if value<=Decimal(str(maximum))),Decimal(0))


def build_score_report(batch,current_comparison,prior_comparison,responses,*,as_of):
    """Rebuild evidence and all components; incoming scores/approvals are ignored.

    Model coverage is deliberately restricted to three explicit SEC SIC routes.
    A score ranks research hypotheses, not purchases. All six components need
    verified inputs; critical review cannot be offset by any component points.
    """
    if not aware(as_of):raise ValueError('aware scoring cutoff required')
    responses=list(responses);sources={}
    for response in responses:
        if response.retrieved_at>as_of:continue
        old=sources.get(response.url)
        if old is None or response.retrieved_at>old.retrieved_at:sources[response.url]=response
        elif old.retrieved_at==response.retrieved_at and old.sha256!=response.sha256:raise ValueError('conflicting raw observations')
    financial=build_report(batch)
    comparison=build_comparative_report(current_comparison,prior_comparison)
    if datetime.fromisoformat(str(comparison['as_of']))>as_of:raise ValueError('future comparison')
    comparative={c['issuer_id']:c for c in comparison['companies']}
    valuations=build_valuation_report(batch,responses,as_of=as_of)
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
        value=by_valuation[cik]['valuation']
        if value is None:
            row['blockers']=['valuation_source_evidence_required'];continue
        try:
            metadata=sources[submissions_url(cik)];snapshot=parse_submissions(metadata,cik)
            row['sector_evidence']=dict(sic=snapshot.sic_label,entity_type=snapshot.entity_type_label,
                source_url=metadata.url,raw_sha256=metadata.sha256,retrieved_at=metadata.retrieved_at)
            if snapshot.entity_type_label!='operating' or snapshot.sic_label not in MODELS:
                row['blockers']=['specialized_or_unmodeled_sector'];continue
            row['model_id']=MODELS[snapshot.sic_label]
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
            cf=sources[companyfacts_url(cik)];payload=SecCompanyFacts._parse(cf,cik)[1];checks=[]
            for field in REQUIRED:
                f=facts[field];spec=SPECS[field]
                request=FactRequest(cik,field,f.period_start,f.period_end,'USD','currency',spec.accounting_definition,as_of)
                verified=SecCompanyFacts(None)._extract(request,spec.tag,cf,payload)
                if verified is None or verified.value!=f.value:raise ValueError('current SEC confirmation mismatch')
                checks.append(dict(field=field,selected=asdict(f),confirmed=asdict(verified)))
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
            check_prior=SecCompanyFacts(None)._extract(request,SPECS['revenue'].tag,cf,payload)
            if check_prior is None or check_prior.value!=prior.value:raise ValueError('prior revenue confirmation mismatch')
            price=value['price'];shares=value['disclosed_shares']
            history=sources.get(history_url(symbol))
            if history is None:row['blockers']=['market_history_required'];continue
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
                thresholds=[('.30',15),('.20',10),('.10',5),('0',2)] if snapshot.sic_label=='7372' else [('.20',15),('.10',10),('.05',5),('0',2)]
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
            row.update(status='evidence_rejected',blockers=['source_period_definition_class_or_market_contract_failed'],
                provider_status=exc.status.value if isinstance(exc,ProviderFailure) else Status.INVALID_DATA.value,
                total_score=None,model_scope_eligible=False,components={k:dict(weight=w,score=None) for k,w in SCORE_WEIGHTS.items()})
    ordered=sorted((c for c in companies if c['status']=='scored_research_hypothesis' and c['total_score'] is not None),key=lambda c:(-c['total_score'],c['symbol'],c['issuer_id']))
    ranking=[]
    for i,c in enumerate(ordered,1):
        c['rank']=i;ranking.append(dict(rank=i,symbol=c['symbol'],issuer_id=c['issuer_id'],score=c['total_score'],model_id=c['model_id']))
    return dict(schema_version=1,model_version=MODEL_VERSION,as_of=as_of,score_weights=dict(SCORE_WEIGHTS),
        companies=companies,ranking=ranking,summary=dict(candidates=len(companies),scored_companies=len(ranking),
            critical_review=sum(c['status']=='critical_review_required' for c in companies),unscored=len(companies)-len(ranking)),
        mvp_accepted=False,hundred_active_common_shares_accepted=False,new_network_requests=0,
        limitations=['limited_SIC_model_coverage','no_strategy_performance_validation','not_investment_or_trade_approval'])


def render_score_markdown(report):
    import html
    def cell(value):return html.escape(str(value)).replace('|','&#124;').replace('\n',' ')
    lines=['# US Equity research scores','',f"Model: {cell(report['model_version'])}; evidence cutoff: {cell(report['as_of'])}",'',
        'Scores are research hypotheses, not investment approval or validated return predictions. MVP acceptance pending.','',
        '| Rank | Symbol | Score / 100 | Model |','| ---: | --- | ---: | --- |']
    for c in report['ranking']:lines.append('| '+' | '.join(cell(c[k]) for k in ('rank','symbol','score','model_id'))+' |')
    lines.extend(['','| Candidate | Status | Blockers |','| --- | --- | --- |'])
    for c in report['companies']:lines.append('| '+' | '.join(cell(v) for v in (c['symbol'],c['status'],'; '.join(c['blockers']) or 'none for numeric research model'))+' |')
    for c in report['companies']:
        if c['total_score'] is None:continue
        lines.extend(['','## '+cell(c['symbol']),'','| Component | Points | Weight |','| --- | ---: | ---: |'])
        for name,r in c['components'].items():lines.append('| '+' | '.join(cell(v) for v in (name,r['score'],r['weight']))+' |')
        lines.extend(['','Valuation uses a disclosed-share scenario: 25% extra shares plus one reported precision quantum. This is a stress assumption, not an observed share count or confidence interval.',
            'Financial suitability, valuation points and observed market risk are separate. Qualitative/governance/capital-change clearance and investment approval remain absent.',''])
        for field,value in c['metrics'].items():lines.append(cell(field)+': '+cell(format(value,'.6f'))+'.')
        market=c['market_risk'];valuation=c['valuation']['indication']
        lines.extend(['',cell(market['source_url'])+' · SHA-256 '+cell(market['raw_sha256'])+'.',
            cell(c['sector_evidence']['source_url'])+' · SHA-256 '+cell(c['sector_evidence']['raw_sha256'])+'.',
            cell(valuation['disclosed_shares']['original_filing']['url'])+' · SHA-256 '+cell(valuation['disclosed_shares']['original_filing']['raw_sha256'])+'.',
            'Full per-component inputs, confirmations and first-valid trails are retained in JSON.'])
    return '\n'.join(lines)+'\n'
