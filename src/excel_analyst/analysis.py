"""Deterministic cleaning and statistical analysis primitives."""

from __future__ import annotations

import math
import re
from typing import Any

import numpy as np
import pandas as pd
from scipy import stats

_NUMBER_PATTERN = re.compile(r"^[+-]?(?:\d[\d,]*\.?\d*|\.\d+)(?:[eE][+-]?\d+)?$")


def _parse_numeric(value: Any) -> float | None:
    """Parse common human-formatted numbers without guessing mixed text columns."""
    if pd.isna(value):
        return None
    if isinstance(value, (int, float, np.number)) and not isinstance(value, (bool, np.bool_)):
        return float(value)

    text = str(value).strip()
    if not text:
        return None

    percent = text.endswith("%")
    if percent:
        text = text[:-1].strip()
    if text.startswith("(") and text.endswith(")"):
        text = f"-{text[1:-1].strip()}"
    text = re.sub(r"[,$€£¥\s]", "", text)
    if not _NUMBER_PATTERN.fullmatch(text):
        return None
    try:
        result = float(text.replace(",", ""))
    except ValueError:
        return None
    if not math.isfinite(result):
        return None
    return result / 100 if percent else result


def convert_numeric_strings(frame: pd.DataFrame) -> tuple[pd.DataFrame, list[str]]:
    """Convert object columns only when all present values safely parse as numbers."""
    cleaned = frame.copy()
    converted: list[str] = []
    for column in cleaned.columns:
        if not (pd.api.types.is_object_dtype(cleaned[column]) or
                pd.api.types.is_string_dtype(cleaned[column])):
            continue
        values = cleaned[column]
        non_missing = values.dropna()
        if non_missing.empty:
            continue
        parsed = [_parse_numeric(value) for value in non_missing]
        if all(value is not None for value in parsed):
            numeric = pd.Series(index=values.index, dtype="float64")
            numeric.loc[non_missing.index] = parsed
            cleaned[column] = numeric
            converted.append(str(column))
    return cleaned, converted


def clean_frame(
    frame: pd.DataFrame, null_strategy: str = "drop_rows"
) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Remove exact duplicates, convert safe numeric strings, then apply null policy."""
    if null_strategy not in {"drop_rows", "keep"}:
        raise ValueError("null_strategy must be 'drop_rows' or 'keep'.")
    if frame.empty:
        raise ValueError("The selected worksheet contains no data rows.")
    if frame.columns.duplicated().any():
        raise ValueError("The worksheet contains duplicate column names; rename them before analysis.")

    original_rows = len(frame)
    original_missing = {str(key): int(value) for key, value in frame.isna().sum().items()}
    deduplicated = frame.drop_duplicates().copy()
    duplicate_rows = original_rows - len(deduplicated)
    converted, converted_columns = convert_numeric_strings(deduplicated)
    rows_before_nulls = len(converted)
    if null_strategy == "drop_rows":
        result = converted.dropna(axis=0, how="any").reset_index(drop=True)
        null_rows_removed = rows_before_nulls - len(result)
    else:
        result = converted.reset_index(drop=True)
        null_rows_removed = 0
    if result.empty:
        raise ValueError("Cleaning removed every row. Try --null-strategy keep or review the workbook.")

    summary = {
        "rows_before": original_rows,
        "rows_after": len(result),
        "duplicate_rows_removed": duplicate_rows,
        "null_rows_removed": null_rows_removed,
        "null_strategy": null_strategy,
        "missing_values_before": original_missing,
        "missing_values_after": {
            str(key): int(value) for key, value in result.isna().sum().items()
        },
        "numeric_columns_converted": converted_columns,
        "columns": [str(column) for column in result.columns],
    }
    return result, summary


def _finite_or_none(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _pvalue(value: Any) -> float | None:
    return _finite_or_none(value)


def _is_numeric_target(series: pd.Series) -> bool:
    return pd.api.types.is_numeric_dtype(series) and not pd.api.types.is_bool_dtype(series)


def _numeric_predictor_stats(target: pd.Series, feature: pd.Series) -> dict[str, Any] | None:
    paired = pd.concat([target, feature], axis=1).dropna()
    if len(paired) < 3 or paired.iloc[:, 0].nunique() < 2 or paired.iloc[:, 1].nunique() < 2:
        return None
    pearson = stats.pearsonr(paired.iloc[:, 0], paired.iloc[:, 1])
    spearman = stats.spearmanr(paired.iloc[:, 0], paired.iloc[:, 1])
    return {
        "feature": str(feature.name),
        "kind": "numeric",
        "n": len(paired),
        "pearson_r": _finite_or_none(pearson.statistic),
        "pearson_p": _pvalue(pearson.pvalue),
        "spearman_rho": _finite_or_none(spearman.statistic),
        "spearman_p": _pvalue(spearman.pvalue),
    }


def _numeric_by_category_stats(target: pd.Series, feature: pd.Series) -> dict[str, Any] | None:
    paired = pd.DataFrame({"target": target, "feature": feature}).dropna()
    levels = paired["feature"].unique()
    if len(paired) < 3 or len(levels) < 2 or len(levels) > 20:
        return None
    groups = [group["target"].to_numpy() for _, group in paired.groupby("feature", observed=True)]
    if any(len(group) < 2 for group in groups):
        return None
    test = stats.f_oneway(*groups)
    grand_mean = float(paired["target"].mean())
    between = sum(len(group) * (float(np.mean(group)) - grand_mean) ** 2 for group in groups)
    total = float(((paired["target"] - grand_mean) ** 2).sum())
    group_means = {
        str(level): round(float(group.mean()), 6)
        for level, group in paired.groupby("feature", observed=True)["target"]
    }
    return {
        "feature": str(feature.name),
        "kind": "categorical",
        "n": len(paired),
        "groups": len(groups),
        "eta_squared": _finite_or_none(between / total) if total else None,
        "anova_f": _finite_or_none(test.statistic),
        "anova_p": _pvalue(test.pvalue),
        "target_mean_by_group": group_means,
    }


def _categorical_association_stats(target: pd.Series, feature: pd.Series) -> dict[str, Any] | None:
    paired = pd.DataFrame({"target": target, "feature": feature}).dropna()
    if len(paired) < 3 or paired["feature"].nunique() > 20 or paired["target"].nunique() > 20:
        return None
    table = pd.crosstab(paired["target"], paired["feature"])
    if min(table.shape) < 2:
        return None
    chi2, pvalue, _, _ = stats.chi2_contingency(table)
    n = int(table.to_numpy().sum())
    rows, columns = table.shape
    phi2 = chi2 / n
    correction = ((columns - 1) * (rows - 1)) / (n - 1) if n > 1 else 0.0
    corrected_phi2 = max(0.0, phi2 - correction)
    corrected_rows = rows - ((rows - 1) ** 2) / (n - 1)
    corrected_columns = columns - ((columns - 1) ** 2) / (n - 1)
    denominator = min(corrected_columns - 1, corrected_rows - 1)
    cramer_v = math.sqrt(corrected_phi2 / denominator) if denominator > 0 else 0.0
    return {
        "feature": str(feature.name),
        "kind": "categorical",
        "n": n,
        "cramers_v": _finite_or_none(cramer_v),
        "chi_square": _finite_or_none(chi2),
        "chi_square_p": _pvalue(pvalue),
    }


def analyze_frame(frame: pd.DataFrame, target_column: str) -> dict[str, Any]:
    """Compute deterministic target descriptions and univariate associations."""
    if target_column not in frame.columns:
        available = ", ".join(map(str, frame.columns))
        raise ValueError(f"Target column {target_column!r} was not found. Available columns: {available}")
    if len(frame) < 3:
        raise ValueError("At least three rows are required for target analysis.")
    target = frame[target_column]
    if target.isna().all():
        raise ValueError(f"Target column {target_column!r} contains no observed values.")

    numeric_target = _is_numeric_target(target)
    description: dict[str, Any]
    if numeric_target:
        observed = target.dropna().astype(float)
        q1, median, q3 = observed.quantile([0.25, 0.5, 0.75])
        iqr = float(q3 - q1)
        outlier_share = float(((observed < q1 - 1.5 * iqr) | (observed > q3 + 1.5 * iqr)).mean()) if iqr else 0.0
        description = {
            "type": "numeric",
            "n": int(observed.size),
            "missing": int(target.isna().sum()),
            "mean": _finite_or_none(observed.mean()),
            "median": _finite_or_none(median),
            "std": _finite_or_none(observed.std()),
            "min": _finite_or_none(observed.min()),
            "q1": _finite_or_none(q1),
            "q3": _finite_or_none(q3),
            "max": _finite_or_none(observed.max()),
            "iqr_outlier_share": _finite_or_none(outlier_share),
            "skew": _finite_or_none(observed.skew()) if len(observed) >= 3 else None,
        }
    else:
        counts = target.astype("string").fillna("<missing>").value_counts(dropna=False)
        description = {
            "type": "categorical",
            "n": int(target.notna().sum()),
            "missing": int(target.isna().sum()),
            "unique_values": int(target.nunique(dropna=True)),
            "class_counts": {str(key): int(value) for key, value in counts.head(20).items()},
            "class_shares": {str(key): round(float(value / max(len(target), 1)), 6) for key, value in counts.head(20).items()},
        }

    associations: list[dict[str, Any]] = []
    excluded_high_cardinality: list[str] = []
    for column in frame.columns:
        if column == target_column:
            continue
        series = frame[column]
        numeric = pd.api.types.is_numeric_dtype(series) and not pd.api.types.is_bool_dtype(series)
        if numeric_target:
            result = _numeric_predictor_stats(target, series) if numeric else _numeric_by_category_stats(target, series)
        elif numeric:
            result = _numeric_by_category_stats(series, target.rename(str(column)))
            if result is not None:
                result["kind"] = "numeric"
                result["feature"] = str(column)
                result["target_group_means"] = result.pop("target_mean_by_group")
                result["eta_squared"] = result.pop("eta_squared")
        else:
            result = _categorical_association_stats(target, series)
        if result is None:
            if series.nunique(dropna=True) > 20:
                excluded_high_cardinality.append(str(column))
            continue
        associations.append(result)

    def association_strength(result: dict[str, Any]) -> float:
        for key in ("spearman_rho", "eta_squared", "cramers_v"):
            value = result.get(key)
            if value is not None:
                return abs(float(value))
        return 0.0

    associations.sort(key=association_strength, reverse=True)
    return {
        "target": str(target_column),
        "target_summary": description,
        "associations": associations,
        "excluded_high_cardinality_columns": excluded_high_cardinality,
        "analysis_notes": [
            "Associations are observational and do not establish causation.",
            "P-values are exploratory and unadjusted for multiple comparisons.",
            "Cramer's V is bias-corrected; categorical tests exclude predictors or targets with more than 20 levels.",
        ],
    }


def json_safe(value: Any) -> Any:
    """Convert common NumPy/pandas values to JSON-compatible primitives."""
    if isinstance(value, dict):
        return {str(key): json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [json_safe(item) for item in value]
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        return _finite_or_none(value)
    if isinstance(value, (np.bool_,)):
        return bool(value)
    if value is pd.NA or value is pd.NaT:
        return None
    return value
