# Salary explanation safeguards

This analysis is distinct from salary prediction and cannot change the predictive
champion. Only prepared records whose split is `train` enter the explanation.
Validation, calibration and test features are not inspected.

## Specification

Four existing native-scale features are used: experience midpoint, observed skill
count, a `stat` token indicator and a `model` token indicator. These keyword
indicators are noisy proxies, not measured employee capabilities. No causal
interpretation or currency conversion is justified.

The proportional-odds diagnostic fits a separate binary cumulative logit for each
observed band threshold in a stacked design. Intercepts are unrestricted. A joint
Wald test compares all threshold slopes with the first threshold's slopes.
The sandwich covariance clusters the full stack by original preparation group,
accounting for repeated thresholds and related postings together. This is not
labelled the classical Brant test. Feature-level exploratory tests use
Benjamini-Hochberg correction; the overall diagnostic uses alpha 0.05.

The implementation uses statsmodels' [cluster-robust covariance support](https://github.com/statsmodels/statsmodels/blob/main/statsmodels/base/covtype.py).
Inference is asymptotic and assumes independent clusters. A non-rejection does
not validate all model assumptions. Rank-deficient contrast covariance or
nonconvergence is inconclusive, never evidence for proportional odds.

## Interpretation switch

When slope equality is rejected or inconclusive, the primary explanation becomes
multinomial logistic regression. Band 0 is the explicit reference. Reported
coefficients and intervals are on the log relative-probability-ratio scale;
they are not common cumulative odds ratios. Both models use clustered
coefficient intervals. Nonconverged multinomial output is marked inconclusive.

Common-odds coefficients remain available for audit but are diagnostic-only when
the common-slope specification is rejected. Do not use them as headline pay
multipliers, causal learning returns, or evidence that statistics "pays twice".

## Reproduction

```powershell
.venv/Scripts/python.exe -m ml_pipeline.sas.run --stage explain
.venv/Scripts/python.exe -m ml_pipeline.sas.run --stage analyze
.venv/Scripts/python.exe -m pytest tests/test_sas_explanation.py -q
```

The first command writes `private_sas/salary_explanation.json`; the second refreshes
the integrated `research_report.json`. Neither trains or reselects salary
predictors. These confidential outputs must not enter public static exports.
After regenerating submission documents, repeat page-count and visual review:
the multinomial coefficient table changes the layout.

Synthetic tests cover contrast algebra, detection of deliberately nonparallel
slopes, insufficient-group rejection and isolation from held-out feature values.
Independent SAS replication, specification sensitivity and prospective validation
remain separate acceptance tasks.
