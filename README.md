# Excel Deep Agent Analyst

An Excel analysis starter built with **LangChain Deep Agents**. A supervisor coordinates two specialized subagents and reusable skills:

1. **data-cleaner** removes exact duplicate rows, safely converts numeric strings, handles missing values, and exports a cleaned workbook.
2. **target-analyst** computes target-centered descriptive statistics and associations using deterministic pandas/SciPy tools.

The LLM coordinates and explains the results; it does not calculate statistics from a sample. The analysis supports numeric and categorical targets and avoids presenting correlation as causation.

## Setup

Requires Python 3.11 or later.

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev,ui]'
cp .env.example .env
```

Add your provider key to `.env`. The default model is `openai:gpt-4.1-mini`, configured through `OPENAI_API_KEY`; you can override it with `OPENAI_MODEL` or `--model` if the corresponding LangChain provider integration is installed.

## Test with Deep Agents UI

The repo exposes the supervisor as a LangGraph Server graph named `excel-analyst` in [langgraph.json](langgraph.json). By default, the UI graph uses `examples/sample_sales.xlsx` and the `Sales` worksheet. The workbook stays on the Python server; send a chat message such as “Analyze Revenue and explain which fields are most associated with it.”

Start the agent API from this repository:

```bash
.venv/bin/langgraph dev
```

Then in a second terminal, run the UI project separately (the UI repository is archived/read-only):

```bash
git clone https://github.com/langchain-ai/deep-agents-ui.git ../deep-agents-ui
cd ../deep-agents-ui
yarn install
yarn dev
```

Open `http://localhost:3000` and connect to deployment URL `http://127.0.0.1:2024` with assistant ID `excel-analyst`. The local LangGraph Server also provides its own Studio UI URL at startup, if you prefer not to run the archived frontend.

To test another workbook, set `EXCEL_WORKBOOK` to its absolute path (or a path relative to the repository), set `EXCEL_SHEET` to a worksheet name/index if needed, and restart the API. `EXCEL_NULL_STRATEGY` accepts `drop_rows` or `keep`. These are server environment settings; they are not file-upload controls in the UI. Each server process holds one workbook workspace, so restart it after changing the workbook.

## Run

Try the included synthetic workbook first:

```bash
excel-analyst examples/sample_sales.xlsx --sheet Sales --target Revenue
```

The [sample workbook](examples/sample_sales.xlsx) has 16 rows, including one exact duplicate and one missing value. `Unit_Price` and `Revenue` use currency-formatted strings so the cleaner's numeric conversion is exercised. The default cleaning policy should leave 14 complete rows.

For your own workbook:

```bash
excel-analyst path/to/workbook.xlsx --target "Sales"
```

Select a worksheet by name or zero-based index and choose a null policy:

```bash
excel-analyst path/to/workbook.xlsx --sheet "Data" --target "Revenue" --null-strategy drop_rows
```

Options:

- `--sheet`: worksheet name or zero-based index; defaults to the first sheet.
- `--target`: exact target column name (required).
- `--null-strategy`: `drop_rows` (default) drops any row with a missing cell; `keep` retains nulls. No imputation is performed.
- `--output-dir`: output directory; defaults to `outputs/<workbook-name>`.
- `--model`: model identifier in LangChain `provider:model` format.

The original workbook is never overwritten. The run produces:

- `<workbook>_cleaned.xlsx` — transformed worksheet copy.
- `analysis.md` — synthesized findings and caveats.
- `analysis.json` — machine-readable cleaning summary and statistical results.

## Statistical methods

- **Numeric target:** Pearson's $r$ (linear association), Spearman's $\rho$ (rank/monotonic association), and one-way ANOVA / $\eta^2$ for categorical predictors.
- **Categorical target:** one-way ANOVA / $\eta^2$ for numeric predictors; chi-square and bias-corrected Cramer's $V$ for categorical predictors.
- Target summaries include distribution statistics, class counts, and an IQR-based outlier share when relevant.
- Categorical association tests omit predictors/targets with more than 20 categories. Reported p-values are exploratory and unadjusted for multiple comparisons.

These are univariate associations, not causal explanations. Complete-case deletion can remove substantial data or introduce bias; inspect the cleaning summary and consider `--null-strategy keep` when appropriate.

## Skills and tools

Skills under `skills/cleaner/` and `skills/analyst/` provide focused cleaning and analysis procedures. The supervisor loads both skill libraries; each custom subagent receives only its relevant library through Deep Agents' skill middleware. Agent filesystem access is read-only and scoped to the skills directory.

Custom tools perform workbook profiling, deterministic cleaning/export, and target analysis. The cleaner and analyst receive minimal separate toolsets and share the same per-run in-memory workspace, ensuring analysis follows cleaning.

## Tests

```bash
pytest
```