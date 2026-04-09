---
name: agentsociety-use-dataset
description: Search, download, and inspect datasets from the agentsociety2-web public API. Progressive README-first exploration pattern. Package-manager-style listing with local/remote views.
license: Proprietary. LICENSE.txt has complete terms
---

# Use Dataset

Search, download, and inspect datasets from the agentsociety2-web platform. All operations use the public API — no authentication required.

## Core Principle: README-First Exploration

**Always read the README before operating on dataset contents.** The README describes the data format, column semantics, units, and usage guidance. Skipping this step leads to misinterpretation.

Follow this progressive exploration pattern:

1. **List** → see what's available and what's installed
2. **Search** → find relevant datasets by category/tags
3. **Read README** → understand the dataset before downloading
4. **Download** → only when you know it's what you need
5. **Inspect files** → read specific files to understand structure
6. **Use in research** → incorporate into analysis or experiments

## Quick Start

```bash
# See all datasets (local + remote)
python scripts/use.py list --all

# Search by category
python scripts/use.py search --category surveys

# Read README before downloading
python scripts/use.py readme <dataset_id>

# Download
python scripts/use.py download <dataset_id>

# Inspect files
python scripts/use.py cat <dataset_id> data/survey.csv
```

## Commands

| Command | Auth | Description |
|---------|:----:|-------------|
| `list` | No | List datasets (local by default, `--all` for merged, `--remote` for remote) |
| `list-installed` | No | Alias for `list` (backward compat) |
| `search` | No | List/search available datasets with filters |
| `info <id>` | No | Show dataset metadata (local + remote merged) |
| `readme <id>` | No | Display dataset README |
| `files <id>` | No | List dataset file tree |
| `download <id>` | No | Download and extract dataset |
| `cat <id> <path>` | No | Read file content from local dataset |

## Package-Manager-Style Listing

### List all datasets (local + remote)

```bash
python scripts/use.py list --all
```

Output shows a merged view with status:
```
ID                  Name                     Category    Version   Status
my-survey           My Survey                surveys     1.0.0     installed
agent-demographics  Agent Demographics       agent_prof  2.0.0     outdated (local: 1.0.0)
weather-data        Weather Station Data     simulation  1.0.0     available
```

Status values:
- **installed** — local version matches remote
- **outdated (local: X.Y.Z)** — remote has a newer version
- **newer (local: X.Y.Z)** — local version is ahead of remote
- **available** — remote only, not yet downloaded
- **installed (offline)** — local only, remote unreachable

### List local only

```bash
python scripts/use.py list
python scripts/use.py list-installed
```

### List remote only

```bash
python scripts/use.py list --remote
```

### Info with version comparison

```bash
python scripts/use.py info <dataset_id>
```

Shows remote metadata by default. If locally installed and outdated, displays a warning with update command.

## Metadata Format

Downloaded datasets store normalized `metadata.json` aligned with the API schema:

```json
{
  "id": "dataset-slug",
  "name": "Display Name",
  "description": "...",
  "category": "surveys",
  "version": "1.0.0",
  "tags": ["tag1"],
  "author": "Author",
  "license": "CC BY 4.0",
  "source": "remote",
  "installed_at": "2026-04-09T12:00:00Z",
  "package_size_bytes": 1024,
  "created_at": "2026-04-08T10:00:00Z",
  "updated_at": "2026-04-09T08:00:00Z"
}
```

## Workflow

### Step 1: Browse

```bash
python scripts/use.py list --all
python scripts/use.py search --category agent_profiles
python scripts/use.py search --tags survey,demographic --limit 10
```

### Step 2: Read the README (IMPORTANT)

```bash
python scripts/use.py readme <dataset_id>
```

The README tells you:
- What the dataset contains
- File formats and schemas
- Column definitions and units
- How to use it correctly

**Do not skip this step.** Understanding the README prevents misinterpreting column types, units, and semantics.

### Step 3: Download

```bash
python scripts/use.py download <dataset_id>
python scripts/use.py download <dataset_id> --output ./my-data/
```

Downloads and extracts to `datasets/<dataset_id>/`. Automatically shows the README and file list.

### Step 4: Inspect Files

```bash
python scripts/use.py cat <dataset_id> data/survey.csv
python scripts/use.py cat <dataset_id> data/config.json
```

Start with small files or just the headers to understand structure before loading full data.

### Step 5: Check for Updates

```bash
python scripts/use.py list --all
python scripts/use.py info <dataset_id>
```

## Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `--server` | string | `https://agentsociety2.fiblab.net` | Backend API URL |
| `--output` | string | `./datasets/` | Download output directory |
| `--datasets-dir` | string | `./datasets/` | Local datasets directory |
| `--category` | string | — | Filter by category |
| `--tags` | string | — | Comma-separated tag filter |
| `--limit` | int | 20 | Max search results |
| `--skip` | int | 0 | Pagination offset |
| `--all` | flag | false | Show merged local+remote view |
| `--remote` | flag | false | Show remote datasets only |

## Defaults

| Setting | Value |
|---------|-------|
| Backend URL | `https://agentsociety2.fiblab.net` |
| Local datasets dir | `./datasets/` |
