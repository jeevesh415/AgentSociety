---
name: agentsociety-synthesize
description: Synthesize experiment results into research insights and summaries.
license: Proprietary. LICENSE.txt has complete terms
---

# Synthesize

Synthesize experiment results across multiple hypotheses and experiments into **bilingual** (简体中文 + English) research summaries, each in **Markdown and HTML**.

## Quick Start

```bash
# Get PYTHON_PATH from .env
PYTHON_PATH=$(grep "^PYTHON_PATH=" .env | cut -d'=' -f2)
PYTHON_PATH=${PYTHON_PATH:-python3}

# Auto-discover all hypotheses and experiments
$PYTHON_PATH scripts/synthesize.py

# Or synthesize specific hypotheses
$PYTHON_PATH scripts/synthesize.py --hypothesis-ids 1 2

# Or synthesize specific experiments
$PYTHON_PATH scripts/synthesize.py --hypothesis-ids 1 --experiment-ids 1 2 3
```

## Python Environment Requirement

**This skill requires `agentsociety2` to be installed in the Python environment.**

Use the `PYTHON_PATH` from your `.env` file to ensure the correct Python interpreter is used. See `CLAUDE.md` for details.

## Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| --hypothesis-ids | strings | No | Hypothesis IDs to synthesize (default: auto-discover all) |
| --experiment-ids | strings | No | Experiment IDs to synthesize (default: auto-discover all) |
| --workspace | string | No | Workspace path (default: current directory) |
| --instructions | string | No | Additional synthesis instructions |

## Two Modes

### 1. Auto-Discovery Mode (Recommended)

Run without arguments to automatically discover and synthesize all hypotheses and experiments:

```bash
$PYTHON_PATH scripts/synthesize.py
```

This will:
1. Discover all `hypothesis_*` directories
2. For each hypothesis, discover all `experiment_*` directories
3. Run analysis on each discovered experiment
4. Generate cross-hypothesis synthesis report

### 2. Targeted Mode

Specify particular hypotheses or experiments:

```bash
# Synthesize only hypotheses 1 and 2
$PYTHON_PATH scripts/synthesize.py --hypothesis-ids 1 2

# Synthesize only experiments 1 and 2 under hypothesis 1
$PYTHON_PATH scripts/synthesize.py --hypothesis-ids 1 --experiment-ids 1 2
```

## What It Does

1. **Per-Experiment Analysis**: Analyzes each experiment in scope
2. **Hypothesis Summaries**: Aggregates results per hypothesis
3. **Cross-Hypothesis Synthesis**: Compares and synthesizes across hypotheses
4. **Report Generation**: Creates bilingual synthesis reports (`_zh` + `_en`, each `.md` + `.html`; primary `synthesis_report_{ts}.md/.html` are Chinese copies)

## Output Files

```
synthesis/
├── synthesis_report_{timestamp}.md       # Chinese MD (copy of _zh)
├── synthesis_report_{timestamp}.html    # Chinese HTML (copy of _zh)
├── synthesis_report_{timestamp}_zh.md / _zh.html
├── synthesis_report_{timestamp}_en.md / _en.html
└── assets/
    └── synthesis_comparison.png         # Comparison chart
```

## Content Sections

1. **Synthesis Strategy** - How the synthesis was approached
2. **Cross-Hypothesis Analysis** - Comparative narrative
3. **Comparative Insights** - Key differences and similarities
4. **Unified Conclusions** - Overall findings
5. **Recommendations** - Suggestions for future work
6. **Best Hypothesis** - If applicable, the best performing hypothesis

## Comparison with `agentsociety-analysis`

| Aspect | agentsociety-analysis | agentsociety-synthesize |
|--------|---------------------|------------------------|
| Scope | Single experiment | Multiple experiments/hypotheses |
| Output | `presentation/hypothesis_X/experiment_Y/` | `synthesis/` |
| Purpose | Deep dive into one experiment | Cross-experiment comparison |
| When to use | After each experiment run | After multiple experiments |

## Prerequisites

- At least one experiment should have been run
- For best results, run `agentsociety-analysis` on each experiment first

## Documentation Sync

After synthesis completes, update:
1. **TOPIC.md** - Add synthesis summary to research progress
2. **HYPOTHESIS.md** - Add synthesis link and conclusions
3. **EXPERIMENT.md** - Add synthesis reference
