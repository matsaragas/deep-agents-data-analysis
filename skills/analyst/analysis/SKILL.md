---
name: analysis
description: >-
  Analyze an Excel dataset around a user-selected target variable. Use for target-centric
  descriptive statistics, numeric correlations, categorical associations, group differences,
  and evidence-based explanatory insights.
---

# Target-centered analysis

## Procedure

1. Analyze only the cleaned dataset produced by `clean_excel_data`. If cleaning has not run,
   ask the coordinator to delegate cleaning first.
2. Call `analyze_target` with the exact target column name. The tool computes statistics from
   the full cleaned dataset; do not infer results from the profile or a subset.
3. Explain the target distribution and the strongest supported relationships. Include effect
   sizes, sample sizes, and p-values where available, and distinguish statistical association
   from practical importance.
4. For numeric targets, interpret Pearson correlation as linear association and Spearman as
   monotonic association. For categorical targets, use eta-squared / ANOVA for numeric
   predictors and bias-corrected Cramer's V / chi-square for categorical predictors.
5. Treat p-values as exploratory, unadjusted tests. Mention small samples, class imbalance,
   missingness, and high-cardinality exclusions where relevant. Do not claim causation or
   imply that association proves an explanatory mechanism.
6. Return concise findings, caveats, and useful follow-up questions. Do not reproduce raw data.
