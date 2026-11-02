# US Equity Research

Evidence cutoff: 2026-11-02T03:39:58.089302+00:00

MVP acceptance: pending. Unavailable scores are not zero and companies remain unranked.

| Symbol | CIK | Period end | Accepted facts | Arithmetic results | Status | Score / 100 |
| --- | --- | --- | ---: | ---: | --- | --- |
| NVDA | 0001045810 | 2026-01-25 | 4 | 0 | review_required | unavailable |
| AAPL | 0000320193 | 2025-09-27 | 6 | 3 | review_required | unavailable |
| MSFT | 0000789019 | 2026-06-30 | 6 | 3 | review_required | unavailable |
| GOOGL | 0001652044 | 2025-12-31 | 5 | 1 | review_required | unavailable |
| AMZN | 0001018724 | 2025-12-31 | 5 | 2 | review_required | unavailable |
| AVGO | 0001730168 | 2025-11-02 | 5 | 2 | review_required | unavailable |
| META | 0001326801 | 2025-12-31 | 6 | 3 | review_required | unavailable |
| TSLA | 0001318605 | 2025-12-31 | 6 | 3 | review_required | unavailable |

## NVDA

Scope: fund_legal_type_and_sector_model_not_accepted

| Field | Value and currency | Source | Period | Definition | Raw SHA-256 | Observed at | Attempts |
| --- | --- | --- | --- | --- | --- | --- | --- |
| revenue | unavailable | unavailable | 2025-01-27 / 2026-01-25 | us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax |  |  | Yahoo: unsupported_field; SEC: missing; Nasdaq: unsupported_field; Finnhub: not_configured |
| assets | 206803000000 USD | https://data.sec.gov/api/xbrl/companyfacts/CIK0001045810.json | instant / 2026-01-25 | us-gaap:Assets | 19ef503a5770f5660964b3c3aea6937579d9b359da344afe6a9adf59c63d26ff | 2026-11-02 03:28:21.436088+00:00 | Yahoo: period_mismatch; SEC: valid |
| liabilities | 49510000000 USD | https://data.sec.gov/api/xbrl/companyfacts/CIK0001045810.json | instant / 2026-01-25 | us-gaap:Liabilities | 19ef503a5770f5660964b3c3aea6937579d9b359da344afe6a9adf59c63d26ff | 2026-11-02 03:28:21.436088+00:00 | Yahoo: unsupported_field; SEC: valid |
| net_income | 120067000000 USD | https://data.sec.gov/api/xbrl/companyfacts/CIK0001045810.json | 2025-01-27 / 2026-01-25 | us-gaap:NetIncomeLoss | 19ef503a5770f5660964b3c3aea6937579d9b359da344afe6a9adf59c63d26ff | 2026-11-02 03:28:21.436088+00:00 | Yahoo: unsupported_field; SEC: valid |
| operating_cash_flow | 102718000000 USD | https://data.sec.gov/api/xbrl/companyfacts/CIK0001045810.json | 2025-01-27 / 2026-01-25 | us-gaap:NetCashProvidedByUsedInOperatingActivities | 19ef503a5770f5660964b3c3aea6937579d9b359da344afe6a9adf59c63d26ff | 2026-11-02 03:28:21.436088+00:00 | Yahoo: unsupported_field; SEC: valid |
| capital_expenditure | unavailable | unavailable | 2025-01-27 / 2026-01-25 | us-gaap:PaymentsToAcquirePropertyPlantAndEquipment |  |  | Yahoo: unsupported_field; SEC: missing; Nasdaq: unsupported_field; Finnhub: not_configured |

| Calculation | Value | Unit | Status |
| --- | --- | --- | --- |
| NetIncomeLoss / contract revenue excluding assessed tax | unavailable | ratio | pending_data |
| NetIncomeLoss / literal Revenues | unavailable | ratio | pending_data |
| ProfitLoss / contract revenue excluding assessed tax; common-share attribution not established | unavailable | ratio | pending_data |
| ProfitLoss / literal Revenues; common-share attribution not established | unavailable | ratio | pending_data |
| Operating cash flow / contract revenue excluding assessed tax | unavailable | ratio | pending_data |
| Operating cash flow / literal Revenues | unavailable | ratio | pending_data |
| Operating cash flow less PP&amp;E payments; not a complete owner-earnings measure | unavailable | currency | pending_data |
| Operating cash flow less literal ProductiveAssets payments; not a PP&amp;E-only measure | unavailable | currency | pending_data |

Score components: financial_strength: sector_model_and_scope_review_required; valuation: market_price_shares_and_valuation_model_required; growth: comparable_prior_period_and_model_required; profitability: sector_model_and_scope_review_required; cash_flow: sector_model_and_scope_review_required; risk: validated_risk_model_required.


## AAPL

Scope: fund_legal_type_and_sector_model_not_accepted

| Field | Value and currency | Source | Period | Definition | Raw SHA-256 | Observed at | Attempts |
| --- | --- | --- | --- | --- | --- | --- | --- |
| revenue | 416161000000 USD | https://data.sec.gov/api/xbrl/companyfacts/CIK0000320193.json | 2024-09-29 / 2025-09-27 | us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax | 73a86c6aedc31f77cac2ea4df5f80f0b3bd7e6eb58bb4e01444fbedf3afb9c43 | 2026-11-02 03:28:27.722754+00:00 | Yahoo: unsupported_field; SEC: valid |
| assets | 359241000000 USD | https://data.sec.gov/api/xbrl/companyfacts/CIK0000320193.json | instant / 2025-09-27 | us-gaap:Assets | 73a86c6aedc31f77cac2ea4df5f80f0b3bd7e6eb58bb4e01444fbedf3afb9c43 | 2026-11-02 03:28:27.722754+00:00 | Yahoo: period_mismatch; SEC: valid |
| liabilities | 285508000000 USD | https://data.sec.gov/api/xbrl/companyfacts/CIK0000320193.json | instant / 2025-09-27 | us-gaap:Liabilities | 73a86c6aedc31f77cac2ea4df5f80f0b3bd7e6eb58bb4e01444fbedf3afb9c43 | 2026-11-02 03:28:27.722754+00:00 | Yahoo: unsupported_field; SEC: valid |
| net_income | 112010000000 USD | https://data.sec.gov/api/xbrl/companyfacts/CIK0000320193.json | 2024-09-29 / 2025-09-27 | us-gaap:NetIncomeLoss | 73a86c6aedc31f77cac2ea4df5f80f0b3bd7e6eb58bb4e01444fbedf3afb9c43 | 2026-11-02 03:28:27.722754+00:00 | Yahoo: unsupported_field; SEC: valid |
| operating_cash_flow | 111482000000 USD | https://data.sec.gov/api/xbrl/companyfacts/CIK0000320193.json | 2024-09-29 / 2025-09-27 | us-gaap:NetCashProvidedByUsedInOperatingActivities | 73a86c6aedc31f77cac2ea4df5f80f0b3bd7e6eb58bb4e01444fbedf3afb9c43 | 2026-11-02 03:28:27.722754+00:00 | Yahoo: unsupported_field; SEC: valid |
| capital_expenditure | 12715000000 USD | https://data.sec.gov/api/xbrl/companyfacts/CIK0000320193.json | 2024-09-29 / 2025-09-27 | us-gaap:PaymentsToAcquirePropertyPlantAndEquipment | 73a86c6aedc31f77cac2ea4df5f80f0b3bd7e6eb58bb4e01444fbedf3afb9c43 | 2026-11-02 03:28:27.722754+00:00 | Yahoo: unsupported_field; SEC: valid |

| Calculation | Value | Unit | Status |
| --- | --- | --- | --- |
| NetIncomeLoss / contract revenue excluding assessed tax | 0.26915064121818238614382414498235058066469467345571 | ratio | calculated_arithmetic_only |
| NetIncomeLoss / literal Revenues | unavailable | ratio | pending_data |
| ProfitLoss / contract revenue excluding assessed tax; common-share attribution not established | unavailable | ratio | pending_data |
| ProfitLoss / literal Revenues; common-share attribution not established | unavailable | ratio | pending_data |
| Operating cash flow / contract revenue excluding assessed tax | 0.26788190147563082556991164477209541499563870713498 | ratio | calculated_arithmetic_only |
| Operating cash flow / literal Revenues | unavailable | ratio | pending_data |
| Operating cash flow less PP&amp;E payments; not a complete owner-earnings measure | 98767000000 | currency | calculated_arithmetic_only |
| Operating cash flow less literal ProductiveAssets payments; not a PP&amp;E-only measure | unavailable | currency | pending_data |

Score components: financial_strength: sector_model_and_scope_review_required; valuation: market_price_shares_and_valuation_model_required; growth: comparable_prior_period_and_model_required; profitability: sector_model_and_scope_review_required; cash_flow: sector_model_and_scope_review_required; risk: validated_risk_model_required.


## MSFT

Scope: fund_legal_type_and_sector_model_not_accepted

| Field | Value and currency | Source | Period | Definition | Raw SHA-256 | Observed at | Attempts |
| --- | --- | --- | --- | --- | --- | --- | --- |
| revenue | 331839000000 USD | https://data.sec.gov/api/xbrl/companyfacts/CIK0000789019.json | 2025-07-01 / 2026-06-30 | us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax | 464cc12cc4796c90a6a0c709eb4920788aa7d4d5eee8b44f2d11d7d44804ae37 | 2026-11-02 03:28:49.694980+00:00 | Yahoo: unsupported_field; SEC: valid |
| assets | 7.58376E+11 USD | https://query1.finance.yahoo.com/ws/fundamentals-timeseries/v1/finance/timeseries/MSFT?symbol=MSFT&amp;type=annualTotalAssets&amp;period1=1735689600&amp;period2=1798761600 | instant / 2026-06-30 | us-gaap:Assets | 6fdcfe06a83eeb0f292979286c8503ae564da010ed25cb988ed04feae9d639df | 2026-11-02 03:39:35.834241+00:00 | Yahoo: valid |
| liabilities | 315989000000 USD | https://data.sec.gov/api/xbrl/companyfacts/CIK0000789019.json | instant / 2026-06-30 | us-gaap:Liabilities | 464cc12cc4796c90a6a0c709eb4920788aa7d4d5eee8b44f2d11d7d44804ae37 | 2026-11-02 03:28:49.694980+00:00 | Yahoo: unsupported_field; SEC: valid |
| net_income | 133749000000 USD | https://data.sec.gov/api/xbrl/companyfacts/CIK0000789019.json | 2025-07-01 / 2026-06-30 | us-gaap:NetIncomeLoss | 464cc12cc4796c90a6a0c709eb4920788aa7d4d5eee8b44f2d11d7d44804ae37 | 2026-11-02 03:28:49.694980+00:00 | Yahoo: unsupported_field; SEC: valid |
| operating_cash_flow | 182935000000 USD | https://data.sec.gov/api/xbrl/companyfacts/CIK0000789019.json | 2025-07-01 / 2026-06-30 | us-gaap:NetCashProvidedByUsedInOperatingActivities | 464cc12cc4796c90a6a0c709eb4920788aa7d4d5eee8b44f2d11d7d44804ae37 | 2026-11-02 03:28:49.694980+00:00 | Yahoo: unsupported_field; SEC: valid |
| capital_expenditure | 115948000000 USD | https://data.sec.gov/api/xbrl/companyfacts/CIK0000789019.json | 2025-07-01 / 2026-06-30 | us-gaap:PaymentsToAcquirePropertyPlantAndEquipment | 464cc12cc4796c90a6a0c709eb4920788aa7d4d5eee8b44f2d11d7d44804ae37 | 2026-11-02 03:28:49.694980+00:00 | Yahoo: unsupported_field; SEC: valid |

| Calculation | Value | Unit | Status |
| --- | --- | --- | --- |
| NetIncomeLoss / contract revenue excluding assessed tax | 0.40305389059152179219440752895229313010224837948523 | ratio | calculated_arithmetic_only |
| NetIncomeLoss / literal Revenues | unavailable | ratio | pending_data |
| ProfitLoss / contract revenue excluding assessed tax; common-share attribution not established | unavailable | ratio | pending_data |
| ProfitLoss / literal Revenues; common-share attribution not established | unavailable | ratio | pending_data |
| Operating cash flow / contract revenue excluding assessed tax | 0.55127637197556646446017496436524941311901253318627 | ratio | calculated_arithmetic_only |
| Operating cash flow / literal Revenues | unavailable | ratio | pending_data |
| Operating cash flow less PP&amp;E payments; not a complete owner-earnings measure | 66987000000 | currency | calculated_arithmetic_only |
| Operating cash flow less literal ProductiveAssets payments; not a PP&amp;E-only measure | unavailable | currency | pending_data |

Score components: financial_strength: sector_model_and_scope_review_required; valuation: market_price_shares_and_valuation_model_required; growth: comparable_prior_period_and_model_required; profitability: sector_model_and_scope_review_required; cash_flow: sector_model_and_scope_review_required; risk: validated_risk_model_required.


## GOOGL

Scope: fund_legal_type_and_sector_model_not_accepted

| Field | Value and currency | Source | Period | Definition | Raw SHA-256 | Observed at | Attempts |
| --- | --- | --- | --- | --- | --- | --- | --- |
| revenue | unavailable | unavailable | 2025-01-01 / 2025-12-31 | us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax |  |  | Yahoo: unsupported_field; SEC: missing; Nasdaq: unsupported_field; Finnhub: not_configured |
| assets | 5.95281E+11 USD | https://query1.finance.yahoo.com/ws/fundamentals-timeseries/v1/finance/timeseries/GOOGL?symbol=GOOGL&amp;type=annualTotalAssets&amp;period1=1704067200&amp;period2=1767225600 | instant / 2025-12-31 | us-gaap:Assets | 682dedef893fba2a1158828a3944ec4bb45ffcaa2bcf88d383135b25d0d35d93 | 2026-11-02 03:39:38.672835+00:00 | Yahoo: valid |
| liabilities | 180016000000 USD | https://data.sec.gov/api/xbrl/companyfacts/CIK0001652044.json | instant / 2025-12-31 | us-gaap:Liabilities | ec4a3095d634583925b5ea450db8a5ed974dc48f6f1b4f594022310bc78d4032 | 2026-11-02 03:28:56.060634+00:00 | Yahoo: unsupported_field; SEC: valid |
| net_income | 132170000000 USD | https://data.sec.gov/api/xbrl/companyfacts/CIK0001652044.json | 2025-01-01 / 2025-12-31 | us-gaap:NetIncomeLoss | ec4a3095d634583925b5ea450db8a5ed974dc48f6f1b4f594022310bc78d4032 | 2026-11-02 03:28:56.060634+00:00 | Yahoo: unsupported_field; SEC: valid |
| operating_cash_flow | 164713000000 USD | https://data.sec.gov/api/xbrl/companyfacts/CIK0001652044.json | 2025-01-01 / 2025-12-31 | us-gaap:NetCashProvidedByUsedInOperatingActivities | ec4a3095d634583925b5ea450db8a5ed974dc48f6f1b4f594022310bc78d4032 | 2026-11-02 03:28:56.060634+00:00 | Yahoo: unsupported_field; SEC: valid |
| capital_expenditure | 91447000000 USD | https://data.sec.gov/api/xbrl/companyfacts/CIK0001652044.json | 2025-01-01 / 2025-12-31 | us-gaap:PaymentsToAcquirePropertyPlantAndEquipment | ec4a3095d634583925b5ea450db8a5ed974dc48f6f1b4f594022310bc78d4032 | 2026-11-02 03:28:56.060634+00:00 | Yahoo: unsupported_field; SEC: valid |

| Calculation | Value | Unit | Status |
| --- | --- | --- | --- |
| NetIncomeLoss / contract revenue excluding assessed tax | unavailable | ratio | pending_data |
| NetIncomeLoss / literal Revenues | unavailable | ratio | pending_data |
| ProfitLoss / contract revenue excluding assessed tax; common-share attribution not established | unavailable | ratio | pending_data |
| ProfitLoss / literal Revenues; common-share attribution not established | unavailable | ratio | pending_data |
| Operating cash flow / contract revenue excluding assessed tax | unavailable | ratio | pending_data |
| Operating cash flow / literal Revenues | unavailable | ratio | pending_data |
| Operating cash flow less PP&amp;E payments; not a complete owner-earnings measure | 73266000000 | currency | calculated_arithmetic_only |
| Operating cash flow less literal ProductiveAssets payments; not a PP&amp;E-only measure | unavailable | currency | pending_data |

Score components: financial_strength: sector_model_and_scope_review_required; valuation: market_price_shares_and_valuation_model_required; growth: comparable_prior_period_and_model_required; profitability: sector_model_and_scope_review_required; cash_flow: sector_model_and_scope_review_required; risk: validated_risk_model_required.


## AMZN

Scope: fund_legal_type_and_sector_model_not_accepted

| Field | Value and currency | Source | Period | Definition | Raw SHA-256 | Observed at | Attempts |
| --- | --- | --- | --- | --- | --- | --- | --- |
| revenue | 716924000000 USD | https://data.sec.gov/api/xbrl/companyfacts/CIK0001018724.json | 2025-01-01 / 2025-12-31 | us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax | acddb7c0a6973a1fd08372de3b292298a34eae7f42a7eedc4bdebd3ac659c8fd | 2026-11-02 03:29:06.267409+00:00 | Yahoo: unsupported_field; SEC: valid |
| assets | 8.18042E+11 USD | https://query1.finance.yahoo.com/ws/fundamentals-timeseries/v1/finance/timeseries/AMZN?symbol=AMZN&amp;type=annualTotalAssets&amp;period1=1704067200&amp;period2=1767225600 | instant / 2025-12-31 | us-gaap:Assets | bae145608ee49633c55b37b2dfe70dbf997a8f1a0a8e4538fb77a2f1f5146ae1 | 2026-11-02 03:39:41.269829+00:00 | Yahoo: valid |
| liabilities | 406977000000 USD | https://api.nasdaq.com/api/company/AMZN/financials?frequency=1 | instant / 2025-12-31 | us-gaap:Liabilities | 6b55028a8d2071d43469ccdb2d9d78244596163173c01af32329dfe9d70a492a | 2026-11-02 03:39:47.306665+00:00 | Yahoo: unsupported_field; SEC: missing; Nasdaq: valid |
| net_income | 77670000000 USD | https://data.sec.gov/api/xbrl/companyfacts/CIK0001018724.json | 2025-01-01 / 2025-12-31 | us-gaap:NetIncomeLoss | acddb7c0a6973a1fd08372de3b292298a34eae7f42a7eedc4bdebd3ac659c8fd | 2026-11-02 03:29:06.267409+00:00 | Yahoo: unsupported_field; SEC: valid |
| operating_cash_flow | 139514000000 USD | https://data.sec.gov/api/xbrl/companyfacts/CIK0001018724.json | 2025-01-01 / 2025-12-31 | us-gaap:NetCashProvidedByUsedInOperatingActivities | acddb7c0a6973a1fd08372de3b292298a34eae7f42a7eedc4bdebd3ac659c8fd | 2026-11-02 03:29:06.267409+00:00 | Yahoo: unsupported_field; SEC: valid |
| capital_expenditure | unavailable | unavailable | 2025-01-01 / 2025-12-31 | us-gaap:PaymentsToAcquirePropertyPlantAndEquipment |  |  | Yahoo: unsupported_field; SEC: missing; Nasdaq: unsupported_field; Finnhub: not_configured |

| Calculation | Value | Unit | Status |
| --- | --- | --- | --- |
| NetIncomeLoss / contract revenue excluding assessed tax | 0.10833784334183260708248015131310989728339405571581 | ratio | calculated_arithmetic_only |
| NetIncomeLoss / literal Revenues | unavailable | ratio | pending_data |
| ProfitLoss / contract revenue excluding assessed tax; common-share attribution not established | unavailable | ratio | pending_data |
| ProfitLoss / literal Revenues; common-share attribution not established | unavailable | ratio | pending_data |
| Operating cash flow / contract revenue excluding assessed tax | 0.19460082240237458921726710223119884394998633048970 | ratio | calculated_arithmetic_only |
| Operating cash flow / literal Revenues | unavailable | ratio | pending_data |
| Operating cash flow less PP&amp;E payments; not a complete owner-earnings measure | unavailable | currency | pending_data |
| Operating cash flow less literal ProductiveAssets payments; not a PP&amp;E-only measure | unavailable | currency | pending_data |

Score components: financial_strength: sector_model_and_scope_review_required; valuation: market_price_shares_and_valuation_model_required; growth: comparable_prior_period_and_model_required; profitability: sector_model_and_scope_review_required; cash_flow: sector_model_and_scope_review_required; risk: validated_risk_model_required.


## AVGO

Scope: fund_legal_type_and_sector_model_not_accepted

| Field | Value and currency | Source | Period | Definition | Raw SHA-256 | Observed at | Attempts |
| --- | --- | --- | --- | --- | --- | --- | --- |
| revenue | 63887000000 USD | https://data.sec.gov/api/xbrl/companyfacts/CIK0001730168.json | 2024-11-04 / 2025-11-02 | us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax | 3bdb6644c12addf1e63c4dc861008d7804fbf3d3f5aa6eb9b97f72c0e89a7adf | 2026-11-02 03:29:21.978529+00:00 | Yahoo: unsupported_field; SEC: valid |
| assets | 171092000000 USD | https://data.sec.gov/api/xbrl/companyfacts/CIK0001730168.json | instant / 2025-11-02 | us-gaap:Assets | 3bdb6644c12addf1e63c4dc861008d7804fbf3d3f5aa6eb9b97f72c0e89a7adf | 2026-11-02 03:29:21.978529+00:00 | Yahoo: missing; SEC: valid |
| liabilities | 89800000000 USD | https://data.sec.gov/api/xbrl/companyfacts/CIK0001730168.json | instant / 2025-11-02 | us-gaap:Liabilities | 3bdb6644c12addf1e63c4dc861008d7804fbf3d3f5aa6eb9b97f72c0e89a7adf | 2026-11-02 03:29:21.978529+00:00 | Yahoo: unsupported_field; SEC: valid |
| net_income | unavailable | unavailable | 2024-11-04 / 2025-11-02 | us-gaap:NetIncomeLoss |  |  | Yahoo: unsupported_field; SEC: missing; Nasdaq: unsupported_field; Finnhub: not_configured |
| operating_cash_flow | 27537000000 USD | https://data.sec.gov/api/xbrl/companyfacts/CIK0001730168.json | 2024-11-04 / 2025-11-02 | us-gaap:NetCashProvidedByUsedInOperatingActivities | 3bdb6644c12addf1e63c4dc861008d7804fbf3d3f5aa6eb9b97f72c0e89a7adf | 2026-11-02 03:29:21.978529+00:00 | Yahoo: unsupported_field; SEC: valid |
| capital_expenditure | 623000000 USD | https://data.sec.gov/api/xbrl/companyfacts/CIK0001730168.json | 2024-11-04 / 2025-11-02 | us-gaap:PaymentsToAcquirePropertyPlantAndEquipment | 3bdb6644c12addf1e63c4dc861008d7804fbf3d3f5aa6eb9b97f72c0e89a7adf | 2026-11-02 03:29:21.978529+00:00 | Yahoo: unsupported_field; SEC: valid |

| Calculation | Value | Unit | Status |
| --- | --- | --- | --- |
| NetIncomeLoss / contract revenue excluding assessed tax | unavailable | ratio | pending_data |
| NetIncomeLoss / literal Revenues | unavailable | ratio | pending_data |
| ProfitLoss / contract revenue excluding assessed tax; common-share attribution not established | unavailable | ratio | pending_data |
| ProfitLoss / literal Revenues; common-share attribution not established | unavailable | ratio | pending_data |
| Operating cash flow / contract revenue excluding assessed tax | 0.43102665644027736472208743562853162615242537605460 | ratio | calculated_arithmetic_only |
| Operating cash flow / literal Revenues | unavailable | ratio | pending_data |
| Operating cash flow less PP&amp;E payments; not a complete owner-earnings measure | 26914000000 | currency | calculated_arithmetic_only |
| Operating cash flow less literal ProductiveAssets payments; not a PP&amp;E-only measure | unavailable | currency | pending_data |

Score components: financial_strength: sector_model_and_scope_review_required; valuation: market_price_shares_and_valuation_model_required; growth: comparable_prior_period_and_model_required; profitability: sector_model_and_scope_review_required; cash_flow: sector_model_and_scope_review_required; risk: validated_risk_model_required.


## META

Scope: fund_legal_type_and_sector_model_not_accepted

| Field | Value and currency | Source | Period | Definition | Raw SHA-256 | Observed at | Attempts |
| --- | --- | --- | --- | --- | --- | --- | --- |
| revenue | 200966000000 USD | https://data.sec.gov/api/xbrl/companyfacts/CIK0001326801.json | 2025-01-01 / 2025-12-31 | us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax | b0d0d92870b68488cec086cffd83514f2cc6c80d3e8c4f91e192b17ce3e7c946 | 2026-11-02 03:29:32.426520+00:00 | Yahoo: unsupported_field; SEC: valid |
| assets | 3.66021E+11 USD | https://query1.finance.yahoo.com/ws/fundamentals-timeseries/v1/finance/timeseries/META?symbol=META&amp;type=annualTotalAssets&amp;period1=1704067200&amp;period2=1767225600 | instant / 2025-12-31 | us-gaap:Assets | 7576598fccd615401396cfd619f4eea2f8847826828547a2a543f9d3f87a22ac | 2026-11-02 03:39:54.543606+00:00 | Yahoo: valid |
| liabilities | 148778000000 USD | https://data.sec.gov/api/xbrl/companyfacts/CIK0001326801.json | instant / 2025-12-31 | us-gaap:Liabilities | b0d0d92870b68488cec086cffd83514f2cc6c80d3e8c4f91e192b17ce3e7c946 | 2026-11-02 03:29:32.426520+00:00 | Yahoo: unsupported_field; SEC: valid |
| net_income | 60458000000 USD | https://data.sec.gov/api/xbrl/companyfacts/CIK0001326801.json | 2025-01-01 / 2025-12-31 | us-gaap:NetIncomeLoss | b0d0d92870b68488cec086cffd83514f2cc6c80d3e8c4f91e192b17ce3e7c946 | 2026-11-02 03:29:32.426520+00:00 | Yahoo: unsupported_field; SEC: valid |
| operating_cash_flow | 115800000000 USD | https://data.sec.gov/api/xbrl/companyfacts/CIK0001326801.json | 2025-01-01 / 2025-12-31 | us-gaap:NetCashProvidedByUsedInOperatingActivities | b0d0d92870b68488cec086cffd83514f2cc6c80d3e8c4f91e192b17ce3e7c946 | 2026-11-02 03:29:32.426520+00:00 | Yahoo: unsupported_field; SEC: valid |
| capital_expenditure | 69691000000 USD | https://data.sec.gov/api/xbrl/companyfacts/CIK0001326801.json | 2025-01-01 / 2025-12-31 | us-gaap:PaymentsToAcquirePropertyPlantAndEquipment | b0d0d92870b68488cec086cffd83514f2cc6c80d3e8c4f91e192b17ce3e7c946 | 2026-11-02 03:29:32.426520+00:00 | Yahoo: unsupported_field; SEC: valid |

| Calculation | Value | Unit | Status |
| --- | --- | --- | --- |
| NetIncomeLoss / contract revenue excluding assessed tax | 0.30083695749529771205079466178358528308271050824518 | ratio | calculated_arithmetic_only |
| NetIncomeLoss / literal Revenues | unavailable | ratio | pending_data |
| ProfitLoss / contract revenue excluding assessed tax; common-share attribution not established | unavailable | ratio | pending_data |
| ProfitLoss / literal Revenues; common-share attribution not established | unavailable | ratio | pending_data |
| Operating cash flow / contract revenue excluding assessed tax | 0.57621687250579700048764467621388692614671138401521 | ratio | calculated_arithmetic_only |
| Operating cash flow / literal Revenues | unavailable | ratio | pending_data |
| Operating cash flow less PP&amp;E payments; not a complete owner-earnings measure | 46109000000 | currency | calculated_arithmetic_only |
| Operating cash flow less literal ProductiveAssets payments; not a PP&amp;E-only measure | unavailable | currency | pending_data |

Score components: financial_strength: sector_model_and_scope_review_required; valuation: market_price_shares_and_valuation_model_required; growth: comparable_prior_period_and_model_required; profitability: sector_model_and_scope_review_required; cash_flow: sector_model_and_scope_review_required; risk: validated_risk_model_required.


## TSLA

Scope: fund_legal_type_and_sector_model_not_accepted

| Field | Value and currency | Source | Period | Definition | Raw SHA-256 | Observed at | Attempts |
| --- | --- | --- | --- | --- | --- | --- | --- |
| revenue | 94827000000 USD | https://data.sec.gov/api/xbrl/companyfacts/CIK0001318605.json | 2025-01-01 / 2025-12-31 | us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax | c951e0ae2402dd8cf8f39319928adccc4196b997941fe40b0d4d6b8060802db1 | 2026-11-02 03:29:38.439017+00:00 | Yahoo: unsupported_field; SEC: valid |
| assets | 1.37806E+11 USD | https://query1.finance.yahoo.com/ws/fundamentals-timeseries/v1/finance/timeseries/TSLA?symbol=TSLA&amp;type=annualTotalAssets&amp;period1=1704067200&amp;period2=1767225600 | instant / 2025-12-31 | us-gaap:Assets | bb1051d505c4152125d52a7209b8f97d46b2bd97464e636dba66fdf507340895 | 2026-11-02 03:39:58.034195+00:00 | Yahoo: valid |
| liabilities | 54941000000 USD | https://data.sec.gov/api/xbrl/companyfacts/CIK0001318605.json | instant / 2025-12-31 | us-gaap:Liabilities | c951e0ae2402dd8cf8f39319928adccc4196b997941fe40b0d4d6b8060802db1 | 2026-11-02 03:29:38.439017+00:00 | Yahoo: unsupported_field; SEC: valid |
| net_income | 3794000000 USD | https://data.sec.gov/api/xbrl/companyfacts/CIK0001318605.json | 2025-01-01 / 2025-12-31 | us-gaap:NetIncomeLoss | c951e0ae2402dd8cf8f39319928adccc4196b997941fe40b0d4d6b8060802db1 | 2026-11-02 03:29:38.439017+00:00 | Yahoo: unsupported_field; SEC: valid |
| operating_cash_flow | 14747000000 USD | https://data.sec.gov/api/xbrl/companyfacts/CIK0001318605.json | 2025-01-01 / 2025-12-31 | us-gaap:NetCashProvidedByUsedInOperatingActivities | c951e0ae2402dd8cf8f39319928adccc4196b997941fe40b0d4d6b8060802db1 | 2026-11-02 03:29:38.439017+00:00 | Yahoo: unsupported_field; SEC: valid |
| capital_expenditure | 8527000000 USD | https://data.sec.gov/api/xbrl/companyfacts/CIK0001318605.json | 2025-01-01 / 2025-12-31 | us-gaap:PaymentsToAcquirePropertyPlantAndEquipment | c951e0ae2402dd8cf8f39319928adccc4196b997941fe40b0d4d6b8060802db1 | 2026-11-02 03:29:38.439017+00:00 | Yahoo: unsupported_field; SEC: valid |

| Calculation | Value | Unit | Status |
| --- | --- | --- | --- |
| NetIncomeLoss / contract revenue excluding assessed tax | 0.040009701878157064970947093127484788087780906281966 | ratio | calculated_arithmetic_only |
| NetIncomeLoss / literal Revenues | unavailable | ratio | pending_data |
| ProfitLoss / contract revenue excluding assessed tax; common-share attribution not established | unavailable | ratio | pending_data |
| ProfitLoss / literal Revenues; common-share attribution not established | unavailable | ratio | pending_data |
| Operating cash flow / contract revenue excluding assessed tax | 0.15551477954590992017041559893279340272285319581976 | ratio | calculated_arithmetic_only |
| Operating cash flow / literal Revenues | unavailable | ratio | pending_data |
| Operating cash flow less PP&amp;E payments; not a complete owner-earnings measure | 6220000000 | currency | calculated_arithmetic_only |
| Operating cash flow less literal ProductiveAssets payments; not a PP&amp;E-only measure | unavailable | currency | pending_data |

Score components: financial_strength: sector_model_and_scope_review_required; valuation: market_price_shares_and_valuation_model_required; growth: comparable_prior_period_and_model_required; profitability: sector_model_and_scope_review_required; cash_flow: sector_model_and_scope_review_required; risk: validated_risk_model_required.

