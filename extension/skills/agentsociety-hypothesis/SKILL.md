---
name: agentsociety-hypothesis
description: Manage research hypotheses with add, get, list, delete actions.
license: Proprietary. LICENSE.txt has complete terms
---

# Hypothesis Management

Manage research hypotheses for AgentSociety experiments. Each hypothesis defines experiment groups and specifies required agent classes and environment modules.

## Quick Start

```bash
# 1. First, discover available modules (use scan-modules skill)
python scripts/scan_modules.py list --short

# 2. Add a new hypothesis
python scripts/hypothesis.py add \
  --description "Agents with higher social capital have more influence" \
  --rationale "Social capital theory suggests..." \
  --groups '{"name":"control","group_type":"control","description":"Baseline"}' \
           '{"name":"treatment","group_type":"treatment","description":"High social capital"}' \
  --agent-classes PersonAgent \
  --env-modules SimpleSocialSpace GlobalInformationEnv
```

## Python Environment Requirement

**This skill requires `agentsociety2` to be installed in the Python environment.**

Use the `PYTHON_PATH` from your `.env` file to ensure the correct Python interpreter is used. See `CLAUDE.md` for details.

## Module Selection

**CRITICAL**: Every hypothesis MUST specify at least:
- **One agent class** (e.g., `PersonAgent`, `LLMDonorAgent`)
- **One environment module** (e.g., `SimpleSocialSpace`, `GlobalInformationEnv`)

Use the **scan-modules** skill to discover available modules:
```bash
# List all available modules
python scripts/scan_modules.py list --short

# Get details about a specific module
python scripts/scan_modules.py info --type agent --name PersonAgent
```

## Actions

### list

### list
List all hypotheses in the workspace.

```bash
python scripts/hypothesis.py list [--workspace PATH] [--json]
```

### add
Add a new hypothesis with experiment groups.

```bash
python scripts/hypothesis.py add \
  --description TEXT \
  --rationale TEXT \
  --groups JSON... \
  --agent-classes TYPE... \
  --env-modules TYPE... \
  [--workspace PATH] \
  [--json]
```

**Group JSON Format:**
```json
{
  "name": "treatment",
  "group_type": "treatment",
  "description": "Agents with high social capital scores",
  "agent_selection_criteria": "agents whose social_connections > median"
}
```

### get
Get details of a specific hypothesis.

```bash
python scripts/hypothesis.py get --hypothesis-id ID [--workspace PATH] [--json]
```

### delete
Delete a hypothesis and its folder.

```bash
python scripts/hypothesis.py delete --hypothesis-id ID [--workspace PATH] [--json]
```

## Module Combinations

### For Social Simulation
```
--agent-classes PersonAgent
--env-modules SimpleSocialSpace GlobalInformationEnv
```

### For Economic Behavior
```
--agent-classes LLMDonorAgent
--env-modules EconomySpace
```

### For Game Theory
```
--agent-classes PrisonersDilemmaAgent
--env-modules PrisonersDilemmaEnv
```

## Output Structure

```
hypothesis_{id}/
├── HYPOTHESIS.md         # Hypothesis description and groups
├── SIM_SETTINGS.json     # Agent and environment module configuration
├── experiment_1/         # First experiment group folder
│   └── EXPERIMENT.md
└── experiment_2/
    └── EXPERIMENT.md
```

## Documentation Sync

After adding/modifying/deleting a hypothesis, update TOPIC.md with hypothesis overview and link.
