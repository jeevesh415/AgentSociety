---
name: agentsociety-synthesize
description: Synthesize experiment results into research insights and summaries.
license: Proprietary. LICENSE.txt has complete terms
---

# Synthesize

Synthesize experiment results into bilingual (Chinese/English) research summaries.

## Quick Start

```bash
# Get PYTHON_PATH from .env
PYTHON_PATH=$(grep "^PYTHON_PATH=" .env | cut -d'=' -f2)
PYTHON_PATH=${PYTHON_PATH:-python3}

python scripts/synthesize.py --hypothesis-id 1 --experiment-id 1
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
| --instructions | string | No | Additional synthesis instructions |
| --output-dir | string | No | Output directory (default: auto-determined) |

## What It Does

1. Collects data from hypothesis, experiment, and analysis
2. Uses LLM to create cohesive research summaries
3. Generates bilingual reports (Chinese and English)

## Output Files

```
presentation/hypothesis_{id}/experiment_{id}/
├── synthesis_report_zh.md    # Chinese synthesis report
└── synthesis_report_en.md    # English synthesis report
```

## Content Sections

1. Research Question - The hypothesis being tested
2. Methods Summary - Experiment design overview
3. Key Findings - Main results from the experiment
4. Conclusions - Interpretation and implications
5. Future Work - Suggestions for follow-up studies

## Documentation Sync

After synthesis completes, update:
1. **TOPIC.md** - Add synthesis summary to research progress
2. **HYPOTHESIS.md** - Add synthesis link and conclusion
3. **EXPERIMENT.md** - Add synthesis reference
