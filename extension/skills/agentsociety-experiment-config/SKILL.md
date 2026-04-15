---
name: agentsociety-experiment-config
description: Generate and validate experiment configuration with strict class instantiation validation.
license: Proprietary. LICENSE.txt has complete terms
---

# Experiment Config

Generate and validate experiment configuration for AgentSociety2 simulations, including questionnaire/survey steps in `steps.yaml`.

## Quick Start

```bash
# Get PYTHON_PATH from .env
PYTHON_PATH=$(grep "^PYTHON_PATH=" .env | cut -d'=' -f2)
PYTHON_PATH=${PYTHON_PATH:-python3}

# Step 1: Validate experiment setup
python scripts/config.py validate --hypothesis-id 1 --experiment-id 1

# Step 2: Prepare directory structure
python scripts/config.py prepare --hypothesis-id 1 --experiment-id 1

# Step 3: Get module information
python scripts/config.py info --hypothesis-id 1 --experiment-id 1

# Step 4: (Claude Code) Generate configuration code
# User: "Generate experiment configuration for hypothesis 1, experiment 1"

# Step 5: Run generated code
python scripts/config.py run --hypothesis-id 1 --experiment-id 1

# Step 6: Validate generated configuration
python scripts/config.py check --hypothesis-id 1 --experiment-id 1
```

## Python Environment Requirement

**This skill requires `agentsociety2` to be installed in the Python environment.**

Use the `PYTHON_PATH` from your `.env` file to ensure the correct Python interpreter is used. See `CLAUDE.md` for details.

## Directory Structure

```
hypothesis_{id}/
├── HYPOTHESIS.md              # Hypothesis description
├── SIM_SETTINGS.json          # Agent classes and env modules selection
└── experiment_{id}/
    ├── EXPERIMENT.md          # Experiment description
    └── init/
        ├── config_params.py      # Claude Code generates this
        ├── init_config.json      # Generated configuration
        └── steps.yaml            # Generated steps
```

## Actions

### validate
Validate experiment setup and module selection.

```bash
python scripts/config.py validate --hypothesis-id ID --experiment-id ID [--workspace PATH] [--json]
```

### prepare
Create init/ directory and config_params.py template.

```bash
python scripts/config.py prepare --hypothesis-id ID --experiment-id ID [--workspace PATH] [--json]
```

### info
Display information about selected modules.

```bash
python scripts/config.py info --hypothesis-id ID --experiment-id ID [--workspace PATH] [--json]
```

### run
Execute config_params.py to generate init_config.json and steps.yaml.

```bash
python scripts/config.py run --hypothesis-id ID --experiment-id ID [--workspace PATH] [--json]
```

### check
Validate generated configuration files (instantiates modules to verify).

```bash
python scripts/config.py check --hypothesis-id ID --experiment-id ID [--workspace PATH] [--json]
```

**Validates:**
1. init_config.json exists and is valid JSON
2. steps.yaml exists and is valid YAML
3. Config structure matches InitConfig Pydantic model
4. Agent/env types are registered
5. Each module can be instantiated with provided kwargs
6. Parameter types match constructor signatures

## Claude Code Workflow

### Phase 1: Validation
1. Run `validate` command
2. Run `prepare` command
3. Run `info` command
4. Read HYPOTHESIS.md, EXPERIMENT.md, SIM_SETTINGS.json
5. Read user_data/ files for parameter defaults

### Phase 2: Code Generation
Generate config_params.py that:
- Uses ONLY standard library imports (json, pathlib, csv)
- Reads from user_data/ directory
- Generates valid init_config.json structure
- Generates valid steps.yaml structure, including `questionnaire` steps when the experiment requires agent-facing surveys
- Outputs to stdout

### Phase 3: Execution
1. Run `run` command
2. Run `check` command
3. Fix any validation errors

## Configuration Structure

### init_config.json
```json
{
  "env_modules": [
    {"module_type": "SimpleSocialSpace", "kwargs": {...}}
  ],
  "agents": [
    {"agent_id": 1, "agent_type": "PersonAgent", "kwargs": {...}}
  ]
}
```

### steps.yaml
```yaml
start_t: "2024-01-01T00:00:00"
steps:
  - type: run
    num_steps: 100
    tick: 1
  - type: ask
    question: "Summarize current state"
  - type: intervene
    instruction: "Modify something..."
  - type: questionnaire
    questionnaire_id: "post_run_survey"
    title: "Post-run survey"
    description: "Collect structured responses from agents after the run"
    target_agent_ids: [1, 2, 3]
    questions:
      - id: "mood"
        prompt: "How do you feel about the outcome?"
        response_type: "choice"
        choices: ["positive", "neutral", "negative"]
      - id: "reason"
        prompt: "Briefly explain your answer."
        response_type: "text"
```

### questionnaire step

Use a `questionnaire` step when the experiment needs structured answers from agents during or after the simulation.

Required fields:
- `type: questionnaire`
- `questionnaire_id`: unique identifier for this questionnaire run
- `questions`: non-empty list of question objects

Optional fields:
- `title`: questionnaire title shown in the prompt context
- `description`: questionnaire-level instructions
- `target_agent_ids`: list of agent IDs; omit to survey all agents

Each question object supports:
- `id`: unique question identifier
- `prompt`: question text
- `response_type`: one of `text`, `integer`, `float`, `choice`, `json`
- `choices`: required when `response_type` is `choice`

## Important Notes

1. **Use class names** as type identifiers (e.g., `PersonAgent`, not `person_agent`)
2. **All parameters go in kwargs** dictionary
3. **agent_id must equal kwargs.id**
4. **Read user_data files** before generating configuration
5. **Questionnaire steps must include questions** and each question must have an `id` and `prompt`
6. **Choice questions must provide choices**; otherwise validation will fail

## Documentation Sync

After generating configuration, update EXPERIMENT.md with configuration parameters and agent selection criteria.
