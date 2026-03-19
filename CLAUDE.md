# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

AgentSociety is a framework for building LLM-based agent simulations in urban environments and research workflows. The repository contains two main packages:

- **`packages/agentsociety`** (v1.x): City simulation framework with gRPC-based environment integration (legacy)
- **`packages/agentsociety2`** (v2.x): Modernized, LLM-native agent simulation platform with research skills (current focus)

## Workspace Structure

This is a uv workspace with Python packages in `packages/`:
- `packages/agentsociety2/` - Primary development package
- `packages/agentsociety/` - Legacy city simulation package
- `packages/agentsociety-community/` - Community contributions
- `packages/agentsociety-benchmark/` - Benchmarking utilities

The frontend is a separate React application in `frontend/`.
VSCode extension is in `extension/`.

## Development Commands

### Python Package (agentsociety2)

```bash
# Install dependencies (in workspace root)
uv sync

# Run tests
cd packages/agentsociety2 && pytest

# Linting
ruff check packages/agentsociety2/

# Format code
ruff format packages/agentsociety2/
```

### Running Experiments (CLI)

```bash
# Get PYTHON_PATH from workspace .env
PYTHON_PATH=$(grep "^PYTHON_PATH=" .env | cut -d'=' -f2)
PYTHON_PATH=${PYTHON_PATH:-.venv/bin/python}

# Run an experiment (--log-file REQUIRED for background execution)
$PYTHON_PATH -m agentsociety2.society.cli \
    --config hypothesis_1/experiment_1/init/init_config.json \
    --steps hypothesis_1/experiment_1/init/steps.yaml \
    --run-dir hypothesis_1/experiment_1/run \
    --experiment-id "1_1" \
    --log-level INFO \
    --log-file hypothesis_1/experiment_1/run/output.log &

# Or run in foreground (logs to console)
$PYTHON_PATH -m agentsociety2.society.cli \
    --config init_config.json \
    --steps steps.yaml \
    --run-dir run
```

### Backend Service (FastAPI)

```bash
# Start backend (from packages/agentsociety2)
cd packages/agentsociety2
python -m agentsociety2.backend.run

# Backend runs on: http://localhost:8001
# API docs available at: http://localhost:8001/docs
# ReDoc available at: http://localhost:8001/redoc
```

### Frontend (React + Vite)

```bash
cd frontend
npm install          # Install dependencies
npm run dev          # Start dev server (http://localhost:5173)
npm run build        # Production build
npm run lint         # ESLint
```

### Documentation (Sphinx)

```bash
# Build Chinese docs (default)
make html

# Build English docs
make html-en

# Build all languages
make html-all
```

## Architecture

### System Architecture Overview

```mermaid
graph TB
    subgraph "User Interfaces"
        CLI[CLI<br/>agentsociety2.society.cli]
        Frontend[React Frontend<br/>localhost:5173]
        VSCode[VSCode Extension]
    end

    subgraph "Backend Layer"
        API[FastAPI Backend<br/>localhost:8001]
    end

    subgraph "Core Simulation"
        Society[AgentSociety<br/>Orchestrator]
        Router[Environment Router<br/>ReAct/PlanExecute/CodeGen]
        Storage[(ReplayWriter<br/>SQLite)]
    end

    subgraph "Agents"
        Agent1[PersonAgent 1]
        Agent2[PersonAgent 2]
        AgentN[PersonAgent N]
    end

    subgraph "Environment Modules"
        Env1[SimpleSocialSpace]
        Env2[EconomyModule]
        EnvN[Custom Modules...]
    end

    subgraph "Research Skills"
        Lit[literature]
        Exp[experiment]
        Hyp[hypothesis]
        Paper[paper]
        Analysis[analysis]
        Agent[agent]
    end

    subgraph "External Services"
        LLM[LLM Provider<br/>OpenAI/Claude/etc]
        Mem0[mem0 Memory<br/>Telemetry Disabled]
        Chroma[ChromaDB<br/>Telemetry Disabled]
    end

    CLI --> Society
    Frontend --> API
    VSCode --> API
    API --> Society
    API --> Skills

    Society --> Router
    Society --> Storage
    Society --> Agent1
    Society --> Agent2
    Society --> AgentN

    Router --> Env1
    Router --> Env2
    Router --> EnvN

    Agent1 --> Router
    Agent2 --> Router
    AgentN --> Router

    Skills --> Society
    Skills --> LLM
    Society --> LLM

    Agent1 -.-> Mem0
    Agent2 -.-> Mem0
    AgentN -.-> Mem0
```

### agentsociety2 Core Components

#### Agent System (`agentsociety2/agent/`)
- **AgentBase**: Abstract base class for all agents
- **PersonAgent**: Concrete person agent implementation
- **DoNothingAgent**: No-op agent for testing
- Agents use LLM via `litellm` router with configurable models (nano/coder/embedding)
- Each agent has: `id`, `profile`, `name`, `replay_writer`
- Key methods: `ask()`, `intervene()`, `set_env()`

#### Environment Router (`agentsociety2/env/`)
- **RouterBase**: Abstract router for environment modules
- **EnvBase**: Base class for environment modules with `@tool` decorator
- **Router implementations**: ReActRouter, PlanExecuteRouter, CodeGenRouter, TwoTierReActRouter, TwoTierPlanExecuteRouter
- Environment modules register tools as observe/statistics/regular methods
- Routers mediate between agents and environment modules

#### CLI (`agentsociety2/society/cli.py`)
- **Main entry point**: `python -m agentsociety2.society.cli`
- **Arguments**: `--config`, `--steps`, `--run-dir`, `--experiment-id`, `--log-level`, `--log-file`
- **Features**: Progress tracking with pid.json, automatic database creation, artifact generation
- **Telemetry blocking**: Forces MEM0_TELEMETRY=False and ANONYMIZED_TELEMETRY=False

#### Research Skills (`agentsociety2/skills/`)
- **literature**: Academic literature search and management
- **experiment**: Experiment configuration and execution
- **hypothesis**: Hypothesis generation and management
- **web_research**: Web research using Miro
- **paper**: Academic paper generation with EasyPaper
- **analysis**: Data analysis and reporting
- **agent**: Agent processing, selection, generation, and filtering

#### Designer (`agentsociety2/designer/`)
- **ExpDesigner**: LLM-driven experiment design pipeline
- **ExpExecutor**: Executes designed experiments
- **ConfigBuilder**: Configuration building and validation

#### Backend API (`agentsociety2/backend/`)
- **FastAPI**-based REST API for external integrations
- **Routes**: `/api/v1/experiments`, `/api/v1/modules`, `/api/v1/replay`, `/api/v1/custom`
- **Separate from core simulation** - runs as independent service
- **API documentation**: Available at `/docs` when running

#### Storage (`agentsociety2/storage/`)
- **ReplayWriter**: SQLite-based storage for simulation replay
- **Models**: AgentProfile, AgentStatus, AgentDialog (SQLModel)
- **ColumnDef/TableSchema**: Dynamic table registration for custom environment data

#### Code Executor (`agentsociety2/code_executor/`)
- **CodeExecutor**: Executes generated code in Docker containers
- **DockerRunner/LocalExecutor**: Execution strategies
- **CodeGenerator**: Generates Python code from experiment configs

#### Logger (`agentsociety2/logger/`)
- **ColoredFormatter**: Color-coded console output by log level
- **File logging**: `add_file_handler()` for writing to log files
- **LiteLLM integration**: Custom callback logger for LLM calls
- **Functions**: `get_logger()`, `set_logger_level()`, `add_file_handler()`

#### Society (`agentsociety2/society/`)
- **AgentSociety**: Main simulation orchestrator
- **AgentSocietyHelper**: Plan-and-Execute helper for external questions/interventions
- **Models**: InitConfig, StepsConfig, ExperimentConfig

### Configuration

Environment variables (see `.env.example`):

**Required Configuration:**
- `AGENTSOCIETY_LLM_API_KEY` - Primary API key (required, validated at startup)
- `AGENTSOCIETY_LLM_API_BASE` - API base URL (required, validated at startup)
- `AGENTSOCIETY_LLM_MODEL` - Default model name

**Optional LLM Configuration** (falls back to default if not set):
- `AGENTSOCIETY_CODER_LLM_*` - Code generation LLM
- `AGENTSOCIETY_NANO_LLM_*` - High-frequency operations LLM
- `AGENTSOCIETY_EMBEDDING_*` - Embedding model settings

**Telemetry** (automatically set by framework):
- `MEM0_TELEMETRY=False` - Required: Disable mem0 telemetry
- `ANONYMIZED_TELEMETRY=False` - Required: Disable ChromaDB/Posthog telemetry

**Other Settings:**
- `AGENTSOCIETY_HOME_DIR` - Data directory (default: ./agentsociety_data)
- `BACKEND_HOST`, `BACKEND_PORT` - Backend service configuration

LLM routing via `agentsociety2.config`:
- `get_llm_router(role)` - Get litellm Router for role (default/coder/nano/embedding)
- `get_llm_router_and_model(role)` - Get both Router and model name
- `extract_json()` - Utility for JSON extraction from LLM responses

**Configuration validation**: The framework validates required configuration at module load time and will raise a ValueError if `AGENTSOCIETY_LLM_API_KEY` or `AGENTSOCIETY_LLM_API_BASE` are not set.

### Frontend Architecture

- React 18 with TypeScript
- Ant Design UI components (@ant-design/pro-components, @ant-design/x)
- MobX for state management
- React Router for navigation
- Monaco Editor for code editing
- Plotly.js for data visualization
- Mapbox GL + Deck.gl for geospatial visualization

### Module Organization

```mermaid
graph TD
    subgraph "agentsociety2/"
        A[agent/]
        E[env/]
        S[society/]
        SK[skills/]
        D[designer/]
        B[backend/]
        ST[storage/]
        CE[code_executor/]
        L[logger/]
        C[config/]
        R[registry/]
        CN[contrib/]
        CU[custom/]
    end

    subgraph "agent/"
        A1[AgentBase]
        A2[PersonAgent]
        A3[DoNothingAgent]
    end

    subgraph "env/"
        E1[EnvBase]
        E2[RouterBase]
        E3[CodeGenRouter]
        E4[ReActRouter]
        E5[PlanExecuteRouter]
    end

    subgraph "society/"
        S1[AgentSociety]
        S2[AgentSocietyHelper]
        S3[cli.py]
        S4[models.py]
    end

    subgraph "skills/"
        SK1[literature/]
        SK2[experiment/]
        SK3[hypothesis/]
        SK4[web_research/]
        SK5[paper/]
        SK6[analysis/]
        SK7[agent/]
    end

    subgraph "backend/"
        B1[routers/]
        B2[services/]
        B3[models/]
        B4[run.py]
    end

    A --> A1
    A --> A2
    A --> A3
    E --> E1
    E --> E2
    E --> E3
    E --> E4
    E --> E5
    S --> S1
    S --> S2
    S --> S3
    S --> S4
    SK --> SK1
    SK --> SK2
    SK --> SK3
    SK --> SK4
    SK --> SK5
    SK --> SK6
    SK --> SK7
    B --> B1
    B --> B2
    B --> B3
    B --> B4
```

## Key Design Patterns

### Agent-Environment Interaction Flow

```mermaid
sequenceDiagram
    participant A as Agent
    participant R as Router
    participant E as EnvModule
    participant T as @tool Methods
    participant L as LLM

    A->>R: ask(question, readonly=True)
    R->>E: Get available tools
    E-->>R: Tool signatures
    R->>L: Generate tool call code
    L-->>R: Python code
    R->>R: Execute in sandbox
    R->>T: Call tool(agent_id, ...)
    T-->>R: Result
    R-->>A: Formatted response
```

### Research Skills Workflow

```mermaid
graph LR
    subgraph "Research Workflow"
        Q[Research Question] --> Lit[Literature Search]
        Lit --> Papers[(Related Papers)]
        Papers --> Hyp[Hypothesis Generator]
        Hyp --> Hyps[Hypotheses]
        Hyps --> Exp[Experiment Designer]
        Exp --> Config[Experiment Config]
        Config --> CLI[CLI Execution]
        CLI --> Results[(Results)]
        Results --> Analysis[Data Analysis]
        Analysis --> Paper[Paper Generator]
        Paper --> Final[Final Paper]
    end
```

### CLI Experiment Execution Flow

```mermaid
flowchart TD
    Start([CLI Start]) --> Validate[Validate Environment]
    Validate --> LoadConfig[Load init_config.json]
    LoadConfig --> LoadSteps[Load steps.yaml]
    LoadSteps --> InitDB[Initialize SQLite DB]
    InitDB --> CreateAgents[Create Agents]
    CreateAgents --> CreateEnv[Create Environment Router]
    CreateEnv --> InitSociety[Initialize AgentSociety]
    InitSociety --> Steps{Execute Steps}

    Steps --> Ask[ask: Query]
    Steps --> Intervene[intervene: Modify]
    Steps --> Step[step: Simulate tick]

    Ask --> SaveArtifact[Save Artifact]
    Intervene --> SaveArtifact
    Step --> SaveArtifact

    SaveArtifact --> More{More Steps?}
    More -->|Yes| Steps
    More -->|No| Close[Close Society]
    Close --> pid[Write pid.json]
    pid --> End([Done])
```

### Environment Modules
- Inherit from `EnvBase`
- Use `@tool(readonly=True/False, kind="observe"|"statistics"|None)` decorator
- Implement `observe()` method (returns state string for agents)
- Tools registered automatically via metaclass

### Agent-Environment Interaction
- Agents call `await env_router.ask(question, readonly=False)`
- Environment routes questions to appropriate module tools
- Supports both querying (readonly=True) and modification (readonly=False)

### Replay System
- All agent actions和环境变化 written to SQLite via ReplayWriter
- Framework tables (agent_profile, agent_status, agent_dialog) auto-created
- Custom tables registered via `register_table(ColumnDef*, TableSchema)`
- Enables full experiment replay and analysis

## Important Notes

- **agentsociety2 is a Python package**: ALWAYS access `agentsociety2` via `import agentsociety2`, NEVER search for it in the file system (e.g., `packages/agentsociety2`). The package is installed in the Python environment and available for import.
- **CLI --log-file is REQUIRED**: When running experiments in background, always specify `--log-file` to capture verbose logs.
- **Telemetry is blocked**: The framework forcibly disables mem0 and ChromaDB telemetry to prevent external connections.
- **HuggingFace connectivity**: The framework auto-switches to Chinese mirror (`hf-mirror.com`) if HuggingFace is unreachable.
- **Version compatibility**: Use Python >= 3.11
- **Dependencies**: Managed via uv workspace - run `uv sync` from root
- **Frontend build**: Use `npm run build` in `frontend/` directory
- **Testing**: pytest configuration in `packages/agentsociety2/`
- **No ray.io dependency in agentsociety2** (simplified from v1)
- **Research skills**: The skills/ module provides LLM-native research workflows for literature search, hypothesis generation, experiment design, and paper writing.
