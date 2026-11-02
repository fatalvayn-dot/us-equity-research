"""Sourced daily-history risk measures and observed split-window checks."""
from datetime import date,datetime,timedelta,timezone
from decimal import Decimal,localcontext
from statistics import median

from .models import aware
from .prices import _identity,EXCHANGES,IDENTITY_TTL,PRICE_TTL,price_url
from .providers import ProviderFailure,Status
from .transport import strict_json


def history_url(symbol):
    return price_url(symbol).split('?')[0]+'?interval=1d&range=1y&events=div%2Csplits'


def parse_history(response,identity,*,cik,symbol,share_date,price_market_at,as_of):
    """No missing-bar interpolation; exclude the quote's possibly unfinished day.

    No split record means only that this returned window contains none. It does
    not establish absence of issuance, repurchases or every capital action.
    """
    if type(share_date) is not date or not aware(as_of) or not aware(price_market_at):
        raise ValueError('exact share date and aware quote/cutoff required')
    entry=_identity(identity,cik,symbol,as_of,IDENTITY_TTL)
    if (response.url!=history_url(symbol) or not aware(response.retrieved_at)
            or not timedelta(0)<=as_of-response.retrieved_at<=PRICE_TTL
            or response.retrieved_at<price_market_at or share_date>price_market_at.date()):
        raise ProviderFailure(Status.INVALID_DATA)
    payload=strict_json(response.body)
    try:
        chart=payload['chart']
        if chart.get('error') is not None:
            error=chart['error'];code=error.get('code','') if isinstance(error,dict) else ''
            if not isinstance(code,str):raise ValueError('invalid provider error code')
            code=code.lower()
            raise ProviderFailure(Status.ACCESS_DENIED if code in ('unauthorized','forbidden') else
                Status.RATE_LIMIT if code in ('too many requests','ratelimit') else Status.API_ERROR)
        if len(chart['result'])!=1:raise ValueError('one exact chart required')
        item=chart['result'][0];meta=item['meta']
        if meta['symbol']!=symbol:raise ProviderFailure(Status.SYMBOL_MISMATCH)
        if (meta['currency']!='USD' or meta['instrumentType']!='EQUITY'
                or meta.get('dataGranularity')!='1d' or meta.get('range')!='1y'
                or meta.get('exchangeTimezoneName')!='America/New_York'
                or EXCHANGES.get(meta['exchangeName'])!=entry.exchange_label):
            raise ValueError('wrong history instrument/unit/window')
        timestamps=item['timestamp'];quotes=item['indicators']['quote'];adjusted=item['indicators']['adjclose']
        if len(quotes)!=1 or len(adjusted)!=1 or not isinstance(timestamps,list) or not 200<=len(timestamps)<=400:
            raise ValueError('bounded full-year daily history required')
        close=quotes[0]['close'];volume=quotes[0]['volume'];adj=adjusted[0]['adjclose']
        if any(not isinstance(x,list) or len(x)!=len(timestamps) for x in (close,volume,adj)):
            raise ValueError('history column drift')
        rows=[];previous=None
        for stamp,c,v,a in zip(timestamps,close,volume,adj):
            if type(stamp) is not int:raise ValueError('epoch integer required')
            at=datetime.fromtimestamp(stamp,timezone.utc)
            if at>response.retrieved_at or (previous is not None and (at<=previous or at-previous>timedelta(days=10))):
                raise ValueError('future, unordered or gapped daily history')
            previous=at
            if (type(c) not in (int,Decimal) or type(a) not in (int,Decimal) or type(v) is not int or v<0):
                raise ValueError('literal complete numeric daily data required')
            c,a=Decimal(c),Decimal(a)
            if any(not x.is_finite() or x<=0 or max(len(x.as_tuple().digits),abs(x.adjusted()))>100 for x in (c,a)) or v>10**20:
                raise ValueError('positive bounded prices required')
            rows.append((at,c,v,a))
        if (rows[0][0].date()>share_date or rows[-1][0].date()<price_market_at.date()
                or (rows[-1][0]-rows[0][0]).days<300):
            raise ValueError('share-to-quote/full-year coverage incomplete')
        completed=[r for r in rows if r[0].date()<price_market_at.date()]
        if len(completed)<200 or price_market_at.date()-completed[-1][0].date()>timedelta(days=4):
            raise ValueError('complete recent sessions required')
        events=item.get('events',{})
        if not isinstance(events,dict) or not isinstance(events.get('splits',{}),dict):raise ValueError('invalid events')
        splits=[]
        for key,event in events.get('splits',{}).items():
            stamp=event['date'];n,d=event['numerator'],event['denominator']
            if type(stamp) is not int or str(stamp)!=key or type(n) not in (int,Decimal) or type(d) not in (int,Decimal):
                raise ValueError('invalid split')
            at=datetime.fromtimestamp(stamp,timezone.utc)
            if at>response.retrieved_at or n<=0 or d<=0:raise ValueError('invalid split chronology/ratio')
            if share_date<=at.date()<=price_market_at.date():splits.append(dict(date=at,numerator=n,denominator=d))
        with localcontext() as ctx:
            ctx.prec=80
            returns=[completed[i][3]/completed[i-1][3]-1 for i in range(1,len(completed))]
            mean=sum(returns)/len(returns)
            variance=sum((r-mean)**2 for r in returns)/(len(returns)-1)
            volatility=(Decimal(252)*variance).sqrt()
            dollar_volume=median([r[1]*r[2] for r in completed[-63:]])
        return dict(issuer_id=cik,symbol=symbol,source_url=response.url,raw_sha256=response.sha256,
            retrieved_at=response.retrieved_at,currency='USD',observations=len(rows),completed_sessions=len(completed),
            latest_daily_close=rows[-1][1],latest_daily_observed_at=rows[-1][0],
            first_session=completed[0][0],last_session=completed[-1][0],quote_day_excluded=price_market_at.date(),
            annualized_sample_volatility=volatility,median_63_session_close_times_volume=dollar_volume,
            volatility_definition='sample standard deviation of adjacent Yahoo adjusted-close simple returns x sqrt(252)',
            liquidity_definition='median of Yahoo close x reported volume, last 63 completed sessions',
            split_window_status='split_event_requires_review' if splits else 'no_split_record_in_returned_window',
            split_events=splits,capital_changes_fully_verified=False,
            limitations=['daily_quote_session_excluded_even_if_completed','not_forecast_volatility',
                'absence_of_split_record_is_not_all_capital_changes_clearance'])
    except (KeyError,TypeError,ValueError,ArithmeticError,OverflowError,OSError):
        raise ProviderFailure(Status.INVALID_DATA) from None
