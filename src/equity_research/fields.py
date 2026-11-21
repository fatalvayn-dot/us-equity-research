"""Literal accounting specifications, never aliases between financial scopes."""
from dataclasses import dataclass
from types import MappingProxyType

@dataclass(frozen=True)
class FieldSpec:
    name: str
    tag: str
    instant: bool
    scope_note: str
    requires_semantic_model_review: bool=False

    @property
    def accounting_definition(self):return 'us-gaap:'+self.tag

SPECS=MappingProxyType({s.name:s for s in (
    FieldSpec('revenue','RevenueFromContractWithCustomerExcludingAssessedTax',False,'Exact contract revenue excluding assessed tax concept.'),
    FieldSpec('assets','Assets',True,'Exact Assets concept.'),
    FieldSpec('liabilities','Liabilities',True,'Exact Liabilities concept; no balance identity inferred.'),
    FieldSpec('net_income','NetIncomeLoss',False,'Exact NetIncomeLoss concept.'),
    FieldSpec('operating_cash_flow','NetCashProvidedByUsedInOperatingActivities',False,'Exact operating activities cash-flow concept.'),
    FieldSpec('capital_expenditure','PaymentsToAcquirePropertyPlantAndEquipment',False,'Exact PP&E payments concept.'),
    FieldSpec('revenue_total','Revenues',False,'Literal Revenues disclosure; not an alias for contract revenue excluding assessed tax.',True),
    FieldSpec('profit_loss','ProfitLoss',False,'Literal ProfitLoss disclosure; attribution scope must be reviewed before common-share analysis.',True),
    FieldSpec('productive_asset_cash_payments','PaymentsToAcquireProductiveAssets',False,'Literal ProductiveAssets cash payments; not PP&E-only capex.',True),
    FieldSpec('current_assets','AssetsCurrent',True,'Literal classified current assets; not total assets.'),
    FieldSpec('current_liabilities','LiabilitiesCurrent',True,'Literal classified current liabilities; not total liabilities or financial debt.'),
    FieldSpec('cash_equivalents','CashAndCashEquivalentsAtCarryingValue',True,'Literal cash and cash equivalents carrying value; no investments/restricted-cash aggregation.'),
    FieldSpec('operating_income','OperatingIncomeLoss',False,'Literal operating income/loss; not net income or EBIT inferred by adding interest.'),
    FieldSpec('gross_profit','GrossProfit',False,'Literal gross profit; no alternate cost/revenue concepts subtracted.'),
)})
TAGS=MappingProxyType({name:(spec.tag,spec.instant) for name,spec in SPECS.items()})


def accounting_readiness(required_fields,facts):
    """Exact inputs only; completeness never constitutes a validated sector model."""
    required=tuple(required_fields)
    if not required or len(set(required))!=len(required) or any(name not in SPECS for name in required):
        raise ValueError('distinct registered required fields needed')
    missing=[];mismatched=[];review=[];contexts=set();starts=set()
    for name in required:
        fact=facts.get(name);spec=SPECS[name]
        if fact is None:missing.append(name)
        elif (fact.field!=name or fact.accounting_definition!=spec.accounting_definition
              or fact.unit!='currency' or spec.instant!=(fact.period_start is None)):mismatched.append(name)
        else:
            contexts.add((fact.issuer_id,fact.period_end,fact.currency,fact.unit))
            if fact.period_start is not None:starts.add(fact.period_start)
        if spec.requires_semantic_model_review:review.append(name)
    context_conflict=len(contexts)>1 or len(starts)>1
    return dict(status='pending_data' if missing else 'invalid_accounting_definition' if mismatched else 'incompatible_fact_context' if context_conflict else 'data_complete_model_validation_pending',
        missing_fields=missing,definition_mismatches=mismatched,context_conflict=context_conflict,semantic_model_review_fields=review,
        sector_model_supported=False,investment_approved=False)
