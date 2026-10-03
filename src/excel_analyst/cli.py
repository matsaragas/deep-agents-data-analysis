"""Command-line entry point for workbook analysis."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

from excel_analyst.agents import build_supervisor
from excel_analyst.workspace import AnalysisWorkspace


def _sheet_value(value: str) -> str | int:
    return int(value) if value.isdecimal() else value


def _message_text(value: Any) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        return "\n".join(
            str(block.get("text", "")) if isinstance(block, dict) else str(block)
            for block in value
        )
    return str(value)


def make_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="excel-analyst",
        description="Clean an Excel worksheet and analyze a target variable using Deep Agents.",
    )
    parser.add_argument("workbook", type=Path, help="Input .xlsx, .xlsm, or .xls workbook")
    parser.add_argument("--target", required=True, help="Exact target column name to analyze")
    parser.add_argument(
        "--sheet",
        type=_sheet_value,
        default=0,
        help="Worksheet name or zero-based index (default: first worksheet)",
    )
    parser.add_argument(
        "--null-strategy",
        choices=("drop_rows", "keep"),
        default="drop_rows",
        help="How to handle missing values (default: drop rows with any missing cell)",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        help="Output folder (default: ./outputs/<workbook-name>)",
    )
    parser.add_argument(
        "--model",
        default=None,
        help="LangChain model identifier (default: OPENAI_MODEL or openai:gpt-4.1-mini)",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    load_dotenv()
    parser = make_parser()
    args = parser.parse_args(argv)
    workbook = args.workbook.expanduser().resolve()
    output_dir = args.output_dir or Path("outputs") / workbook.stem
    model_name = args.model or os.getenv("OPENAI_MODEL", "openai:gpt-4.1-mini")

    if model_name.startswith("openai:") and not os.getenv("OPENAI_API_KEY"):
        parser.error("OPENAI_API_KEY is not set. Copy .env.example to .env and add your key.")

    try:
        workspace = AnalysisWorkspace(
            workbook=workbook,
            output_dir=output_dir,
            sheet_name=args.sheet,
            null_strategy=args.null_strategy,
        )
        supervisor = build_supervisor(workspace, model_name)
        prompt = (
            f"Analyze the Excel workbook {workbook.name}, worksheet {args.sheet!r}. "
            f"The target variable is exactly {args.target!r}. "
            f"Use null strategy {args.null_strategy!r}. Follow the required ordered workflow: "
            "profile, data-cleaner, then target-analyst. Report data cleaning impacts and "
            "target-focused statistical insights with appropriate caveats."
        )
        result = supervisor.invoke({"messages": [{"role": "user", "content": prompt}]})
        messages = result.get("messages", [])
        report = _message_text(messages[-1].content) if messages else "No report was returned."
        json_path, report_path = workspace.save_results(report)
    except Exception as error:  # noqa: BLE001 - surface provider and workbook errors cleanly
        print(f"Analysis failed: {error}", file=sys.stderr)
        return 1

    print(report)
    print(f"\nCleaned workbook: {workspace.cleaned_path}")
    print(f"Analysis report:  {report_path}")
    print(f"Analysis data:    {json_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
