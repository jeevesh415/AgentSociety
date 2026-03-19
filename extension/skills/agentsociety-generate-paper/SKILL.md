---
name: agentsociety-generate-paper
description: Generate academic paper PDF from experiment analysis results.
license: Proprietary. LICENSE.txt has complete terms
---

# Generate Paper

Generate academic paper PDF from experiment analysis using the EasyPaper service.

## Quick Start

```bash
# Get PYTHON_PATH from .env
PYTHON_PATH=$(grep "^PYTHON_PATH=" .env | cut -d'=' -f2)
PYTHON_PATH=${PYTHON_PATH:-python3}

python scripts/generate.py --hypothesis-id 1 --experiment-id 1
```

## Python Environment Requirement

**This skill requires `agentsociety2` to be installed in the Python environment.**

Use the `PYTHON_PATH` from your `.env` file to ensure the correct Python interpreter is used. See `CLAUDE.md` for details.

## Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| --hypothesis-id | string | Yes | Hypothesis ID |
| --experiment-id | string | Yes | Experiment ID |
| --workspace | string | No | Workspace path (default: current directory) |
| --target-pages | integer | No | Target page count (default: 6) |
| --template | string | No | Path to LaTeX template .zip file |
| --style | string | No | Style guide name (e.g., 'ICML', 'NeurIPS') |
| --no-review | flag | No | Disable EasyPaper's review loop |
| --output-dir | string | No | Output directory (default: auto-generated) |

## What It Does

1. Gathers context from hypothesis, experiment, and analysis data
2. Builds metadata for paper generation
3. Calls EasyPaper API to generate formatted PDF
4. Saves PDF and LaTeX source files

## Output Files

```
hypothesis_{id}/experiment_{id}/final_paper_{timestamp}/
├── paper.pdf              # Final PDF output
├── metadata.json          # Paper metadata used
└── iteration_*_final/     # LaTeX source files
```

## Prerequisites

1. EasyPaper service must be running and accessible
2. Experiment should have analysis results for better content

## Style Guides

Available styles: `plain`, `ICML`, `COLM`, `NeurIPS`, and others supported by EasyPaper.
