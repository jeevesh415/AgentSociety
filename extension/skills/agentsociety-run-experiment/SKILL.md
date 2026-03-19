---
name: agentsociety-run-experiment
description: Run, monitor, or stop AgentSociety2 simulation experiments.
license: Proprietary. LICENSE.txt has complete terms
---

# Run Experiment

Manage experiment execution using AgentSociety2's built-in CLI.

## Quick Start

```bash
# Get PYTHON_PATH from workspace .env
PYTHON_PATH=$(grep "^PYTHON_PATH=" .env | cut -d'=' -f2)
PYTHON_PATH=${PYTHON_PATH:-.venv/bin/python}

# Start an experiment (--log-file REQUIRED)
$PYTHON_PATH -m agentsociety2.society.cli \
    --config hypothesis_1/experiment_1/init/init_config.json \
    --steps hypothesis_1/experiment_1/init/steps.yaml \
    --run-dir hypothesis_1/experiment_1/run \
    --experiment-id "1_1" \
    --log-file hypothesis_1/experiment_1/run/output.log &

# Or use the entry point directly (if installed)
agentsociety \
    --config hypothesis_1/experiment_1/init/init_config.json \
    --steps hypothesis_1/experiment_1/init/steps.yaml \
    --run-dir hypothesis_1/experiment_1/run \
    --experiment-id "1_1" \
    --log-file hypothesis_1/experiment_1/run/output.log &
```

## Python Environment

AgentSociety2 must be installed in your Python environment. Use the `PYTHON_PATH` from your workspace `.env` file:

```bash
PYTHON_PATH=$(grep "^PYTHON_PATH=" .env | cut -d'=' -f2)
PYTHON_PATH=${PYTHON_PATH:-.venv/bin/python}

$PYTHON_PATH -m agentsociety2.society.cli [options]
```

## CLI Arguments

| Argument | Required | Default | Description |
|----------|----------|---------|-------------|
| `--config` | Yes | - | Path to `init_config.json` |
| `--steps` | Yes | - | Path to `steps.yaml` |
| `--run-dir` | No | `.` | Path to run/ directory for outputs |
| `--experiment-id` | No | - | Optional experiment identifier |
| `--log-level` | No | `INFO` | DEBUG, INFO, WARNING, ERROR, CRITICAL |
| `--log-file` | **Yes** | - | Path to log file (REQUIRED for background execution) |

## Usage Examples

### Start Experiment

**REQUIRES `--log-file` parameter.** The CLI outputs verbose logs that must be saved to a file:

```bash
PYTHON_PATH=$(grep "^PYTHON_PATH=" .env | cut -d'=' -f2)

$PYTHON_PATH -m agentsociety2.society.cli \
    --config hypothesis_1/experiment_1/init/init_config.json \
    --steps hypothesis_1/experiment_1/init/steps.yaml \
    --run-dir hypothesis_1/experiment_1/run \
    --experiment-id "1_1" \
    --log-level INFO \
    --log-file hypothesis_1/experiment_1/run/output.log &
```

### Run in Foreground (for debugging)

```bash
# Without --log-file, logs go to console only
$PYTHON_PATH -m agentsociety2.society.cli \
    --config hypothesis_1/experiment_1/init/init_config.json \
    --steps hypothesis_1/experiment_1/init/steps.yaml \
    --run-dir hypothesis_1/experiment_1/run \
    --log-level DEBUG
```

### With Custom Log Level and File

```bash
$PYTHON_PATH -m agentsociety2.society.cli \
    --config hypothesis_1/experiment_1/init/init_config.json \
    --steps hypothesis_1/experiment_1/init/steps.yaml \
    --run-dir hypothesis_1/experiment_1/run \
    --log-level DEBUG \
    --log-file hypothesis_1/experiment_1/run/output.log &
```

## Programmatic API

For advanced usage, import the runner functions directly:

```python
import asyncio
from agentsociety2.skills.experiment.runner import (
    start_experiment,
    stop_experiment,
    get_experiment_status,
    list_experiments,
)

# Start experiment
async def run():
    await start_experiment(
        workspace_path="/path/to/workspace",
        hypothesis_id=1,
        experiment_id=1,
        run_id="run",  # optional, default="run"
    )

# Check status
status = await get_experiment_status(
    workspace_path="/path/to/workspace",
    hypothesis_id=1,
    experiment_id=1,
    run_id="run",
)

# Stop experiment
await stop_experiment(
    workspace_path="/path/to/workspace",
    hypothesis_id=1,
    experiment_id=1,
    run_id="run",
)

# List experiments
experiments = await list_experiments(
    workspace_path="/path/to/workspace",
    hypothesis_id=1,  # optional
)
```

## Output Files

| File | Description |
|------|-------------|
| `run/sqlite.db` | Simulation database (auto-created) |
| `run/output.log` | Log file (specified via `--log-file` parameter) |
| `run/pid.json` | Process ID and status (auto-created) |
| `run/artifacts/` | Step execution artifacts (ask/intervene results) |

## Monitoring Execution

### Check Process Status

```bash
# Check if process is running
ps aux | grep "agentsociety2.society.cli"

# View output log in real-time (log file specified via --log-file)
tail -f hypothesis_1/experiment_1/run/output.log

# Check pid.json for status
cat hypothesis_1/experiment_1/run/pid.json
```

### Status Indicators

| Status | Description |
|--------|-------------|
| `running` | Experiment is currently executing |
| `completed` | Experiment finished successfully |
| `failed` | Experiment terminated with errors |
| `terminated` | Experiment was stopped via signal |

## Environment Requirements

The following environment variables must be set (typically in `.env`):

```bash
# Required
AGENTSOCIETY_LLM_API_KEY=your_api_key
AGENTSOCIETY_LLM_API_BASE=https://api.example.com/v1
AGENTSOCIETY_LLM_MODEL=your_model_name

# Optional (falls back to above)
AGENTSOCIETY_CODER_LLM_API_KEY=your_api_key
AGENTSOCIETY_NANO_LLM_API_KEY=your_api_key

# Required (disable telemetry)
MEM0_TELEMETRY=False
ANONYMIZED_TELEMETRY=False
```

## Troubleshooting

### Environment Validation

The CLI validates required environment variables before execution. Missing variables will cause early exit with clear error messages.

### Connection Errors

LLM API connection errors appear as:
```
litellm.InternalServerError: Connection error
```

Verify:
1. API endpoint is reachable
2. API key is valid
3. Model name is correct

### Process Management

To stop a running experiment:
```bash
# Find the PID
cat hypothesis_1/experiment_1/run/pid.json

# Kill gracefully
kill -TERM <pid>

# Or use pkill
pkill -f "agentsociety2.society.cli"
```
