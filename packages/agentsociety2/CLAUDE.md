# CLAUDE.md

This file provides guidance to Claude Code when working in this AI Social Scientist workspace.

**Research Context**: See `TOPIC.md` for research topics, goals, and current work.

---

## Python Environment

**CRITICAL**: All skills require `agentsociety2` to be installed in the Python environment.

### Finding the Correct Python

The workspace `.env` file contains `PYTHON_PATH` pointing to the Python environment with agentsociety2 installed:

```bash
# Read PYTHON_PATH from .env (with fallback to python3)
PYTHON_PATH=$(grep "^PYTHON_PATH=" .env | cut -d'=' -f2)
PYTHON_PATH=${PYTHON_PATH:-python3}

# Use this Python for ALL skill invocations
$PYTHON_PATH .claude/skills/agentsociety-hypothesis/scripts/hypothesis.py list
```

### Why PYTHON_PATH Matters

- Dependencies are managed via `uv`, not system Python
- Skills auto-load `.env` but use the calling Python interpreter
- Always use `$PYTHON_PATH` to ensure agentsociety2 is available

---

## Research Workflow (Execution Order)

Follow this sequence for social science research:

```
1. Define Research Topic (TOPIC.md)
   └─> Define research question and objectives

2. Literature Review
   └─> agentsociety-literature-search
   └─> agentsociety-quick-web-search（简单的快速联网检索）
   └─> agentsociety-web-research（复杂的深挖/多轮研究）

3. Generate Hypothesis
   └─> agentsociety-hypothesis add

4. Initialize Experiment
   └─> agentsociety-experiment-config (validate → prepare → info → run → check)

5. Run Experiment
   └─> agentsociety-run-experiment start

6. Analyze Results
   └─> agentsociety-analysis

7. Generate Report
   └─> agentsociety-synthesize

8. Refine Hypothesis/Experiment
   └─> Repeat from step 3 with new insights
```

---

## Workspace Structure

```
.
├── TOPIC.md              # Research topic and goals
├── CLAUDE.md             # This file - technical guidance
├── AGENTS.md             # Symlink to CLAUDE.md
├── .env                  # Environment configuration (API keys, PYTHON_PATH, etc)
├── papers/               # Literature storage
│   ├── literature_index.json  # Literature catalog
│   └── literature/            # Individual article summaries
├── user_data/            # User data storage for custom datasets
├── custom/               # Custom Agent and Environment modules
│   ├── agents/               # Custom agent definitions
│   │   └── examples/         # Example agents (reference only)
│   ├── envs/                 # Custom environment modules
│   │   └── examples/         # Example environments (reference only)
│   └── README.md             # Custom module development guide
├── .agentsociety/        # Internal workspace state
│   └── prefill_params.json  # Pre-filled parameters for modules
├── hypothesis_{id}/      # Hypothesis directories
│   ├── HYPOTHESIS.md         # Hypothesis description and groups
│   ├── SIM_SETTINGS.json     # Agent and env module selection
│   └── experiment_{id}/
│       ├── EXPERIMENT.md     # Experiment description
│       ├── init/             # Configuration files (simplified)
│       │   ├── config_params.py  # Parameter generation script
│       │   ├── init_config.json  # Experiment configuration
│       │   └── steps.yaml        # Execution steps
│       ├── run/              # Simulation outputs
│       │   ├── sqlite.db         # Simulation database
│       │   ├── stdout.log        # Standard output
│       │   ├── stderr.log        # Error messages
│       │   └── pid.json          # Process ID file (when running)
│       └── data/             # Analysis results
│           ├── analysis_summary.json
│           ├── report.md
│           └── figures/
└── presentation/         # Synthesized reports
    └── hypothesis_{id}/
        └── experiment_{id}/
            ├── synthesis_report_zh.md
            └── synthesis_report_en.md
```

### Directory Notes

- **custom/** - Create your custom Agent and Environment modules here. See `custom/README.md` for development guide.
- **user_data/** - Store your custom datasets and data files here for experiment configuration.
- **.agentsociety/** - Internal workspace state, managed by the system.

---

## User Dialogue Style

When interacting with users:

### 1. Academic Tone
- Use academic terminology and maintain professionalism
- Be precise with terminology
- Acknowledge uncertainty and limitations

### 2. Language Matching
- Match the user's language (Chinese or English)
- Maintain consistency throughout the conversation

### 3. Guidance Flow
- Proactively guide users to the next step
- After completing a step, suggest the next action
- Explain the current step's position in the overall research workflow
- Provide optional research paths

### 4. Ask Questions
- Frequently ask questions to clarify user requirements:
- "Which specific research direction are you interested in?"
- "What is the theoretical basis for this hypothesis?"
- "What results do you expect to observe?"
- "How many agents should participate in the experiment?"

---

## Quick Skill Reference

| Skill | Purpose | Example |
|-------|---------|---------|
| `agentsociety-scan-modules` | List available agents/envs | `list --short` |
| `agentsociety-hypothesis` | Manage hypotheses | `add`, `list`, `get` |
| `agentsociety-experiment-config` | Generate experiment config | `validate`, `prepare`, `run` |
| `agentsociety-run-experiment` | Execute simulations | `start`, `status`, `stop` |
| `agentsociety-analysis` | Analyze results | `--hypothesis-id 1 --experiment-id 1` |
| `agentsociety-synthesize` | Create reports | Bilingual synthesis |

---

## Essential Commands

```bash
# Always use PYTHON_PATH from .env
PYTHON_PATH=$(grep "^PYTHON_PATH=" .env | cut -d'=' -f2)
PYTHON_PATH=${PYTHON_PATH:-python3}

# List available modules
$PYTHON_PATH .claude/skills/agentsociety-scan-modules/scripts/scan_modules.py list

# List hypotheses
$PYTHON_PATH .claude/skills/agentsociety-hypothesis/scripts/hypothesis.py list

# Run experiment
$PYTHON_PATH .claude/skills/agentsociety-run-experiment/scripts/run.py start --hypothesis-id 1 --experiment-id 1
```
