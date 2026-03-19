---
name: agentsociety-literature-search
description: Search academic literature from remote API and save to workspace papers directory.
license: Proprietary. LICENSE.txt has complete terms
---

# Literature Search

Search academic literature from a remote literature search API and save results to the workspace.

## Quick Start

```bash
# Get PYTHON_PATH from .env
PYTHON_PATH=$(grep "^PYTHON_PATH=" .env | cut -d'=' -f2)
PYTHON_PATH=${PYTHON_PATH:-python3}

python scripts/search.py "social network analysis"
python scripts/search.py "agent-based modeling" --top-k 5
```

## Python Environment Requirement

**This skill requires `agentsociety2` to be installed in the Python environment.**

Use the `PYTHON_PATH` from your `.env` file to ensure the correct Python interpreter is used. See `CLAUDE.md` for details.

## Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| query | string | Yes | Search query (positional argument) |
| --top-k | integer | No | Number of articles to return (default: 3) |
| --no-multi-query | flag | No | Disable multi-query mode (default: enabled) |
| --workspace | string | No | Workspace path (default: current directory) |

## What It Does

1. Queries remote literature search API (LITERATURE_SEARCH_API_URL in .env)
2. Uses multi-query mode to semantically expand your query
3. Saves each article as markdown in `papers/literature/`
4. Updates `papers/literature_index.json`
5. Generates AI summary of findings

## Output Files

```
papers/
├── literature_index.json    # Literature catalog (auto-created/updated)
└── literature/
    ├── article_1_title.md   # Individual article summaries
    └── ...
```

## Prerequisites

Configure the literature search API URL in your `.env` file:
```bash
LITERATURE_SEARCH_API_URL=http://localhost:8002/api/v1/search
```
