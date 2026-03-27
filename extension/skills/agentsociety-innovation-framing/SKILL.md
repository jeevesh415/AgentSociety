---
name: agentsociety-innovation-framing
description: Frame innovation directions from literature search results and write them back into TOPIC.md.
license: Proprietary. LICENSE.txt has complete terms
---

# Innovation Framing

Synthesize literature search results into a concrete innovation framing for the current research topic, then rewrite `TOPIC.md` as an updated topic brief.

## Quick Start

```bash
# Get PYTHON_PATH from .env
PYTHON_PATH=$(grep "^PYTHON_PATH=" .env | cut -d'=' -f2)
PYTHON_PATH=${PYTHON_PATH:-python3}

# Frame innovation directions from the current literature index
$PYTHON_PATH scripts/frame.py

# Limit to the literature results for a specific search query
$PYTHON_PATH scripts/frame.py --query "social influence diffusion"

# Add a custom focus for the framing
$PYTHON_PATH scripts/frame.py --focus "强调可通过AgentSociety2仿真验证的社会机制"
```

## Python Environment Requirement

**This skill requires `agentsociety2` to be installed in the Python environment.**

Use the `PYTHON_PATH` from your `.env` file to ensure the correct Python interpreter is used. See `CLAUDE.md` for details.

## Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| --workspace | string | No | Workspace path (default: current directory) |
| --query | string | No | Restrict framing to literature entries associated with a specific literature-search query |
| --focus | string | No | Extra instruction for how the innovation framing should be oriented |
| --top-k | integer | No | Number of literature entries to use as evidence (default: 6) |
| --json | flag | No | Output machine-readable JSON summary |

## What It Does

1. Loads `papers/literature_index.json`
2. Selects the most relevant literature entries
3. Reads the corresponding saved literature markdown files
4. Uses the configured LLM to derive:
   - current problem framing
   - literature tensions and gaps
   - candidate innovation angles
   - hypothesis and experiment implications
   - next research actions
5. If the current literature library is insufficient to understand the field state, it can trigger an additional literature search round automatically
6. Rewrites `TOPIC.md` as an updated topic document

## Output

The skill rewrites `TOPIC.md` in place while preserving a fixed heading structure:

```md
# <Research Title>

## Description

## Research Gap

## Innovation Direction

## Candidate Hypotheses

## Next Steps
```

## Prerequisites

- Run `agentsociety-literature-search` first so that `papers/literature_index.json` exists
- Ensure the saved literature markdown files still exist under `papers/`

## Coverage Policy

If the skill judges that the current literature library is still too thin to support a reliable innovation framing, it may continue by invoking the literature-search capability again with supplemental queries before updating `TOPIC.md`.

## Recommended Workflow

1. `agentsociety-literature-search`
2. `agentsociety-innovation-framing`
3. Review the updated `TOPIC.md`
4. `agentsociety-hypothesis add`

## Documentation Sync

After framing completes:
1. Keep `TOPIC.md` as the canonical topic + innovation framing document
2. Use the generated framing to guide downstream hypothesis and experiment design
