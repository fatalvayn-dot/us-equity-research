# Financial review v1

Purpose: make financial suitability, valuation gaps and risk visible independently
in the usable research browser. Policy identifier: `financial-review-v1`.

| Check | Literal inputs | Trigger | Report effect |
| --- | --- | --- | --- |
| balance_deficit | Assets, Liabilities, same instant | Liabilities > Assets | mandatory critical review |
| loss_and_operating_cash_outflow | NetIncomeLoss, NetCashProvidedByUsedInOperatingActivities, same annual duration | both < 0 | mandatory critical review |
| operating_loss | OperatingIncomeLoss | < 0 | watch |
| current_balance_shortfall | AssetsCurrent, LiabilitiesCurrent | current assets < current liabilities | watch |

These thresholds are conservative research-policy hypotheses. They are not
empirically calibrated probabilities or SEC recommendations. Negative book
balances can result from capital distributions and accounting treatments; they
do not independently establish insolvency. Liabilities are not interest-bearing
debt. Low current balances can reflect an efficient cash cycle. Positive profit
does not establish cash generation or debt-service capacity. Conceptual reference:
[SEC financial-statement guide](https://www.sec.gov/about/reports-publications/beginners-guide-financial-statements).

Every check independently revalidates exact CIK, period, currency, unit,
accounting definition, source hash and publication/retrieval cutoff. Annual-flow
checks require an explicit 350–380-day period, including 52/53-week years. A
550-day period-end age limit is a coarse stale-input guard; it does not confirm
the most recent filing. This first screen uses annual periods only. A newly
retrieved old statement cannot pass the age guard by changing its retrieval time.

Zero is literal data, not missing. Missing, invalid, negative balance amounts or
unsupported periods leave the relevant check unresolved. Critical triggers take
priority over unresolved or favorable other checks. A `no_screen_trigger` result
means none of these four checks triggered; `overall_risk_cleared` remains false.
The report never imports caller-supplied risk clearance or score approvals.

Debt maturities, covenants, going-concern opinions, material events, financial
institutions and other sector economics require further source-bound review.
Special/unknown models and unverified common-share scope remain unapproved. The
report exposes these gaps separately from valuation and score-component gaps.
No numerical total or rank is produced until all required gates are implemented
and accepted; the current 100-point weights remain an unvalidated hypothesis.

Recorded 100-candidate reassessment: 4 mandatory reviews, 44 unresolved numeric
screens and 52 without a trigger in this limited screen. Four balance-deficit
signals: ABBV, PM, DELL and MCD. Twenty current-balance and two operating-loss
watch signals overlap company categories. These are dated source observations,
not new live outcomes or investment recommendations. Rebuild with the README
command; inspect `docs/evidence/risk100/manifest.json` for artifact hashes.
