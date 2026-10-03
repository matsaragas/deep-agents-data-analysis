"""Deep Agent supervisor and the specialized cleaning/analysis subagents."""

from __future__ import annotations

import json
from pathlib import Path

from deepagents import create_deep_agent
from deepagents.backends.filesystem import FilesystemBackend
from deepagents.middleware import FilesystemMiddleware
from langchain.chat_models import init_chat_model

from excel_analyst.analysis import json_safe
from excel_analyst.workspace import AnalysisWorkspace

SKILLS_DIR = Path(__file__).resolve().parents[2] / "skills"
READ_ONLY_SKILL_FILES = ["read_file", "ls"]


def build_supervisor(workspace: AnalysisWorkspace, model_name: str):
    """Build the Deep Agent with focused tools, skills, and sequential delegation."""
    model = init_chat_model(model_name, temperature=0)
    backend = FilesystemBackend(root_dir=str(SKILLS_DIR), virtual_mode=True)
    def read_only_filesystem() -> FilesystemMiddleware:
        return FilesystemMiddleware(backend=backend, tools=READ_ONLY_SKILL_FILES)

    def get_dataset_profile() -> str:
        """Inspect workbook columns and missing/duplicate counts without returning raw rows."""
        return json.dumps(json_safe(workspace.profile()), indent=2, ensure_ascii=False)

    def clean_excel_data() -> str:
        """Remove duplicates, convert safe numeric strings, apply the selected null policy, and save a clean copy."""
        return json.dumps(json_safe(workspace.clean()), indent=2, ensure_ascii=False)

    def analyze_target(target_column: str) -> str:
        """Compute target statistics, correlations, and categorical associations on cleaned data."""
        if workspace.cleaned is None:
            raise RuntimeError("Cleaning has not completed. Run the data-cleaner first.")
        return json.dumps(
            json_safe(workspace.analyze(target_column)),
            indent=2,
            ensure_ascii=False,
            allow_nan=False,
        )

    cleaner_skills = ["/cleaner/"]
    analyst_skills = ["/analyst/"]
    subagents = [
        {
            "name": "data-cleaner",
            "description": (
                "Cleans the currently loaded Excel worksheet: removes exact duplicate rows, "
                "converts safely parseable numeric strings, applies the configured null policy, "
                "and exports a cleaned workbook. Always run this before target analysis."
            ),
            "system_prompt": (
                "You are the data-cleaning specialist. Read and follow the cleaning skill, "
                "then call clean_excel_data exactly once. Report the row loss, null policy, "
                "numeric conversions, and output workbook. Do not analyze the target or expose rows."
            ),
            "tools": [clean_excel_data],
            "skills": cleaner_skills,
            "middleware": [read_only_filesystem()],
        },
        {
            "name": "target-analyst",
            "description": (
                "Performs statistical analysis for the user's specified target column using "
                "the cleaned workbook, including correlations and categorical associations."
            ),
            "system_prompt": (
                "You are a statistical analyst. Read and follow the analysis skill. Use only "
                "the analyze_target tool to compute results; never estimate statistics from "
                "prompt context. Explain association rather than causation, include effect sizes "
                "and caveats, and return concise findings without raw records."
            ),
            "tools": [analyze_target],
            "skills": analyst_skills,
            "middleware": [read_only_filesystem()],
        },
    ]

    return create_deep_agent(
        model=model,
        tools=[get_dataset_profile],
        subagents=subagents,
        backend=backend,
        skills=cleaner_skills + analyst_skills,
        middleware=[read_only_filesystem()],
        system_prompt=(
            "You coordinate Excel data analysis. For each user request, first call "
            "get_dataset_profile. Create a cleaning plan and present it to the user asking for " 
            "approval. If the user don't agree with a plan ask for user input. If the user agrees, " 
            "then you MUST delegate to data-cleaner and wait for its "
            "successful result. Only after cleaning, delegate to target-analyst with the exact "
            "requested target column. Do not call target analysis before cleaning, do not use "
            "the general-purpose subagent, and do not compute statistics yourself. Synthesize "
            "the tool-backed findings in a clear report with cleaning impact, strongest "
            "associations, practical interpretation, limitations, and follow-up suggestions. "
            "Never claim association proves causation."
        ),
        name="excel-analysis-supervisor",
    )
