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
python scripts/search.py "agent-based modeling" --limit 5
python scripts/search.py "deep learning" --year-from 2020 --year-to 2024
```

## Python Environment Requirement

**This skill requires `agentsociety2` to be installed in the Python environment.**

Use the `PYTHON_PATH` from your `.env` file to ensure the correct Python interpreter is used. See `CLAUDE.md` for details.

## Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| query | string | Yes | Search query (positional argument) |
| --limit | integer | No | Number of articles to return (default: 10) |
| --year-from | integer | No | Filter by publication year (start) |
| --year-to | integer | No | Filter by publication year (end) |
| --workspace | string | No | Workspace path (default: current directory) |
| --multi-query | flag | No | Enable multi-query mode (split complex queries into subtopics) |

## What It Does

1. Queries remote literature search API (LITERATURE_SEARCH_API_URL in .env)
2. Searches **all available data sources by default** (local, arXiv, CrossRef, OpenAlex)
3. Saves each article as markdown in `papers/literature/`
4. Updates `papers/literature_index.json`
5. Generates AI summary of findings

## Data Sources

The service searches **all sources by default** when `sources` is not specified:

| Source | Description | Content Type |
|--------|-------------|--------------|
| local | RAGFlow local knowledge base | Imported full-text documents |
| arxiv | arXiv preprint platform | Physics, Math, CS, etc. |
| crossref | DOI metadata database | Journal paper metadata |
| openalex | OpenAlex academic graph | 250M+ academic papers |

Local knowledge base results are always displayed first in the response.

## Output Files

```
papers/
├── literature_index.json    # Literature catalog (auto-created/updated)
└── literature/
    ├── article_1_title.md   # Individual article summaries
    └── ...
```

## Prerequisites

Configure the literature search API in your `.env` file:
```bash
LITERATURE_SEARCH_API_URL=http://localhost:8008/api/search
LITERATURE_SEARCH_API_KEY=lit-your-api-key-here
```

Or configure via the VSCode extension settings page:
1. Open the extension configuration page
2. Find the "文献检索" (Literature Search) card
3. Enter API URL and API Key
4. Click "验证配置" (Validate Config) to verify the connection

## Validation

The "验证配置" button performs two checks:
1. **Health Check**: Verifies the service is running (`/health` endpoint)
2. **Auth Check**: Validates the API Key (`/api/stats` endpoint)

Successful validation will show available data sources.

## API Response Fields

Each article contains:
- `title`: Article title
- `authors`: Author list
- `abstract`: Article abstract
- `year`: Publication year
- `journal`: Journal name
- `doi`: DOI identifier
- `url`: Original link
- `score`: Relevance score
- `source`: Data source (local/arxiv/crossref/openalex)

## Advanced Usage

### Filter by Year Range
```bash
python scripts/search.py "machine learning" --year-from 2020 --year-to 2024
```

### Limit Results
```bash
python scripts/search.py "neural networks" --limit 5
```

### Multi-Query Mode
Enable multi-query mode to automatically split complex queries into subtopics for broader coverage:
```bash
python scripts/search.py "social norms and cooperation in game theory" --multi-query
```

This is useful for complex topics that span multiple research areas. The system will:
1. Analyze the query using LLM
2. Split it into 2-4 meaningful subtopics
3. Search each subtopic in parallel
4. Merge and deduplicate results
