"""Per-run Excel data state and deterministic output handling."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd

from excel_analyst.analysis import analyze_frame, clean_frame, json_safe


class AnalysisWorkspace:
    """Own the source and cleaned frames for one workbook analysis run."""

    def __init__(
        self,
        workbook: Path,
        output_dir: Path,
        sheet_name: str | int = 0,
        null_strategy: str = "drop_rows",
    ) -> None:
        self.workbook = workbook.expanduser().resolve()
        self.output_dir = output_dir.expanduser().resolve()
        self.sheet_name = sheet_name
        self.null_strategy = null_strategy
        if not self.workbook.is_file():
            raise FileNotFoundError(f"Workbook not found: {self.workbook}")
        if self.workbook.suffix.lower() not in {".xlsx", ".xlsm", ".xls"}:
            raise ValueError("Supported Excel formats are .xlsx, .xlsm, and .xls.")
        self.source = pd.read_excel(self.workbook, sheet_name=sheet_name)
        if not isinstance(self.source, pd.DataFrame):
            raise TypeError("Select one worksheet; a single sheet name or index is required.")
        if self.source.empty:
            raise ValueError("The selected worksheet contains no data rows.")
        self.cleaned: pd.DataFrame | None = None
        self.cleaning_summary: dict[str, Any] | None = None
        self.analysis_result: dict[str, Any] | None = None
        self.cleaned_path = self.output_dir / f"{self.workbook.stem}_cleaned.xlsx"

    def profile(self) -> dict[str, Any]:
        """Return compact schema and quality metadata without exposing row-level data."""
        frame = self.cleaned if self.cleaned is not None else self.source
        return {
            "workbook": self.workbook.name,
            "worksheet": str(self.sheet_name),
            "stage": "cleaned" if self.cleaned is not None else "source",
            "rows": len(frame),
            "columns": [str(column) for column in frame.columns],
            "dtypes": {str(column): str(dtype) for column, dtype in frame.dtypes.items()},
            "missing_values": {str(column): int(count) for column, count in frame.isna().sum().items()},
            "duplicate_rows": int(frame.duplicated().sum()),
        }

    def clean(self) -> dict[str, Any]:
        """Clean source once and export a separate Excel workbook."""
        if self.cleaned is not None:
            return self.cleaning_summary or {}
        self.cleaned, self.cleaning_summary = clean_frame(self.source, self.null_strategy)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.cleaned.to_excel(self.cleaned_path, index=False)
        self.cleaning_summary["cleaned_workbook"] = str(self.cleaned_path)
        return self.cleaning_summary

    def analyze(self, target_column: str) -> dict[str, Any]:
        """Run target-centric statistics over the cleaned frame only."""
        if self.cleaned is None:
            raise RuntimeError("Clean the workbook before analyzing a target column.")
        self.analysis_result = analyze_frame(self.cleaned, target_column)
        return self.analysis_result

    def save_results(self, report: str) -> tuple[Path, Path]:
        """Persist machine-readable statistics and the synthesized LLM report."""
        self.output_dir.mkdir(parents=True, exist_ok=True)
        json_path = self.output_dir / "analysis.json"
        report_path = self.output_dir / "analysis.md"
        with json_path.open("w", encoding="utf-8") as output_file:
            json.dump(
                json_safe(
                    {
                        "source_workbook": str(self.workbook),
                        "worksheet": str(self.sheet_name),
                        "cleaning": self.cleaning_summary,
                        "analysis": self.analysis_result,
                    }
                ),
                output_file,
                indent=2,
                ensure_ascii=False,
                allow_nan=False,
            )
        report_path.write_text(report.strip() + "\n", encoding="utf-8")
        return json_path, report_path
