"""LangGraph Server entry point for the Deep Agents UI demo."""

from __future__ import annotations

import os
import sys
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SOURCE_ROOT = PROJECT_ROOT / "src"
if str(SOURCE_ROOT) not in sys.path:
    sys.path.insert(0, str(SOURCE_ROOT))

from excel_analyst.agents import build_supervisor
from excel_analyst.workspace import AnalysisWorkspace

load_dotenv(PROJECT_ROOT / ".env")


def _sheet_from_environment(value: str) -> str | int:
    return int(value) if value.isdecimal() else value


workbook_value = os.getenv("EXCEL_WORKBOOK", "examples/sample_sales.xlsx")
workbook_path = Path(workbook_value).expanduser()
if not workbook_path.is_absolute():
    workbook_path = PROJECT_ROOT / workbook_path

output_value = os.getenv("EXCEL_OUTPUT_DIR", "outputs/ui-demo")
output_path = Path(output_value).expanduser()
if not output_path.is_absolute():
    output_path = PROJECT_ROOT / output_path

workspace = AnalysisWorkspace(
    workbook=workbook_path,
    output_dir=output_path,
    sheet_name=_sheet_from_environment(os.getenv("EXCEL_SHEET", "Sales")),
    null_strategy=os.getenv("EXCEL_NULL_STRATEGY", "drop_rows"),
)
agent = build_supervisor(
    workspace,
    os.getenv("OPENAI_MODEL", "openai:gpt-4.1-mini"),
)
