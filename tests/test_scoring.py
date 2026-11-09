"""Synthetic financial and market histories; no fabricated live-success claim."""
import copy
import json
import unittest
from dataclasses import replace
from datetime import date,datetime,timedelta,timezone
from decimal import Decimal

from equity_research.cache import encode
from equity_research.companyfacts import companyfacts_url
from equity_research.market_history import history_url,parse_history
from equity_research.providers import ProviderFailure,Status
from equity_research.scoring import build_score_report
from equity_research.transport import Response
from test_valuation import NOW,CIK,batch,cf,meta,filing,identity,price

ASOF=NOW+timedelta(minutes=2)


def financial(**changes):
    values=dict(assets='1000',liabilities='400',current_assets='300',current_liabilities='100',operating_income='200')
    values.update(changes);b=batch(**values)
    for row in b['companies'][0]['fields']:
        row['fact'].update(source_url=companyfacts_url(CIK),filing_accession='0000320193-26-000001',filed_on='2026-01-15')
    return b


def comparisons(b=None):
    b=copy.deepcopy(b or financial());b['companies'][0]['fields']=[r for r in b['companies'][0]['fields'] if r['query']['field']=='revenue']
    prior=copy.deepcopy(b)
    for row in prior['companies'][0]['fields']:
        row['query'].update(period_start='2024-01-01',period_end='2024-12-31')
        row['fact'].update(period_start='2024-01-01',period_end='2024-12-31',value='800')
    return b,prior


def companyfacts(**changes):
    values=dict(assets=1000,liabilities=400,current_assets=300,current_liabilities=100,operating_income=200)
    values.update(changes);r=cf(metric_values=values);p=json.loads(r.body)
    for concept in p['facts']['us-gaap'].values():
        for row in concept['units']['USD']:
            if next(k for k,v in p['facts']['us-gaap'].items() if v is concept) in ('Assets','Liabilities','AssetsCurrent','LiabilitiesCurrent'):
                row.pop('start',None)
    rows=p['facts']['us-gaap']['RevenueFromContractWithCustomerExcludingAssessedTax']['units']['USD']
    rows.append(dict(rows[0],start='2024-01-01',end='2024-12-31',val=800))
    return replace(r,body=json.dumps(p).encode())


def metadata(sic='3571',entity='operating'):
    r=meta();p=json.loads(r.body);p.update(sic=sic,entityType=entity)
    recent=p['filings']['recent']
    for key,value in dict(accessionNumber='0000320193-26-000001',form='10-K',filingDate='2026-01-15',
                          reportDate='2025-12-31',primaryDocument='annual.htm',acceptanceDateTime='2026-01-15T16:00:00Z').items():recent[key].append(value)
    return replace(r,body=json.dumps(p).encode())


def history(*,split=False,volume=10000000):
    days=[];day=date(2025,11,3)
    while day<=NOW.date():
        if day.weekday()<5:days.append(day)
        day+=timedelta(days=1)
    stamps=[int(datetime.combine(d,datetime.min.time(),timezone.utc).timestamp())+14*3600+30*60 for d in days]
    events={}
    if split:
        stamp=int(datetime(2026,10,26,14,30,tzinfo=timezone.utc).timestamp())
        events['splits']={str(stamp):dict(date=stamp,numerator=2,denominator=1)}
    item=dict(meta=dict(symbol='AAPL',currency='USD',instrumentType='EQUITY',exchangeName='NMS',
        exchangeTimezoneName='America/New_York',dataGranularity='1d',range='1y'),timestamp=stamps,events=events,
        indicators=dict(quote=[dict(close=[10]*len(days),volume=[volume]*len(days))],adjclose=[dict(adjclose=[10]*len(days))]))
    return Response(history_url('AAPL'),json.dumps(dict(chart=dict(error=None,result=[item]))).encode(),NOW+timedelta(minutes=1))


def score(*,b=None,metadata_response=None,history_response=None,cf_response=None,filing_response=None,current=None,prior=None):
    b=b or financial();default_current,default_prior=comparisons(b)
    responses=[companyfacts() if cf_response is None else cf_response,metadata_response or metadata(),filing_response or filing(),identity(),price(),history_response or history()]
    return build_score_report(b,current or default_current,prior or default_prior,responses,as_of=ASOF)


class MarketHistoryTests(unittest.TestCase):
    def test_completed_sessions_and_exact_zero_volatility_are_real_values(self):
        r=parse_history(history(),identity(),cik=CIK,symbol='AAPL',share_date=date(2026,10,20),price_market_at=NOW,as_of=ASOF)
        self.assertEqual(r['annualized_sample_volatility'],Decimal(0));self.assertEqual(r['median_63_session_close_times_volume'],Decimal(100000000))
        self.assertLess(r['last_session'].date(),NOW.date());self.assertFalse(r['capital_changes_fully_verified'])

    def test_split_window_detected_without_guessing_adjusted_share_count(self):
        r=parse_history(history(split=True),identity(),cik=CIK,symbol='AAPL',share_date=date(2026,10,20),price_market_at=NOW,as_of=ASOF)
        self.assertEqual(r['split_window_status'],'split_event_requires_review');self.assertEqual(len(r['split_events']),1)

    def test_wrong_currency_symbol_nulls_and_column_drift_rejected(self):
        for mode in ('currency','symbol','null','drift','future'):
            r=history();p=json.loads(r.body);item=p['chart']['result'][0]
            if mode in ('currency','symbol'):item['meta'][mode]='EUR' if mode=='currency' else 'MSFT'
            elif mode=='null':item['indicators']['adjclose'][0]['adjclose'][10]=None
            elif mode=='drift':item['indicators']['quote'][0]['volume'].pop()
            else:item['timestamp'][-1]=int((ASOF+timedelta(days=1)).timestamp())
            with self.subTest(mode=mode),self.assertRaises(ProviderFailure):parse_history(replace(r,body=json.dumps(p).encode()),identity(),cik=CIK,symbol='AAPL',share_date=date(2026,10,20),price_market_at=NOW,as_of=ASOF)

    def test_stale_response_or_insufficient_calendar_window_rejected(self):
        with self.assertRaises(ProviderFailure):parse_history(history(),identity(),cik=CIK,symbol='AAPL',share_date=date(2026,10,20),price_market_at=NOW,as_of=ASOF+timedelta(minutes=16))
        r=history();p=json.loads(r.body);item=p['chart']['result'][0]
        item['timestamp']=item['timestamp'][-200:]
        for data in (item['indicators']['quote'][0],item['indicators']['adjclose'][0]):
            for k in data:data[k]=data[k][-200:]
        with self.assertRaises(ProviderFailure):parse_history(replace(r,body=json.dumps(p).encode()),identity(),cik=CIK,symbol='AAPL',share_date=date(2026,10,20),price_market_at=NOW,as_of=ASOF)

    def test_provider_quota_and_access_errors_are_distinct_from_missing_history(self):
        for code,status in [('Unauthorized',Status.ACCESS_DENIED),('Too Many Requests',Status.RATE_LIMIT)]:
            r=replace(history(),body=json.dumps(dict(chart=dict(error=dict(code=code),result=None))).encode())
            with self.assertRaises(ProviderFailure) as context:parse_history(r,identity(),cik=CIK,symbol='AAPL',share_date=date(2026,10,20),price_market_at=NOW,as_of=ASOF)
            self.assertEqual(context.exception.status,status)


class ScoringTests(unittest.TestCase):
    def test_complete_verified_model_has_six_explained_components_and_no_investment_approval(self):
        r=score();c=r['companies'][0]
        self.assertEqual(c['status'],'scored_research_hypothesis')
        self.assertEqual(c['total_score'],Decimal('87.5'))
        self.assertEqual(sum(p['score'] for p in c['components'].values()),c['total_score'])
        self.assertEqual(sum(p['weight'] for p in c['components'].values()),100)
        self.assertFalse(c['investment_approved']);self.assertFalse(r['mvp_accepted'])
        self.assertEqual(c['rank'],1);self.assertEqual(len(c['evidence']['financial_confirmations']),9)

    def test_software_uses_its_declared_margin_thresholds(self):
        c=score(metadata_response=metadata(sic='7372'))['companies'][0]
        self.assertEqual(c['components']['profitability']['score'],Decimal(10))
        self.assertEqual(c['model_id'],'prepackaged_software_v1')

    def test_financial_reit_bdc_unknown_and_nonoperating_routes_never_scored(self):
        for sic,entity in [('6021','operating'),('6798','operating'),('6770','operating'),(None,'operating'),('9999','operating'),('3571','investment')]:
            c=score(metadata_response=metadata(sic=sic,entity=entity))['companies'][0]
            self.assertIsNone(c['total_score']);self.assertFalse(c['model_scope_eligible'])
            self.assertTrue(all(p['score'] is None for p in c['components'].values()))

    def test_unsupported_sec_sector_precedes_missing_market_valuation(self):
        # This issuer has an observed SEC SIC but no price, history or
        # original share filing. It must not consume the modeled valuation
        # repair queue when no supported sector model exists.
        for sic in ('6021','6798','9999'):
            with self.subTest(sic=sic):
                report=build_score_report(financial(),*comparisons(),
                    [companyfacts(),metadata(sic=sic),identity()],as_of=ASOF)
                row=report['companies'][0]
                self.assertEqual(row['blockers'],['specialized_or_unmodeled_sector'])
                self.assertIsNone(row['total_score'])
                self.assertFalse(row['model_scope_eligible'])
                self.assertEqual(row['sector_evidence']['sic'],sic)
                self.assertFalse(row['investment_approved'])

    def test_supported_sec_sector_with_missing_market_stays_unscored(self):
        report=build_score_report(financial(),*comparisons(),
            [companyfacts(),metadata(sic='3571'),identity()],as_of=ASOF)
        row=report['companies'][0]
        self.assertEqual(row['blockers'],['valuation_source_evidence_required'])
        self.assertIsNone(row['total_score'])
        self.assertFalse(report['mvp_accepted'])

    def test_no_metadata_never_implies_unsupported_sector(self):
        report=build_score_report(financial(),*comparisons(),
            [companyfacts(),identity()],as_of=ASOF)
        row=report['companies'][0]
        self.assertEqual(row['blockers'],['valuation_source_evidence_required'])
        self.assertNotIn('sector_evidence',row)

    def test_critical_deficit_overrides_favorable_other_inputs_and_injected_points(self):
        b=financial(liabilities='1001');b['companies'][0].update(total_score=100,investment_approved=True)
        c=score(b=b)['companies'][0]
        self.assertEqual(c['status'],'critical_review_required');self.assertIsNone(c['total_score'])
        self.assertIsNone(c['rank']);self.assertFalse(c['investment_approved'])

    def test_missing_field_is_not_zero_filled_even_when_sec_has_a_value(self):
        c=score(b=financial(capital_expenditure=None))['companies'][0]
        self.assertIsNone(c['total_score']);self.assertIn('capital_expenditure',c['missing_fields'])

    def test_split_and_low_dollar_volume_block_total_not_just_subtract_points(self):
        c=score(history_response=history(split=True))['companies'][0]
        self.assertIsNone(c['total_score']);self.assertIn('split_since_disclosed_count_requires_review',c['blockers'])
        c=score(history_response=history(volume=10))['companies'][0]
        self.assertIsNone(c['total_score']);self.assertIn('insufficient_observed_trading_liquidity',c['blockers'])
        h=history();payload=json.loads(h.body);payload['chart']['result'][0]['indicators']['quote'][0]['close'][-1]=1000
        c=score(history_response=replace(h,body=json.dumps(payload).encode()))['companies'][0]
        self.assertIsNone(c['total_score']);self.assertIn('quote_history_price_disagreement_requires_review',c['blockers'])

    def test_fresh_sec_conflict_and_wrong_growth_context_block_total(self):
        c=score(cf_response=companyfacts(assets=1001))['companies'][0]
        self.assertIsNone(c['total_score']);self.assertEqual(c['status'],'evidence_rejected')
        current,prior=comparisons();current['companies'][0]['fields'][0]['fact']['value']='1001'
        c=score(current=current,prior=prior)['companies'][0]
        self.assertIsNone(c['total_score']);self.assertIn('growth_current_period_or_definition_conflict',c['blockers'])

    def test_stress_is_an_explicit_assumption_not_an_observed_count(self):
        c=score()['companies'][0];v=c['valuation']
        self.assertEqual(v['assumed_share_count_uplift'],Decimal('.25'))
        self.assertEqual(v['stressed_capitalization'],Decimal('1262.50'))
        self.assertEqual(v['indication']['disclosed_shares']['value'],Decimal(100))
        self.assertFalse(v['indication']['corporate_actions_validated'])

    def test_net_loss_is_visible_in_risk_even_with_positive_operating_cash(self):
        c=score(b=financial(net_income='-100'),cf_response=companyfacts(net_income=-100))['companies'][0]
        self.assertEqual(c['components']['risk']['score'],Decimal(8))
        self.assertEqual(c['components']['risk']['basis']['net_loss_penalty'],Decimal(2))

    def test_nonpositive_prior_growth_base_and_absent_history_cannot_receive_total(self):
        current,prior=comparisons();prior['companies'][0]['fields'][0]['fact']['value']='0'
        c=score(current=current,prior=prior)['companies'][0]
        self.assertIsNone(c['total_score']);self.assertIn('comparable_revenue_required',c['blockers'])
        r=build_score_report(financial(),*comparisons(),[companyfacts(),metadata(),filing(),identity(),price()],as_of=ASOF)
        self.assertIsNone(r['companies'][0]['total_score']);self.assertIn('market_history_required',r['companies'][0]['blockers'])

    def test_explicit_bdc_fund_or_shell_overrides_apparently_eligible_technology_sic(self):
        for concept,text in [('cef:BusinessDevelopmentCompanyFlag','true'),('dei:EntityInvCompanyType','N-2'),('dei:EntityShellCompany','true')]:
            doc=filing(extra=f'<ix:nonNumeric name="{concept}" contextRef="cover">{text}</ix:nonNumeric>')
            doc=replace(doc,body=doc.body.replace(b'<html ',b'<html xmlns:cef="http://xbrl.sec.gov/cef/2026" '))
            c=score(filing_response=doc)['companies'][0]
            self.assertIsNone(c['total_score']);self.assertIn('fund_bdc_or_shell_disclosure_requires_specialized_review',c['blockers'])


if __name__=='__main__':unittest.main()
