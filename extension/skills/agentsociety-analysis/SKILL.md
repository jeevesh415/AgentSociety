---
name: agentsociety-analysis
description: Analyze experiment data and generate analysis reports.
license: Proprietary. LICENSE.txt has complete terms
---

# Data Analysis

Analyze a single experiment's simulation data and generate comprehensive reports with visualizations.

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
| --hypothesis-id | string | Yes | Hypothesis ID (e.g., '1', '2') |
| --experiment-id | string | Yes | Experiment ID (e.g., '1', '2') |
| --workspace | string | No | Workspace path (default: current directory) |

## What It Does

This skill is executed by the unified `AnalysisAgent` sub-agent in `agentsociety2.skills.analysis`, so it can be used both as:
- a VS Code skill workflow (`extension/skills/agentsociety-analysis`)
- a programmatic sub-agent pipeline (`Analyzer`/`AnalysisAgent`)

For complex analysis, it runs as a **multi-stage sub-agent workflow** (not a one-shot call):
- stage 1: context + schema understanding
- stage 2: data-grounded insight generation
- stage 3: tool execution (EDA/statistics/visualization)
- stage 4: **summarize execution results before next iteration**
- stage 5: report generation (bilingual: `report_zh` + `report_en`, each Markdown + HTML)

The analysis follows a **data-first** approach:

1. **Load Context** - Read experiment configuration and status
2. **Understand Data** - Extract database schema, row counts, sample data
3. **Generate Insights** - Create data-grounded insights (not hypothetical)
4. **Run Analysis Tools** - Execute statistical tests, visualizations
5. **Generate Reports** - Produce Markdown and HTML reports

## Output Files

```
presentation/hypothesis_{id}/experiment_{id}/
├── report_zh.md / report_zh.html   # 简体中文报告
├── report_en.md / report_en.html   # English report
├── README.md                    # Output file guide
├── data/
│   ├── analysis_summary.json    # Structured analysis results
│   ├── eda_profile.html         # ydata-profiling output
│   └── eda_sweetviz.html        # sweetviz output
├── charts/                      # Generated charts
└── assets/                      # Report-embedded static resources
```

## EDA Tools Used

| Tool | Output | Purpose |
|------|--------|---------|
| ydata-profiling | `eda_profile.html` | Comprehensive data profile |
| Sweetviz | `eda_sweetviz.html` | Correlation & target analysis |
| Quick stats | Markdown text | pandas.describe() summary |

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
