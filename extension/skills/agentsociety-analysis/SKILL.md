---
name: agentsociety-analysis
description: Analyze experiment data and generate analysis reports.
license: Proprietary. LICENSE.txt has complete terms
---

# Data Analysis

Analyze experiment simulation data and generate comprehensive reports.

## Quick Start

```bash
# Get PYTHON_PATH from .env
PYTHON_PATH=$(grep "^PYTHON_PATH=" .env | cut -d'=' -f2)
PYTHON_PATH=${PYTHON_PATH:-python3}

python scripts/analyze.py --hypothesis-id 1 --experiment-id 1
```

## Python Environment Requirement

**This skill requires `agentsociety2` to be installed in the Python environment.**

Use the `PYTHON_PATH` from your `.env` file to ensure the correct Python interpreter is used. See `CLAUDE.md` for details.

## Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| --hypothesis-id | string | Yes | Hypothesis ID (e.g., '1', '2') |
| --experiment-id | string | Yes | Experiment ID (e.g., '1', '2') |
| --run-id | string | No | Run ID (default: 'run') |
| --workspace | string | No | Workspace path (default: current directory) |
| --output-dir | string | No | Output directory path (default: auto-determined) |

## What It Does

1. Validates experiment data exists
2. Analyzes agent behaviors, interactions, and patterns
3. Generates markdown report with visualizations
4. Creates analysis_summary.json with structured results

## Output Files

```
hypothesis_{id}/experiment_{id}/data/
├── analysis_summary.json    # Structured analysis results
├── report.md                # Detailed analysis report
└── figures/                 # Generated charts and visualizations
```

## Prerequisites

The experiment must have been run with data:
- `hypothesis_{id}/experiment_{id}/run/sqlite.db` must exist

## Documentation Sync

After analysis completes, update:
1. **EXPERIMENT.md** - Add analysis summary, key findings, statistical tests
2. **HYPOTHESIS.md** - Add conclusions and analysis link
3. **TOPIC.md** - Add key findings to research progress (optional)
