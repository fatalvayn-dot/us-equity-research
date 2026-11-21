"""Independent narrow original iXBRL Assets/Liabilities check for collected sample."""
import gzip,json
from datetime import date
from decimal import Decimal
from pathlib import Path
from equity_research.filingcheck import filing_instant
from equity_research.providers import ProviderFailure

root=Path(__file__).resolve().parents[1];evidence=root/'docs/evidence'
source=json.loads((evidence/'annual-document-resume.json').read_text())['companies']
by_symbol={c['symbol']:c for c in source if 'source_evidence' in c}
financial=json.loads((evidence/'archived-eight-financial.json').read_text())['companies']
results=[]
for company in financial:
 document=by_symbol[company['symbol']];e=document['source_evidence'];body=gzip.decompress((root/e['fixture']).read_bytes())
 for field in company['fields']:
  fact=field['fact']
  if fact is None or fact['field'] not in ('assets','liabilities'):continue
  result=dict(symbol=company['symbol'],field=fact['field'],period_end=fact['period_end'],collected_value=fact['value'],financial_source=fact['source'],original_source=e)
  try:
   value=filing_instant(body,cik=company['issuer_id'],period_end=date.fromisoformat(fact['period_end']),concept='Assets' if fact['field']=='assets' else 'Liabilities')
   result.update(original_value=str(value),status='matched' if value==Decimal(fact['value']) else 'mismatch')
  except ProviderFailure as exc:result.update(status=exc.status.value)
  results.append(result)
report=dict(checks=results,summary=dict(checks=len(results),matched=sum(r['status']=='matched' for r in results),unresolved=sum(r['status']!='matched' for r in results)),
    scope_approved=False,hundred_company_accepted=False,validation_scope='Only Assets/Liabilities; no income/cash-flow/valuation or legal-type acceptance')
(evidence/'eight-original-balances.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report['summary']))
