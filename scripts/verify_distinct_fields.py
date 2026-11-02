"""Recorded SEC-to-original replay for separately requested accounting definitions."""
import gzip,json
from datetime import date,datetime
from decimal import Decimal
from pathlib import Path
from equity_research.companyfacts import SecCompanyFacts
from equity_research.fields import SPECS,accounting_readiness
from equity_research.models import FactQuery
from equity_research.pipeline import DeferredProvider
from equity_research.providers import Resolver
from equity_research.models import Source
from equity_research.transport import Response

root=Path(__file__).resolve().parents[1];evidence=root/'docs/evidence'
diagnostics=json.loads((evidence/'original-concept-diagnostics.json').read_text())
by_symbol={c['symbol']:c for c in diagnostics['companies']}
snapshots=json.loads((evidence/'eight-sec-snapshots.json').read_text())['sources']
by_cik={s['issuer_id']:s for s in snapshots}
selection={'NVDA':['revenue_total','productive_asset_cash_payments'],'GOOGL':['revenue_total'],
 'AMZN':['productive_asset_cash_payments'],'AVGO':['profit_loss']}
rows=[];calls=[]
for symbol,names in selection.items():
 c=by_symbol[symbol];source=by_cik[c['issuer_id']]
 response=Response(source['url'],gzip.decompress((root/source['fixture']).read_bytes()),datetime.fromisoformat(source['retrieved_at']))
 if response.sha256!=source['sha256']:raise ValueError('source checksum mismatch')
 # Replay at the actual saved observation time, not a new live retrieval label.
 clock=lambda stamp=response.retrieved_at:stamp
 class Replay:
  def __init__(self,response):self.response=response
  def get(self,url):
   if url!=self.response.url:raise AssertionError('unexpected source URL')
   calls.append(url);return self.response
 provider=SecCompanyFacts(Replay(response),clock=clock)
 from equity_research.yahoo import YahooAssets
 class NoNetwork:
  def get(self,url):raise AssertionError('unsupported or stopped provider must not query')
 def stopped():raise AssertionError('lower provider must not be created')
 resolver=Resolver([YahooAssets(NoNetwork(),directory=None,symbol=symbol,clock=clock),provider,
     DeferredProvider(Source.NASDAQ,stopped),DeferredProvider(Source.FINNHUB,stopped)],clock=clock)
 for name in names:
  spec=SPECS[name];query=FactQuery(c['issuer_id'],name,date.fromisoformat(c['period_start']),date.fromisoformat(c['period_end']),'USD','currency',spec.accounting_definition)
  result=resolver.resolve_current(query)
  original=next(r for r in c['concepts'] if r['concept']==spec.accounting_definition)
  fact=result.fact
  if fact is None or original['status']!='exact_original_value' or fact.value!=Decimal(original['value']):raise ValueError('distinct definition did not match original')
  from dataclasses import asdict
  from equity_research.cache import encode
  rows.append(dict(symbol=symbol,field=name,fact=json.loads(json.dumps(asdict(fact),default=encode)),
    attempts=json.loads(json.dumps([asdict(a) for a in result.attempts],default=encode)),
    original=original,original_source=c['source_evidence'],status='matched',
    readiness=accounting_readiness([name],{name:fact})))
report=dict(mode='ordered Yahoo unsupported then recorded SEC exact response replay at original observation; original annual comparison',
 observations=rows,summary=dict(new_distinct_facts=len(rows),original_matches=len(rows),network_requests=0),
 old_narrow_fields_filled=False,automatic_aliasing=False,sector_model_accepted=False,hundred_company_accepted=False)
(evidence/'distinct-accounting-fields.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report['summary']))
