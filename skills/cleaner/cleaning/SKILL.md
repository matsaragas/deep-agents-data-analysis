---
name: cleaning
description: >-
  Clean Excel tabular data before analysis: inspect quality, remove duplicate records,
  handle missing values according to the requested policy, and safely convert numeric
  strings. Use whenever an Excel workbook needs preprocessing.
---

# Excel data cleaning

## Procedure

1. Call the `clean_excel_data` tool before any target analysis. It performs deterministic
   transformations; do not try to clean a sample and extrapolate to the full workbook.
2. Keep the original workbook unchanged. The tool writes the cleaned copy to the configured
   output directory and reports exact row counts, duplicate counts, missing-value counts,
   and conversions.
3. Remove exact duplicate rows.
4. Convert object columns only when every non-empty value can be parsed as a number. Common
   forms such as `"1,234"`, currency symbols, parenthesized negatives, and percentages are
   supported. A percentage is represented as a fraction (for example, `"12%"` becomes `0.12`).
   Never convert identifiers or mixed categorical text by guessing.
5. Apply the user-selected null policy. `drop_rows` removes any row with at least one missing
   value; `keep` leaves missing values in place. Do not silently impute values or drop columns.
6. Report the impact of row removal prominently. Complete-case analysis can introduce bias;
   mention this limitation if many rows were removed.
7. Return a concise cleaning summary to the coordinator, not raw rows.
