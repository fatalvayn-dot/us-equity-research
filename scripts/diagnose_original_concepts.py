"""Replay original annual concepts without mapping alternate accounting scopes."""
import gzip,json
from datetime import date
from decimal import Decimal
from pathlib import Path
from equity_research.concept_diagnostics import inspect_concepts
from equity_research.companyfacts import TAGS
root=Path(__file__).resolve().parents[1];evidence=root/'docs/evidence'
documents={r['symbol']:r for r in json.loads((evidence/'annual-document-resume.json').read_text())['companies'] if 'period' in r}
financial=json.loads((evidence/'archived-eight-financial.json').read_text())['companies']
results=[];checks=[]
for c in financial:
 d=documents[c['symbol']];e=d['source_evidence'];body=gzip.decompress((root/e['fixture']).read_bytes());period=d['period']
 concepts=['us-gaap:'+tag for tag,instant in TAGS.values() if not instant]
 concepts=list(dict.fromkeys(concepts+['us-gaap:Revenues','us-gaap:ProfitLoss','us-gaap:PaymentsToAcquireProductiveAssets']))
 diagnostic=inspect_concepts(body,cik=c['issuer_id'],concepts=concepts,period_start=date.fromisoformat(period['period_start']),period_end=date.fromisoformat(period['period_end']))
 if diagnostic['raw_sha256']!=e['sha256']:raise ValueError('original evidence differs')
 diagnostic.update(symbol=c['symbol'],source_evidence=e);results.append(diagnostic)
 lookup={x['concept']:x for x in diagnostic['concepts']}
 for f in c['fields']:
  q=f['query']
  if q['period_start'] is None:continue
  original=lookup[q['accounting_definition']];fact=f['fact']
  status='missing_collected_fact' if fact is None else 'original_unresolved' if original['value'] is None else 'matched' if Decimal(fact['value'])==Decimal(original['value']) else 'mismatch'
  checks.append(dict(symbol=c['symbol'],field=q['field'],accounting_definition=q['accounting_definition'],status=status,
    collected_value=fact['value'] if fact else None,original=original))
# A transparent accounting-identity candidate, never a direct Liabilities fact.
amzn=documents['AMZN'];body=gzip.decompress((root/amzn['source_evidence']['fixture']).read_bytes())
identity=inspect_concepts(body,cik=amzn['issuer_id'],concepts=['us-gaap:Liabilities','us-gaap:LiabilitiesAndStockholdersEquity','us-gaap:StockholdersEquity'],
 period_start=None,period_end=date.fromisoformat(amzn['period']['period_end']))
values={r['concept']:r['value'] for r in identity['concepts']}
if values['us-gaap:LiabilitiesAndStockholdersEquity'] is not None and values['us-gaap:StockholdersEquity'] is not None:
 identity['arithmetic_candidate']=dict(formula='LiabilitiesAndStockholdersEquity - StockholdersEquity',value=str(Decimal(values['us-gaap:LiabilitiesAndStockholdersEquity'])-Decimal(values['us-gaap:StockholdersEquity'])),
    status='candidate_only_requires_scope_and_mezzanine_review',accepted_as_liabilities=False)
identity['source_evidence']=amzn['source_evidence']
report=dict(companies=results,duration_checks=checks,amzn_identity_diagnostic=identity,
 summary=dict(duration_checks=len(checks),matched=sum(c['status']=='matched' for c in checks),missing_collected=sum(c['status']=='missing_collected_fact' for c in checks),unresolved=sum(c['status']=='original_unresolved' for c in checks),mismatched=sum(c['status']=='mismatch' for c in checks)),
 new_network_requests=0,automatic_substitution=False,hundred_company_accepted=False)
(evidence/'original-concept-diagnostics.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report['summary']))
for c in results:
 if c['symbol'] in ('NVDA','GOOGL','AMZN','AVGO'):print(c['symbol'],[(r['concept'],r['status'],r['value']) for r in c['concepts']])
print('AMZN identity',identity.get('arithmetic_candidate'))
