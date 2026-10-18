import pandas as pd
import pytest

from excel_analyst.analysis import analyze_frame, clean_frame, convert_numeric_strings
from excel_analyst.workspace import AnalysisWorkspace


def test_convert_common_numeric_string_formats():
    frame = pd.DataFrame({"amount": ["1,200", "($25)", "12.5%"], "label": ["north", "south", "east"]})
    converted, columns = convert_numeric_strings(frame)
    assert columns == ["amount"]
    assert converted["amount"].tolist() == [1200.0, -25.0, 0.125]
    assert converted["label"].tolist() == ["north", "south", "east"]


def test_clean_frame_removes_duplicates_and_null_rows():
    frame = pd.DataFrame({"x": ["1", "1", "3"], "y": [4, 4, None]})
    cleaned, summary = clean_frame(frame)
    assert cleaned.to_dict("records") == [{"x": 1.0, "y": 4.0}]
    assert summary["duplicate_rows_removed"] == 1
    assert summary["null_rows_removed"] == 1


def test_keep_nulls_and_reject_invalid_policy():
    frame = pd.DataFrame({"x": [1, None, 3]})
    cleaned, summary = clean_frame(frame, "keep")
    assert len(cleaned) == 3
    assert summary["null_rows_removed"] == 0
    with pytest.raises(ValueError, match="null_strategy"):
        clean_frame(frame, "impute")


def test_numeric_target_analysis_ranks_related_predictor():
    frame = pd.DataFrame({"target": [1, 2, 3, 4, 5], "related": [2, 4, 6, 8, 10], "group": ["a", "a", "b", "b", "b"]})
    result = analyze_frame(frame, "target")
    assert result["target_summary"]["type"] == "numeric"
    assert result["associations"][0]["feature"] == "related"
    assert result["associations"][0]["spearman_rho"] == pytest.approx(1)


def test_categorical_target_analyzes_numeric_groups():
    frame = pd.DataFrame({"segment": ["A", "A", "A", "B", "B", "B"], "spend": [1, 2, 3, 20, 21, 22]})
    result = analyze_frame(frame, "segment")
    assert result["target_summary"]["type"] == "categorical"
    association = result["associations"][0]
    assert association["feature"] == "spend"
    assert association["eta_squared"] > 0.9


def test_categorical_predictor_association_uses_cramers_v():
    frame = pd.DataFrame(
        {"target": ["A", "A", "B", "B", "C", "C"], "segment": ["x", "x", "y", "y", "z", "z"]}
    )
    result = analyze_frame(frame, "target")
    assert result["associations"][0]["feature"] == "segment"
    assert result["associations"][0]["cramers_v"] > 0.8


def test_workspace_exports_cleaned_workbook_and_json(tmp_path):
    source_path = tmp_path / "source.xlsx"
    output_dir = tmp_path / "results"
    pd.DataFrame(
        {"amount": ["1", "2", "2", "4", "5"], "target": [1, 2, 2, 4, None]}
    ).to_excel(source_path, index=False)

    workspace = AnalysisWorkspace(source_path, output_dir)
    summary = workspace.clean()
    analysis = workspace.analyze("target")
    json_path, report_path = workspace.save_results("# Findings")

    exported = pd.read_excel(workspace.cleaned_path)
    assert len(exported) == 3
    assert pd.api.types.is_numeric_dtype(exported["amount"])
    assert summary["duplicate_rows_removed"] == 1
    assert analysis["target"] == "target"
    assert json_path.is_file()
    assert report_path.read_text(encoding="utf-8").startswith("# Findings")
