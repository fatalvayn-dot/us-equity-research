"""Indicative capitalization from dated disclosed shares, never a live market-cap claim."""
from .turkish import label, calculation_label
import re
from dataclasses import asdict
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal, localcontext
from enum import Enum

from .companyfacts import SecCompanyFacts, companyfacts_url, FORMS
from .concept_diagnostics import Inventory
from .filing_metadata import filing_security_metadata
from .models import Fact, FactRequest, aware
from .prices import PriceFailure, parse_price, price_url
from .providers import ProviderFailure, Status
from .sec import DIRECTORY_URL
from .submissions import parse_submissions, submissions_url

POLICY_VERSION = 'disclosed-share-indication-v1'
SHARE_CONCEPT = 'dei:EntityCommonStockSharesOutstanding'
SHARE_MAX_AGE = timedelta(days=120)
SNAPSHOT_TTL = timedelta(hours=6)
COVER_DEBT_TITLE = re.compile(
    r'[0-9]+(?:\.[0-9]+)?% (?:EUR |GBP |USD )?(?:Senior )?Notes due '
    r'(?:(?:January|February|March|April|May|June|July|August|September|October|November|December) )?'
    r'20[0-9]{2}', re.I)


# These are full title shapes observed on SEC covers. A generic "Notes" label
# does not establish that an unmatched security is outside the common class.
COVER_OTHER_DEBT_TITLE = re.compile(
    r'(?:[0-9]+ [1-9][0-9]*/[1-9][0-9]*% Guaranteed Subordinated Notes due 20[0-9]{2}'
    r'|Floating Rate Notes due 20[0-9]{2}'
    r'|[0-9]+(?:\.[0-9]+)?% Fixed-to-Floating Rate Notes due '
    r'(?:January|February|March|April|May|June|July|August|September|October|November|December) '
    r'(?:[1-9]|[12][0-9]|3[01]), 20[0-9]{2})', re.I)


def _cover_debt_corroboration(title):
    if COVER_DEBT_TITLE.fullmatch(title):
        return 'cover_only_fixed_coupon_debt'
    if COVER_OTHER_DEBT_TITLE.fullmatch(title):
        return 'cover_only_explicit_debt'
    return None


class ShareIssue(str, Enum):
    STALE_COMPANYFACTS = 'stale_share_companyfacts'
    STALE_DISCLOSURE = 'stale_share_disclosure'
    CLASS_MODEL_REQUIRED = 'class_specific_share_model_required'


class ShareFailure(ProviderFailure):
    def __init__(self, issue: ShareIssue):
        self.issue = issue
        super().__init__(Status.INVALID_DATA)


def disclosed_shares(response, *, cik, as_of):
    """Latest exact DEI shares observation; no weighted-average/issued-share aliases."""
    if not aware(as_of): raise ValueError('aware cutoff required')
    _, payload = SecCompanyFacts._parse(response, cik)
    age = as_of - response.retrieved_at
    if age < timedelta(0):
        raise ProviderFailure(Status.INVALID_DATA)
    if age > SNAPSHOT_TTL:
        raise ShareFailure(ShareIssue.STALE_COMPANYFACTS)
    try:
        taxonomy=payload['facts'].get('dei', {})
        if not isinstance(taxonomy,dict):raise ValueError('DEI object required')
        concept = taxonomy.get('EntityCommonStockSharesOutstanding')
        if concept is None: return None
        if not isinstance(concept,dict) or not isinstance(concept.get('units'),dict):raise ValueError('unit arrays required')
        rows = concept['units'].get('shares')
        if rows is None:
            if concept['units']:raise ValueError('incompatible share unit')
            return None
        if not isinstance(rows, list): raise ValueError('share rows required')
        candidates=[]
        for row in rows:
            if not isinstance(row,dict):raise ValueError('share row object required')
            if row.get('form') not in FORMS: continue
            end=date.fromisoformat(row['end']);filed=date.fromisoformat(row['filed'])
            value=row['val'];accession=row['accn']
            if ('start' in row or not re.fullmatch(r'[0-9]{10}-[0-9]{2}-[0-9]{6}',accession)
                    or filed>response.retrieved_at.date()):
                raise ValueError('invalid share observation')
            available=datetime.combine(filed+timedelta(days=1),time(5),timezone.utc)
            if available<=as_of:
                # Keep the end/filed pair for chronological ordering even when
                # an old, unselected row has its dates inverted. Never silently
                # repair it or let it replace a valid newer observation.
                candidates.append(dict(value=value,end=end,filed=filed,accession=accession,
                    form=row['form'],available_at=available,chronology_valid=end<=filed))
        if not candidates:return None
        latest=max((r['end'],r['filed']) for r in candidates)
        chosen=[r for r in candidates if (r['end'],r['filed'])==latest]
        def valid_count(value):
            return (type(value) in (int,Decimal) and Decimal(value).is_finite() and value>0
                    and value==Decimal(value).to_integral_value() and Decimal(value).adjusted()<=20)
        # Select chronology before numeric validation. An invalid latest row must
        # never fall back to an older valid count. Unselected historic numeric
        # defects are quarantined, not repaired or used as current operands.
        if any(not r['chronology_valid'] for r in chosen):
            raise ValueError('invalid latest share chronology')
        if any(not valid_count(r['value']) for r in chosen):
            raise ValueError('positive bounded integral latest shares required')
        for r in chosen:r['value']=Decimal(r['value'])
        historical_review=[]
        for r in candidates:
            if (r['end'],r['filed'])==latest:continue
            if not r['chronology_valid']:
                historical_review.append(dict(end=r['end'],filed=r['filed'],accession=r['accession'],
                    status='unselected_historical_date_order_invalid'))
            if not valid_count(r['value']):
                historical_review.append(dict(end=r['end'],filed=r['filed'],accession=r['accession'],
                    status='unselected_historical_numeric_value_invalid'))
        if len({(r['value'],r['accession'],r['form']) for r in chosen})!=1:
            raise ValueError('ambiguous latest share disclosure')
        row=chosen[0]
        if not timedelta(0)<=as_of.date()-row['end']<=SHARE_MAX_AGE:
            raise ShareFailure(ShareIssue.STALE_DISCLOSURE)
        row.pop('chronology_valid')
        result=dict(**row,issuer_id=cik,concept=SHARE_CONCEPT,unit='shares',
                    source_url=response.url,raw_sha256=response.sha256,retrieved_at=response.retrieved_at)
        if historical_review:result['historical_numeric_review']=historical_review
        return result
    except (KeyError,TypeError,ValueError,ArithmeticError):
        raise ProviderFailure(Status.INVALID_DATA) from None


def _share_number(fact, inventory):
    a=fact['attrs'];unit=inventory.units.get(a.get('unitref'))
    if (not unit or unit['compound'] or [s.strip() for s in unit['measures']]!=['xbrli:shares']
            or inventory.namespaces.get('xbrli')!='http://www.xbrl.org/2003/instance'
            or a.get('xsi:nil','false').lower() in ('true','1') or fact['excluded']
            or a.get('continuedat') or a.get('sign') is not None):
        raise ValueError('exact shares unit and supported numeric presentation required')
    if a.get('format'):
        prefix,sep,local=a['format'].partition(':')
        if (not sep or local.lower() not in ('num-dot-decimal','numdotdecimal')
                or inventory.namespaces.get(prefix) not in (
                    'http://www.xbrl.org/inlineXBRL/transformation/2020-02-12',
                    'http://www.xbrl.org/inlineXBRL/transformation/2022-02-16')):
            raise ValueError('unsupported share transformation')
    text=fact['text'].strip();scale=int(a.get('scale','0'))
    if not re.fullmatch(r'(?:[0-9]+|[0-9]{1,3}(?:,[0-9]{3})+)(?:\.[0-9]+)?',text) or len(text)>100 or not -12<=scale<=12:
        raise ValueError('unsupported share number')
    decimals=a.get('decimals')
    if decimals!='INF' and (not isinstance(decimals,str) or not re.fullmatch(r'-?[0-9]{1,2}',decimals)):
        raise ValueError('reported precision required')
    if decimals!='INF' and not -12<=int(decimals)<=12:raise ValueError('unsupported reported precision')
    with localcontext() as ctx:
        ctx.prec=128;value=Decimal(text.replace(',',''))*(Decimal(10)**scale)
    if value<=0 or value!=value.to_integral_value():raise ValueError('positive integral shares required')
    return value,decimals


def verify_share_class(shares, metadata, filing, *, symbol, as_of):
    """Reparse exact original filing and reject listed or disclosed class ambiguity."""
    cik=shares['issuer_id'];snapshot=parse_submissions(metadata,cik)
    if (not timedelta(0)<=as_of-metadata.retrieved_at<=SNAPSHOT_TTL
            or symbol not in snapshot.tickers or shares['retrieved_at']>as_of
            or not aware(filing.retrieved_at) or filing.retrieved_at>as_of
            or filing.retrieved_at.date()<shares['filed']):
        raise ProviderFailure(Status.INVALID_DATA)
    from .transport import strict_json
    try:
        recent=strict_json(metadata.body)['filings']['recent']
        indexes=[i for i,a in enumerate(recent['accessionNumber']) if a==shares['accession']]
        if len(indexes)!=1:raise ValueError('share filing not in verified recent metadata')
        i=indexes[0];document=recent['primaryDocument'][i]
        report_end=date.fromisoformat(recent['reportDate'][i])
        if (recent['form'][i]!=shares['form'] or recent['filingDate'][i]!=shares['filed'].isoformat()
                or not re.fullmatch(r'[A-Za-z0-9_-][A-Za-z0-9_.-]*',document) or '..' in document):
            raise ValueError('share filing mismatch')
        url=f'https://www.sec.gov/Archives/edgar/data/{int(cik)}/{shares["accession"].replace("-", "")}/{document}'
        if filing.url!=url:raise ValueError('wrong original document')
        cover=filing_security_metadata(filing.body,cik=cik,symbol=symbol,report_end=report_end,
            document_type=shares['form'],include_all_listed=True)
        # A single listed ticker alone cannot prove that all common shares have
        # the same economics. Class-labeled covers and dimensional DEI counts
        # require a separately accepted multi-class model.
        if any(re.search(r'\bclass\s+[A-Za-z0-9]+\b',r['title'],re.I) for r in cover['registered_security']):
            raise ShareFailure(ShareIssue.CLASS_MODEL_REQUIRED)
        # SEC submissions can list a common symbol alongside preferred or debt
        # tickers. Permit that only when this exact filing cover independently
        # identifies every additional ticker as explicitly non-common and no
        # second common/ordinary security is visible. Unknown or missing cover
        # classifications remain a hard review gate.
        listed=cover['listed_security'];other=[]
        other_tickers=[ticker for ticker in snapshot.tickers if ticker!=symbol]
        other_cover=[r for r in listed if r['symbol']!=symbol]
        is_common=lambda title:re.search(r'\b(common|ordinary)\s+(stock|shares?)\b',title,re.I)
        is_explicit_non_common=lambda title:re.search(
            r'\b(preferred|depositary|depository|warrants?|units?|notes?|bonds?)\b',title,re.I)
        if any(is_common(r['title']) or not is_explicit_non_common(r['title']) for r in other_cover):
            raise ValueError('additional common or unknown security requires review')
        used=set();unmatched=[]
        for ticker in other_tickers:
            matches=[(i,r) for i,r in enumerate(other_cover) if r['symbol']==ticker]
            identities={(r['title'],r['exchange']) for _,r in matches}
            if len(identities)==1:
                title,exchange=next(iter(identities));used.update(i for i,_ in matches)
                other.append(dict(symbol=ticker,title=title,exchange=exchange,
                    symbol_corroboration='exact_cover_symbol'))
            else:unmatched.append(ticker)
        remaining=[r for i,r in enumerate(other_cover) if i not in used]
        # The cover can list explicit debt absent from submissions.
        # Preserve those exact symbols as debt evidence, without matching them
        # to any missing metadata ticker or including them in the share count.
        if remaining and not unmatched and all(
                _cover_debt_corroboration(row['title']) for row in remaining):
            debt_by_symbol = {}
            for row in remaining:
                identity = (row['title'], row['exchange'])
                prior = debt_by_symbol.setdefault(row['symbol'], identity)
                if prior != identity:
                    raise ValueError('conflicting cover-only debt identity')
            other.extend(dict(symbol=ticker, title=title, exchange=exchange,
                symbol_corroboration=_cover_debt_corroboration(title))
                for ticker, (title, exchange) in debt_by_symbol.items())
            remaining = []
        # Some SEC submissions use an exchange-style preferred ticker while the
        # filing cover uses a spaced series designator (for example ORCL-PD vs
        # ORCL PRD). Do not normalize punctuation or guess among alternatives:
        # accept only one unmatched metadata ticker and one unmatched cover row,
        # retain both exact labels, and use neither as a common-share operand.
        if unmatched or remaining:
            if len(unmatched)!=1 or len(remaining)!=1:
                raise ValueError('additional ticker lacks unambiguous cover classification')
            row=remaining[0]
            if _cover_debt_corroboration(row['title']):
                raise ValueError('explicit debt cannot explain an unmatched metadata ticker')
            other.append(dict(symbol=unmatched[0],cover_symbol=row['symbol'],title=row['title'],
                exchange=row['exchange'],symbol_corroboration='single_unambiguous_non_common_cover_alias'))
        p=Inventory();p.feed(filing.body.decode('utf-8'));p.close()
        if (p.conflict or p.context is not None or p.unit is not None or p.stack
                or not re.fullmatch(r'http://xbrl.sec.gov/dei/20[0-9]{2}',p.namespaces.get('dei',''))):
            raise ValueError('unverified original share taxonomy')
        matches=[]
        for f in p.facts:
            if f['attrs'].get('name','').lower()!=SHARE_CONCEPT.lower():continue
            c=p.contexts.get(f['attrs'].get('contextref'))
            if not c or c.get('scheme')!='http://www.sec.gov/CIK' or c.get('identifier','').strip().zfill(10)!=cik:
                raise ValueError('share issuer context mismatch')
            if c['dimensional']:raise ShareFailure(ShareIssue.CLASS_MODEL_REQUIRED)
            if c.get('instant','').strip()!=shares['end'].isoformat() or c.get('startdate'):
                raise ValueError('share instant mismatch')
            matches.append(_share_number(f,p))
        if len(set(matches))!=1 or matches[0][0]!=shares['value']:
            raise ValueError('original share disclosure does not reconcile')
        result=dict(value=shares['value'],disclosed_on=shares['end'],decimals=matches[0][1],
            unit='shares',concept=SHARE_CONCEPT,companyfacts=shares,
            original_filing=dict(url=filing.url,raw_sha256=filing.sha256,retrieved_at=filing.retrieved_at),
            metadata=dict(url=metadata.url,raw_sha256=metadata.sha256,retrieved_at=metadata.retrieved_at),
            registered_security=cover['registered_security'],scope_approved=False)
        # Keep the established single-ticker report contract byte stable. The
        # extra audit fields exist only when they are needed to prove why a
        # multi-ticker issuer's common security can be isolated.
        if other:result.update(other_registered_securities=other,
            common_security_scope='single_verified_common_symbol_with_explicit_non_common_tickers')
        return result
    except (KeyError,TypeError,ValueError,ArithmeticError,UnicodeError):
        raise ProviderFailure(Status.INVALID_DATA) from None


def indicative_valuation(*, price_response, identity, companyfacts, metadata, filing,
                         financial_company, as_of, diagnostics=None):
    """Price times *dated* disclosed shares. No corporate-action adjustment guessed.

    The resulting indication cannot feed scores until capital changes and the
    sector model are validated. Each source and each date remains visible.
    """
    def stage(name):
        if diagnostics is not None:diagnostics['validation_stage']=name
    stage('financial_batch')
    # Recompute the financial report from its field trails. A caller-supplied
    # calculation or acceptance flag is never an operand or model approval.
    import json
    from .cache import encode
    from .reporting import build_report
    normalized=json.loads(json.dumps(dict(schema_version=1,generated_at=as_of.isoformat(),companies=[dict(
        symbol=financial_company['symbol'],issuer_id=financial_company['issuer_id'],
        scope_status=financial_company.get('scope_status'),scope_reason=financial_company.get('scope_reason'),
        fields=financial_company['fields'])]),default=encode))
    financial_company=build_report(normalized)['companies'][0]
    cik=financial_company['issuer_id'];symbol=financial_company['symbol']
    stage('price')
    price=parse_price(price_response,identity,cik=cik,symbol=symbol,as_of=as_of)
    if price is None:raise ProviderFailure(Status.MISSING)
    stage('disclosed_shares')
    shares=disclosed_shares(companyfacts,cik=cik,as_of=as_of)
    if shares is None:raise ProviderFailure(Status.MISSING)
    stage('share_class')
    proof=verify_share_class(shares,metadata,filing,symbol=symbol,as_of=as_of)
    stage('share_price_chronology')
    if price.market_at.date()<shares['end'] or shares['available_at']>price.retrieved_at:
        raise ProviderFailure(Status.INVALID_DATA)
    stage('financial_period_currency')
    if (financial_company['status'] not in ('review_required',) or financial_company.get('currency')!='USD'
            or not financial_company.get('period_end')
            or as_of.date()-date.fromisoformat(financial_company['period_end'])>timedelta(days=550)):
        raise ProviderFailure(Status.INVALID_DATA)
    # Independent SEC corroboration does not replace the first selected source.
    # A later restatement/conflict must block the indication, not be averaged or
    # silently mixed with a different reporting period.
    from .fields import SPECS
    stage('sec_financial_confirmation')
    payload=SecCompanyFacts._parse(companyfacts,cik)[1];confirmation=[]
    for row in financial_company['fields']:
        field=row['query']['field']
        if field not in ('revenue','net_income','operating_cash_flow','capital_expenditure') or row['fact'] is None:continue
        selected=Fact(**row['fact'])
        request=FactRequest(cik,field,selected.period_start,selected.period_end,'USD','currency',SPECS[field].accounting_definition,as_of)
        verified=SecCompanyFacts(None)._extract(request,SPECS[field].tag,companyfacts,payload)
        if verified is None or verified.value!=selected.value:
            raise ProviderFailure(Status.INVALID_DATA)
        confirmation.append(dict(field=field,first_selected_fact=asdict(selected),sec_verification_fact=asdict(verified),matches=True))
    values=[r['fact']['value'] for r in financial_company['fields'] if r['fact']]
    magnitude=max([len(price.value.as_tuple().digits),len(shares['value'].as_tuple().digits)]+
                  [max(len(v.as_tuple().digits),abs(v.adjusted())) for v in values])
    if magnitude>1000:raise ProviderFailure(Status.INVALID_DATA)
    with localcontext() as ctx:
        ctx.prec=max(100,magnitude*2+20);capitalization=price.value*shares['value']
        if max(len(capitalization.as_tuple().digits),abs(capitalization.adjusted()))>1000:
            raise ProviderFailure(Status.INVALID_DATA)
        metrics=[]
        # These remain literal issuer-level ratios, not fair values or owner
        # earnings. Do not substitute ProfitLoss, productive-asset payments or
        # a different revenue definition when the selected operands are absent.
        for name,field in (('contract_revenue_to_indicated_cap','revenue'),
                           ('issuer_net_income_to_indicated_cap','net_income')):
            fact=next((r['fact'] for r in financial_company['fields'] if r['query']['field']==field),None)
            metrics.append(dict(metric=name,value=fact['value']/capitalization if fact else None,
                status='indicative_arithmetic_only' if fact else 'pending_data',inputs=[fact] if fact else []))
        cash=next((r for r in financial_company['calculations'] if r['calculation']=='cash_after_ppe_payments'),None)
        metrics.append(dict(metric='ocf_less_ppe_payments_to_indicated_cap',
            value=cash['value']/capitalization if cash and cash['value'] is not None else None,
            status='indicative_arithmetic_only' if cash and cash['value'] is not None else 'pending_data',
            inputs=cash['inputs'] if cash else []))
    return dict(policy_version=POLICY_VERSION,issuer_id=cik,symbol=symbol,as_of=as_of,
        status='indicative_arithmetic_only',indicated_capitalization=capitalization,currency='USD',
        formula='Yahoo regular-session USD price x original-filing-verified dated DEI common shares',
        price=asdict(price),disclosed_shares=proof,metrics=metrics,fair_value=None,
        financial_review=financial_company['financial_assessment'],
        independent_financial_confirmations=confirmation,
        share_source_evaluation=[dict(source='Yahoo',status='unsupported_field',http_requested=False),
            dict(source='SEC',status='valid',http_requested=False)],
        corporate_actions_validated=False,sector_model_supported=False,scope_approved=False,
        total_score=None,investment_approved=False,
        blockers=['capital_changes_since_share_date_unverified','sector_model_and_security_scope_pending',
                  'annual_input_not_latest_statement_confirmation'],
        limitations=['not_observed_current_market_capitalization',
                     'share_disclosure_can_be_rounded_and_up_to_120_days_old',
                     'issuer_net_income_not_common_share_earnings',
                     'ocf_less_ppe_payments_not_complete_owner_earnings'])


def build_valuation_report(batch, responses, *, as_of):
    from .reporting import build_report
    if not aware(as_of):raise ValueError('aware cutoff required')
    financial=build_report(batch)
    if len(financial['companies'])>100:raise ValueError('bounded 100-candidate valuation report required')
    if datetime.fromisoformat(financial['as_of'])>as_of:raise ValueError('future financial evidence')
    latest={}
    for response in responses:
        if not aware(response.retrieved_at):raise ValueError('aware source time required')
        if response.retrieved_at>as_of:continue
        old=latest.get(response.url)
        if old is None or response.retrieved_at>old.retrieved_at:latest[response.url]=response
        elif response.retrieved_at==old.retrieved_at and response.sha256!=old.sha256:
            raise ValueError('conflicting original observations')
    companies=[]
    for company in financial['companies']:
        cik=company['issuer_id'];symbol=company['symbol']
        row=dict(issuer_id=cik,symbol=symbol,status='pending_source_evidence',valuation=None,total_score=None)
        diagnostics={'validation_stage':'source_inventory'}
        try:
            cf=latest.get(companyfacts_url(cik));meta=latest.get(submissions_url(cik))
            required=[price_url(symbol),DIRECTORY_URL,companyfacts_url(cik),submissions_url(cik)]
            row['missing_source_urls']=[url for url in required if url not in latest]
            row['source_observations']=[dict(url=url,raw_sha256=latest[url].sha256,retrieved_at=latest[url].retrieved_at.isoformat()) for url in required if url in latest]
            if row['missing_source_urls']:companies.append(row);continue
            diagnostics['validation_stage']='disclosed_shares'
            shares=disclosed_shares(cf,cik=cik,as_of=as_of)
            if shares is None:
                row['missing_evidence']=['disclosed_shares'];companies.append(row);continue
            diagnostics['validation_stage']='original_share_filing'
            candidates=[r for url,r in latest.items() if url.startswith(f'https://www.sec.gov/Archives/edgar/data/{int(cik)}/{shares["accession"].replace("-", "")}/')]
            if len(candidates)!=1:
                if not candidates:row['missing_source_urls'].append('exact_original_share_filing')
                else:row.update(status='source_contract_rejected',provider_status='invalid_data',failure_detail='ambiguous_original_share_filing')
                row['failed_validation_stage']=diagnostics['validation_stage'];companies.append(row);continue
            row['source_observations'].append(dict(url=candidates[0].url,raw_sha256=candidates[0].sha256,retrieved_at=candidates[0].retrieved_at.isoformat()))
            row['valuation']=indicative_valuation(price_response=latest[price_url(symbol)],identity=latest[DIRECTORY_URL],
                companyfacts=cf,metadata=meta,filing=candidates[0],financial_company=company,as_of=as_of,diagnostics=diagnostics)
            row['status']='indicative_arithmetic_only'
        except ProviderFailure as exc:
            row.update(status='source_contract_rejected',provider_status=exc.status.value,failed_validation_stage=diagnostics['validation_stage'])
            if isinstance(exc,(PriceFailure,ShareFailure)):row['failure_detail']=exc.issue.value
        except (ValueError,KeyError,TypeError):
            row.update(status='source_contract_rejected',provider_status=Status.INVALID_DATA.value,failed_validation_stage=diagnostics['validation_stage'])
        companies.append(row)
    return dict(schema_version=1,policy_version=POLICY_VERSION,as_of=as_of,companies=companies,
        summary=dict(candidates=len(companies),indicative_valuations=sum(c['valuation'] is not None for c in companies),
                     rejected=sum(c['status']=='source_contract_rejected' for c in companies),
                     pending=sum(c['status']=='pending_source_evidence' for c in companies),scored_companies=0),
        new_network_requests=0,mvp_accepted=False)


def render_valuation_markdown(report):
    import html
    def cell(value):return html.escape(label(value)).replace('|','&#124;').replace('\n',' ')
    lines=['# Bildirilen hisse adedine dayalı değerleme göstergeleri','',f"Kaynak verilerinin kesim zamanı: {cell(report['as_of'])}",'',
        'İlk sürümün kabulü bekleniyor. Tarihli hisse adedine dayalı aritmetik göstergelerdir; gözlenen güncel piyasa değeri veya adil değer değildir. Puan ve sıralama yoktur.','',
        '| Sembol | Durum | Gösterge sermaye değeri (USD) | Hisse adedi bildirim tarihi |','| --- | --- | ---: | --- |']
    for c in report['companies']:
        v=c['valuation']
        lines.append('| '+' | '.join(cell(x) for x in (c['symbol'],c['status'],v['indicated_capitalization'] if v else 'unavailable',
            v['disclosed_shares']['disclosed_on'] if v else 'unavailable'))+' |')
    for c in report['companies']:
        v=c['valuation']
        lines.extend(['','## '+cell(c['symbol']),''])
        if v is None:
            lines.append('Mevcut değil: '+cell(c.get('provider_status') or '; '.join(c.get('missing_source_urls',[])))+'.');continue
        p=v['price'];s=v['disclosed_shares']
        lines.extend([f"Fiyat: {cell(p['value'])} USD, piyasa zamanı {cell(p['market_at'])}, gözlem zamanı {cell(p['retrieved_at'])}.",
            f"Bildirilen hisse adedi: {cell(s['value'])}, tarihi {cell(s['disclosed_on'])}, bildirilen ondalık hassasiyet {cell(s['decimals'])}.",
            '', '| Ölçüt | Oran | Durum |', '| --- | ---: | --- |'])
        for metric in v['metrics']:
            value=format(Decimal(str(metric['value'])),'.6f') if metric['value'] is not None else 'unavailable'
            lines.append('| '+' | '.join(cell(x) for x in (metric['metric'],value,metric['status']))+' |')
        for name,source in [('Fiyat',p),('SEC finansal verileri',s['companyfacts']),('Özgün bildirim',s['original_filing']),('Şirket bilgileri',s['metadata'])]:
            lines.extend(['',cell(name)+': '+cell(source.get('source_url') or source.get('url'))+' · SHA-256 '+cell(source['raw_sha256'])+'.'])
        lines.extend(['','Puanın hesaplanmama nedenleri: '+cell('; '.join(v['blockers']))+'.',
            'Sınırlamalar: '+cell('; '.join(v['limitations']))+'.'])
    return '\n'.join(lines)+'\n'
