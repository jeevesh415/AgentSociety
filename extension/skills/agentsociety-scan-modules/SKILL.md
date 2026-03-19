---
name: agentsociety-scan-modules
description: Scan and query available agent and environment classes in the AgentSociety2 workspace.
license: Proprietary. LICENSE.txt has complete terms
---

# Scan Modules

Scan and query available agent classes and environment modules in the AgentSociety2 workspace.

## Quick Start

```bash
# Get PYTHON_PATH from .env
PYTHON_PATH=$(grep "^PYTHON_PATH=" .env | cut -d'=' -f2)
PYTHON_PATH=${PYTHON_PATH:-python3}

# List all modules (medium detail)
python scripts/scan_modules.py list

# List only module names (short mode)
python scripts/scan_modules.py list --short

# Get detailed info about a specific module
python scripts/scan_modules.py info --type agent --name PersonAgent
```

## Python Environment Requirement

**This skill requires `agentsociety2` to be installed in the Python environment.**

Use the `PYTHON_PATH` from your `.env` file to ensure the correct Python interpreter is used. See `CLAUDE.md` for details.

## Actions

### list
List all available modules with optional filtering.

```bash
python scripts/scan_modules.py list [--type TYPE] [--custom-only] [--short|--full] [--json] [--workspace PATH]
```

**Options:**
- `--type`: Filter by type (`agent` or `env`)
- `--custom-only`: Show only custom modules
- `--short`, `-s`: Show only module names
- `--full`, `-f`: Show complete descriptions
- `--json`: Output in JSON format

### info
Get detailed information about a specific module.

```bash
python scripts/scan_modules.py info --type TYPE --name NAME [--json] [--workspace PATH]
```

Shows: full description, constructor parameters, file location, import path, prefill parameters.

### search
Search for modules by keyword in name or description.

```bash
python scripts/scan_modules.py search --keyword KEYWORD [--type TYPE] [--json] [--workspace PATH]
```

### export
Export all module information to a JSON file.

```bash
python scripts/scan_modules.py export --output FILE [--workspace PATH]
```

### validate
Validate that a module can be imported and instantiated.

```bash
python scripts/scan_modules.py validate --type TYPE --name NAME [--workspace PATH]
```

## Module Locations

- **Built-in Agents**: `packages/agentsociety2/agentsociety2/agent/person.py`
- **Built-in Envs**: `packages/agentsociety2/agentsociety2/contrib/env/`
- **Contrib Agents**: `packages/agentsociety2/agentsociety2/contrib/agent/`
- **Custom Modules**: `packages/agentsociety2/agentsociety2/custom/agents/` and `custom/envs/`

## Common Use Cases

### Finding suitable environment for a simulation
```bash
python scripts/scan_modules.py search --keyword "social" --type env
python scripts/scan_modules.py info --type env --name SimpleSocialSpace
```

### Checking available custom modules
```bash
python scripts/scan_modules.py list --custom-only
```

### Preparing for experiment configuration
```bash
python scripts/scan_modules.py export --output user_data/modules.json
```

## Module Type Identifiers

Use the **class name** as the type identifier:

| Class Name | Type Identifier |
|------------|-----------------|
| PersonAgent | `PersonAgent` |
| SimpleSocialSpace | `SimpleSocialSpace` |
| PrisonersDilemmaEnv | `PrisonersDilemmaEnv` |
