---
name: agentsociety-create-dataset
description: Guide users to create, validate, package, and upload datasets to the agentsociety2-web platform.
license: Proprietary. LICENSE.txt has complete terms
---

# Create Dataset

Guide users through creating a dataset compatible with agentsociety2-web, validating it, packaging it as a ZIP, and uploading it to the platform.

## Quick Start

```bash
python scripts/create.py login
python scripts/create.py init my-survey --category surveys --description "A survey dataset" --author "Your Name"
# ... add data files under my-survey/data/ ...
python scripts/create.py validate my-survey/
python scripts/create.py pack my-survey/
python scripts/create.py upload my-survey.zip
python scripts/create.py submit my-survey
```

## Workflow

Follow this exact sequence:

1. **Login** (one-time): `python scripts/create.py login`
   - Opens browser for Casdoor Device Code Flow authentication
   - Credentials saved to `~/.agentsociety/credentials.json`

2. **Initialize**: `python scripts/create.py init <name> --category <category> --description <desc> --author <name>`
   - Creates directory with README.md template, dataset.json, and data/
   - Category options: `agent_profiles`, `surveys`, `experiments`, `literature`, `simulation_results`, `other`

3. **Add data**: Guide user to place CSV/JSON/Parquet files under `<name>/data/`

4. **Edit README.md**: Fill in the Data Format, Columns, and Usage sections to describe the dataset

5. **Edit dataset.json**: Ensure id (slug), description, tags are correct

6. **Validate**: `python scripts/create.py validate <path>`
   - Checks README.md, dataset.json, data/, size limits

7. **Package**: `python scripts/create.py pack <dir>`
   - Creates `<dir>.zip`

8. **Upload**: `python scripts/create.py upload <zip>`
   - Creates dataset on platform and uploads ZIP
   - Requires prior login

9. **Submit**: `python scripts/create.py submit <dataset_id>`
   - Submits for admin review

## Commands Reference

| Command | Auth | Description |
|---------|:----:|-------------|
| `login` | No | Casdoor Device Code Flow authentication |
| `logout` | No | Clear saved credentials |
| `init <name>` | No | Create dataset directory structure |
| `validate <path>` | No | Validate dataset dir or ZIP |
| `pack <dir>` | No | Package directory into ZIP |
| `upload <zip>` | Yes | Upload to agentsociety2-web |
| `submit <dataset_id>` | Yes | Submit for admin review |

## Dataset Format

A valid dataset is a directory containing:

```
<name>/
├── README.md         # Required. Describes the dataset.
├── dataset.json      # Required. Metadata (id, name, description, category, etc.)
└── data/             # Recommended. Dataset files (CSV, JSON, etc.)
    ├── file1.csv
    └── file2.json
```

### dataset.json Schema

```json
{
  "id": "lowercase-slug-with-dashes",
  "name": "Human-readable name",
  "description": "What this dataset contains",
  "category": "surveys",
  "version": "1.0.0",
  "tags": ["tag1", "tag2"],
  "author": "Author Name",
  "license": "CC BY 4.0"
}
```

**Constraints:**
- `id`: must match `^[a-z0-9_-]+$`, must be unique on the platform
- `category`: one of `agent_profiles`, `surveys`, `experiments`, `literature`, `simulation_results`, `other`
- Total package size: max 2GB

**Note on metadata alignment:** The `dataset.json` fields are sent directly to the backend API during `upload`. After downloading via `agentsociety-use-dataset`, the data is stored in a normalized `metadata.json` with additional fields (`source`, `installed_at`, `package_size_bytes`). The core fields (`id`, `name`, `version`, etc.) are shared between both formats.

## Defaults

| Setting | Value |
|---------|-------|
| Casdoor URL | `https://login.fiblab.net` |
| Backend URL | `https://agentsociety2.fiblab.net` |
| Client ID | `7ffcbfe4ae0fcb2c0d63` |
