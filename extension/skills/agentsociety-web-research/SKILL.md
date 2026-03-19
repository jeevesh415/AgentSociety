---
name: agentsociety-web-research
description: Perform web research using Miro MCP service.
license: Proprietary. LICENSE.txt has complete terms
---

# Web Research

Perform web research through the external Miro MCP service.

## Quick Start

```bash
# Get PYTHON_PATH from .env
PYTHON_PATH=$(grep "^PYTHON_PATH=" .env | cut -d'=' -f2)
PYTHON_PATH=${PYTHON_PATH:-python3}

python scripts/research.py "latest developments in large language models"
```

## Python Environment Requirement

**This skill requires `agentsociety2` to be installed in the Python environment.**

Use the `PYTHON_PATH` from your `.env` file to ensure the correct Python interpreter is used. See `CLAUDE.md` for details.

## Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| query | string | Yes | Research query (positional argument) |
| --llm | string | No | LLM model name to use |
| --agent | string | No | Agent configuration name |

## What It Does

1. Searches the web using Miro MCP service
2. Synthesizes findings from multiple sources
3. Returns a concise summary

## Use Cases

- Research recent developments in a field
- Compare different approaches or technologies
- Find documentation or examples
- Gather background information for hypotheses

## Prerequisites

Requires Miro MCP service to be accessible.
