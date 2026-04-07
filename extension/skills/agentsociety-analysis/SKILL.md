---
name: agentsociety-analysis
description: Analyze experiment data and generate analysis reports.
license: Proprietary. LICENSE.txt has complete terms
---

# Data Analysis

Analyze experiment data and generate reports. Supports single experiment, batch experiments, and synthesis.

## Quick Start

```bash
# Get PYTHON_PATH from .env
PYTHON_PATH=$(grep "^PYTHON_PATH=" .env | cut -d'=' -f2)
PYTHON_PATH=${PYTHON_PATH:-python3}

$PYTHON_PATH scripts/analyze.py --hypothesis-id 1 --experiment-id 1
```

## Python Environment Requirement

**This skill requires `agentsociety2` to be installed in the Python environment.**

Use the `PYTHON_PATH` from your `.env` file to ensure the correct Python interpreter is used. See `CLAUDE.md` for details.

## Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| --mode | string | No | `single` (default) \| `batch` \| `synthesize` |
| --hypothesis-id | string | single/batch | Hypothesis ID (e.g., '1', '2') |
| --experiment-id | string | single | Experiment ID (e.g., '1', '2') |
| --experiment-ids | string[] | batch/synthesize | Experiment IDs list (default: auto-discover) |
| --hypothesis-ids | string[] | synthesize | Hypothesis IDs list (default: auto-discover) |
| --workspace | string | No | Workspace path (default: current directory) |
| --instructions | string | No | Additional analysis/synthesis instructions |
| --literature-summary | string | No | Optional literature summary to incorporate |

## What It Does

This skill calls `agentsociety2.skills.analysis` (same code as the Python package):

- **Orchestration**: `service.Analyzer` / `run_analysis_workflow`
- **Core loop**: `agents.AnalysisAgent` — data-first insights, **ReAct-style tool rounds** (`executor.AnalysisRunner`), visualization + LLM judges
- **Artifacts**: `output.Reporter` (bilingual MD/HTML); `output.EDAGenerator` (optional EDA / quick stats)
- **LLM wiring**: XML shapes in `llm_contracts.py`; composable Markdown bullets in `instruction_md/` (loaded via `utils.get_analysis_skills`)

For complex analysis, it runs as a **multi-stage workflow** (not one-shot):

- stage 1: load experiment context
- stage 2: `DataReader.read_full_summary()` + data-grounded insights
- stage 3: strategy tools + iterative adjust (EDA / builtins / `code_executor`)
- stage 4: compress/summarize tool history where needed
- stage 5: visualization plan + chart generation
- stage 6: report generation (Markdown + HTML, with retry/judge)

The analysis follows a **data-first** approach:

1. **Load Context** - Read experiment configuration and status
2. **Understand Data** - Extract database schema, row counts, sample data
3. **Generate Insights** - Create data-grounded insights (not hypothetical)
4. **Run Analysis Tools** - Execute statistical tests, visualizations
5. **Generate Reports** - Produce Markdown and HTML reports

## Output Files

```
presentation/hypothesis_{id}/experiment_{id}/
├── report.md                    # Markdown report
├── report.html                  # HTML report (complete document)
├── README.md                    # Output file guide
├── data/
│   ├── analysis_summary.json    # Structured analysis results
│   ├── eda_profile.html         # ydata-profiling (if generated)
│   └── eda_sweetviz.html        # Sweetviz (if generated)
├── charts/                      # Generated charts
└── assets/                      # Report-embedded static resources
```

## EDA (when tools or fallback generate them)

| Source | Output | Notes |
|--------|--------|--------|
| ydata-profiling | `eda_profile.html` | Sampled table via `EDAGenerator` |
| Sweetviz | `eda_sweetviz.html` | Sampled table via `EDAGenerator` |
| Quick stats | Injected into report prompt | Markdown from `DataReader` / `EDAGenerator.generate_quick_stats` |

## Analysis Capabilities

### Statistical Analysis
- Descriptive statistics (mean, median, std, etc.)
- Hypothesis testing (t-test, ANOVA, chi-square)
- Correlation analysis
- Regression (via statsmodels)

### Visualization
- Distribution plots (histogram, KDE, violin)
- Comparison plots (bar, box, swarm)
- Correlation heatmaps
- Time series with confidence bands
- Network graphs (agent interactions)

### Advanced Analysis
- Social network analysis (networkx)
- Temporal dynamics and convergence
- Inequality metrics (Gini coefficient)
- Text/sentiment analysis

## Prerequisites

The experiment must have been run with data:
- `hypothesis_{id}/experiment_{id}/run/sqlite.db` must exist
- The database should contain simulation results

## Comparison with `agentsociety-synthesize`

| Aspect | agentsociety-analysis | agentsociety-synthesize |
|--------|---------------------|------------------------|
| Scope | Single experiment | Multiple experiments/hypotheses |
| Output | `presentation/hypothesis_X/experiment_Y/` | `synthesis/` |
| Purpose | Deep dive into one experiment | Cross-experiment comparison |
| When to use | After each experiment run | After multiple experiments |

## Documentation Sync

After analysis completes, update:
1. **EXPERIMENT.md** - Add analysis summary, key findings, statistical tests
2. **HYPOTHESIS.md** - Add conclusions and analysis link
3. **TOPIC.md** - Add key findings to research progress (optional)
