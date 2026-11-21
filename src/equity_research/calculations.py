"""Traceable arithmetic only; no sector valuation, investment score or approval."""
import re
from dataclasses import asdict,dataclass
from datetime import date
from decimal import Decimal,localcontext
from types import MappingProxyType

from .fields import SPECS
from .models import Fact,FactRequest,aware

@dataclass(frozen=True)
class CalculationSpec:
    name: str
    fields: tuple[str,str]
    operation: str
    description: str

CALCULATIONS=MappingProxyType({s.name:s for s in (
    CalculationSpec('net_margin_contract_revenue',('net_income','revenue'),'divide','NetIncomeLoss / contract revenue excluding assessed tax'),
    CalculationSpec('net_margin_total_revenue',('net_income','revenue_total'),'divide','NetIncomeLoss / literal Revenues'),
    CalculationSpec('profit_loss_margin_contract_revenue',('profit_loss','revenue'),'divide','ProfitLoss / contract revenue excluding assessed tax; common-share attribution not established'),
    CalculationSpec('profit_loss_margin_total_revenue',('profit_loss','revenue_total'),'divide','ProfitLoss / literal Revenues; common-share attribution not established'),
    CalculationSpec('ocf_margin_contract_revenue',('operating_cash_flow','revenue'),'divide','Operating cash flow / contract revenue excluding assessed tax'),
    CalculationSpec('ocf_margin_total_revenue',('operating_cash_flow','revenue_total'),'divide','Operating cash flow / literal Revenues'),
    CalculationSpec('cash_after_ppe_payments',('operating_cash_flow','capital_expenditure'),'subtract','Operating cash flow less PP&E payments; not a complete owner-earnings measure'),
    CalculationSpec('cash_after_productive_asset_payments',('operating_cash_flow','productive_asset_cash_payments'),'subtract','Operating cash flow less literal ProductiveAssets payments; not a PP&E-only measure'),
    CalculationSpec('current_ratio',('current_assets','current_liabilities'),'divide','AssetsCurrent / LiabilitiesCurrent; classified balance-sheet liquidity ratio'),
    CalculationSpec('cash_equivalents_to_current_liabilities',('cash_equivalents','current_liabilities'),'divide','CashAndCashEquivalentsAtCarryingValue / LiabilitiesCurrent; investments not included'),
    CalculationSpec('working_capital',('current_assets','current_liabilities'),'subtract_balances','AssetsCurrent - LiabilitiesCurrent; negative result is not by itself insolvency evidence'),
    CalculationSpec('operating_margin_contract_revenue',('operating_income','revenue'),'divide','OperatingIncomeLoss / contract revenue excluding assessed tax'),
    CalculationSpec('operating_margin_total_revenue',('operating_income','revenue_total'),'divide','OperatingIncomeLoss / literal Revenues'),
    CalculationSpec('gross_margin_contract_revenue',('gross_profit','revenue'),'divide','GrossProfit / contract revenue excluding assessed tax'),
    CalculationSpec('gross_margin_total_revenue',('gross_profit','revenue_total'),'divide','GrossProfit / literal Revenues'),
)})


def calculate(name,facts,*,issuer_id,period_start,period_end,currency,as_of):
    if name not in CALCULATIONS:raise ValueError('explicit registered calculation required')
    spec=CALCULATIONS[name]
    duration=any(not SPECS[field].instant for field in spec.fields)
    if (not aware(as_of) or type(period_end) is not date
            or (period_start is not None and (type(period_start) is not date or not period_start<period_end))
            or (duration and period_start is None)):
        raise ValueError('explicit aware cutoff and exact required period needed')
    if not isinstance(issuer_id,str) or not re.fullmatch(r'[0-9]{10}',issuer_id) or int(issuer_id)==0 or not isinstance(currency,str) or not re.fullmatch('[A-Z]{3}',currency):raise ValueError('explicit canonical issuer/currency required')
    result=dict(calculation=name,formula=spec.description,issuer_id=issuer_id,period_start=period_start.isoformat() if duration else None,
        period_end=period_end.isoformat(),currency=None if spec.operation=='divide' else currency,input_currency=currency,as_of=as_of.isoformat(),value=None,
        unit='ratio' if spec.operation=='divide' else 'currency',inputs=[],missing_fields=[],rejections=[],
        semantic_review_fields=[field for field in spec.fields if SPECS[field].requires_semantic_model_review],
        sector_model_supported=False,scope_approved=False,investment_approved=False)
    for field in spec.fields:
        definition=SPECS[field]
        request=FactRequest(issuer_id,field,None if definition.instant else period_start,period_end,currency,'currency',definition.accounting_definition,as_of)
        fact=facts.get(field)
        if fact is None:result['missing_fields'].append(field);continue
        if not isinstance(fact,Fact):result['rejections'].append(dict(field=field,reason='invalid_fact_type'));continue
        reason=request.rejection(fact)
        if reason:result['rejections'].append(dict(field=field,reason=reason));continue
        if fact.raw_sha256 is None:result['rejections'].append(dict(field=field,reason='missing_raw_source_hash'));continue
        result['inputs'].append(asdict(fact))
    if result['rejections']:result['status']='invalid_inputs';return result
    if result['missing_fields']:result['status']='pending_data';return result
    first,second=(facts[field].value for field in spec.fields)
    if any(SPECS[field].instant and facts[field].value<0 for field in spec.fields):
        result['status']='unsupported_balance_sign';return result
    if spec.operation=='divide' and second<=0:
        result['status']='nonpositive_denominator';return result
    if spec.operation=='subtract' and second<0:
        result['status']='unsupported_payment_sign';return result
    # Bound adversarial magnitude and keep enough precision for exact subtraction.
    magnitude=max(max(len(v.as_tuple().digits),abs(v.adjusted())) for v in (first,second))
    if magnitude>1000:result['status']='unsupported_magnitude';return result
    with localcontext() as ctx:
        ctx.prec=max(50,magnitude*2+20)
        value=first/second if spec.operation=='divide' else first-second
    result.update(status='calculated_arithmetic_only',value=value)
    return result
