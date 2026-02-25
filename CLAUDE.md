# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

AgentSociety is a framework for building LLM-based agent simulations in urban environments. The repository contains two main packages:

- **`packages/agentsociety`** (v1.x): City simulation framework with gRPC-based environment integration
- **`packages/agentsociety2`** (v2.x): Modernized, LLM-native agent simulation platform (current focus)

## Workspace Structure

This is a uv workspace with Python packages in `packages/`:
- `packages/agentsociety2/` - Primary development package
- `packages/agentsociety/` - Legacy city simulation package
- `packages/agentsociety-community/` - Community contributions
- `packages/agentsociety-benchmark/` - Benchmarking utilities

The frontend is a separate React application in `frontend/`.

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

### Backend Service (FastAPI)

```bash
# Start backend (from packages/agentsociety2)
cd packages/agentsociety2
python -m agentsociety2.backend.run

# Backend runs on: http://localhost:8001
# Docs available at: http://localhost:8001/docs
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

### agentsociety2 Core Components

#### Agent System (`agentsociety2/agent/`)
- **AgentBase**: Abstract base class for all agents
- **PersonAgent**: Concrete person agent implementation
- Agents use LLM via `litellm` router with configurable models (nano/coder/embedding)
- Each agent has: `id`, `profile`, `name`, `replay_writer`
- Key methods: `ask()`, `intervene()`, `set_env()`

#### Environment Router (`agentsociety2/env/`)
- **RouterBase**: Abstract router for environment modules
- **EnvBase**: Base class for environment modules with `@tool` decorator
- **Router implementations**: ReActRouter, PlanExecuteRouter, CodeGenRouter, TwoTierReActRouter, TwoTierPlanExecuteRouter
- Environment modules register tools as observe/statistics/regular methods
- Routers mediate between agents and environment modules

#### Experiment Designer (`agentsociety2/designer/`)
- **ExpDesigner**: LLM-driven experiment design pipeline
- **ExpExecutor**: Executes designed experiments
- **AgentFileProcessor/AgentSelector/AgentGenerator**: Agent file processing utilities
- Literature search integration for hypothesis-driven experiments

#### Storage (`agentsociety2/storage/`)
- **ReplayWriter**: SQLite-based storage for simulation replay
- **Models**: AgentProfile, AgentStatus, AgentDialog (SQLModel)
- **ColumnDef/TableSchema**: Dynamic table registration for custom environment data

#### Code Executor (`agentsociety2/code_executor/`)
- **CodeExecutor**: Executes generated code in Docker containers
- **DockerRunner/LocalExecutor**: Execution strategies
- **CodeGenerator**: Generates Python code from experiment configs

#### Society Helper (`agentsociety2/society/`)
- **AgentSocietyHelper**: Plan-and-Execute helper for external questions/interventions
- Supports `ask()` (readonly) and `intervene()` (read-write) modes
- Creates plans, executes steps, supports dynamic replanning

### Configuration

Environment variables (see `.env.example`):
- `AGENTSOCIETY_LLM_*` - Default LLM settings (required)
- `AGENTSOCIETY_CODER_LLM_*` - Code generation LLM (optional, falls back to default)
- `AGENTSOCIETY_NANO_LLM_*` - High-frequency operations LLM (optional)
- `AGENTSOCIETY_EMBEDDING_*` - Embedding model settings (optional)
- `BACKEND_HOST`, `BACKEND_PORT` - Backend service configuration

LLM routing via `agentsociety2.config`:
- `get_llm_router(role)` - Get litellm Router for role (default/coder/nano/embedding)
- `get_llm_router_and_model(role)` - Get both Router and model name
- `extract_json()` - Utility for JSON extraction from LLM responses

### Frontend Architecture

- React 18 with TypeScript
- Ant Design UI components (@ant-design/pro-components, @ant-design/x)
- MobX for state management
- React Router for navigation
- Monaco Editor for code editing
- Plotly.js for data visualization
- Mapbox GL + Deck.gl for geospatial visualization

## Key Design Patterns

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

- **HuggingFace connectivity**: The framework auto-switches to Chinese mirror (`hf-mirror.com`) if HuggingFace is unreachable
- **Version compatibility**: Use Python >= 3.11
- **Dependencies**: Managed via uv workspace - run `uv sync` from root
- **Frontend build**: Use `npm run build` in `frontend/` directory
- **Testing**: pytest configuration in `packages/agentsociety2/`
- **No ray.io dependency in agentsociety2** (simplified from v1)
