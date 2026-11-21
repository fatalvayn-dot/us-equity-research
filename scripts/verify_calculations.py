"""Recorded real input arithmetic; never live/model/backtest acceptance."""
import json
from datetime import date,datetime
from pathlib import Path
from equity_research.cache import decode_fact,encode
from equity_research.calculations import CALCULATIONS,calculate

root=Path(__file__).resolve().parents[1];evidence=root/'docs/evidence'
base=json.loads((evidence/'archived-eight-financial.json').read_text())
extra=json.loads((evidence/'distinct-accounting-fields.json').read_text())
supplement={}
for row in extra['observations']:supplement.setdefault(row['symbol'],{})[row['field']]=decode_fact(row['fact'])
results=[]
for c in base['companies']:
 facts={f['fact']['field']:decode_fact(f['fact']) for f in c['fields'] if f['fact']}
 facts.update(supplement.get(c['symbol'],{}))
 query=c['fields'][0]['query']
 cutoff=max(max(f.retrieved_at,f.available_at) for f in facts.values())
 for name in CALCULATIONS:
  result=calculate(name,facts,issuer_id=c['issuer_id'],period_start=date.fromisoformat(query['period_start']),
      period_end=date.fromisoformat(query['period_end']),currency='USD',as_of=cutoff)
  results.append(dict(symbol=c['symbol'],**result))
report=dict(mode='offline arithmetic from recorded exact facts; cutoff covers original observations, not a historical vintage claim',
 calculations=results,summary=dict(requested=len(results),calculated=sum(r['status']=='calculated_arithmetic_only' for r in results),pending=sum(r['status']=='pending_data' for r in results)),
 new_network_requests=0,sector_model_accepted=False,investment_score_produced=False,hundred_company_accepted=False)
(evidence/'calculation-sample.json').write_text(json.dumps(report,default=encode,indent=2)+'\n');print(json.dumps(report['summary']))
