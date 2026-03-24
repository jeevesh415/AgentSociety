# Search Registration Mechanism

This document describes how custom agents and environment modules are discovered and registered in AgentSociety 2, particularly for VSCode extension integration.

## Overview

AgentSociety 2 provides an automatic discovery mechanism for:

1. **Custom Agents** - Classes inheriting from `AgentBase`
2. **Environment Modules** - Classes inheriting from `EnvBase`

The VSCode extension uses this mechanism to make custom components available to users.

## Agent Discovery

### File Location

Agents should be placed in Python files within your workspace:

```
workspace/
├── agents/
│   ├── my_agent.py
│   ├── specialist_agent.py
│   └── __init__.py
```

### Agent Class Definition

To make your agent discoverable:

```python
# agents/my_agent.py
from agentsociety2.agent import AgentBase
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from agentsociety2.storage import ReplayWriter
    from agentsociety2.env.router_base import RouterBase

class MyCustomAgent(AgentBase):
    """A brief description of your agent.

    This agent does X and is useful for Y scenarios.
    """

    def __init__(
        self,
        id: int,
        profile: dict,
        custom_param: str = "default",
        replay_writer: Optional["ReplayWriter"] = None,
        **kwargs
    ):
        super().__init__(id=id, profile=profile, replay_writer=replay_writer, **kwargs)
        self._custom_param = custom_param

    async def ask(self, question: str, readonly: bool = True) -> str:
        """Process questions with custom behavior."""
        return await super().ask(question, readonly=readonly)

    @classmethod
    def mcp_description(cls) -> str:
        """Return MCP description for discovery."""
        return """MyCustomAgent - A description for the UI.

This agent specializes in X and provides Y capabilities.

Attributes:
    custom_param (str): Description of custom parameter
    profile (dict): Agent profile with name, personality, etc.

Example:
    agent = MyCustomAgent(
        id=1,
        profile={"name": "Alice", "personality": "friendly"},
        custom_param="value"
    )
"""
```

### Discovery Criteria

An agent class is discovered if it:

1. Inherits from `AgentBase` (directly or indirectly)
2. Has an `mcp_description()` classmethod
3. Is in a file with "*.py" extension
4. Is within a recognized workspace directory

### Discovery Process

```python
# Internal discovery implementation
import importlib.util
import inspect
from pathlib import Path

def discover_agents(workspace_path: Path) -> dict[str, type]:
    """Discover all agent classes in workspace."""
    agents = {}

    for py_file in workspace_path.rglob("*.py"):
        # Skip test files and __pycache__
        if "test" in str(py_file) or "__pycache__" in str(py_file):
            continue

        # Import the module
        spec = importlib.util.spec_from_file_location("module", py_file)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        # Find agent classes
        for name, obj in inspect.getmembers(module, inspect.isclass):
            if (issubclass(obj, AgentBase) and
                obj != AgentBase and
                hasattr(obj, 'mcp_description')):
                agents[name] = obj

    return agents
```

## Environment Module Discovery

### File Location

Environment modules should be placed in:

```
workspace/
├── env_modules/
│   ├── my_module.py
│   ├── custom_env.py
│   └── __init__.py
```

### Module Class Definition

```python
# env_modules/my_module.py
from agentsociety2.env import EnvBase, tool

class MyCustomModule(EnvBase):
    """A custom environment module for X.

    Provides tools for agents to interact with Y.
    """

    def __init__(self, param1: str = "default"):
        super().__init__()
        self._param1 = param1

    @tool(readonly=True, kind="observe")
    def get_state(self, agent_id: int) -> str:
        """Get the current state for an agent."""
        return f"State: {self._param1}"

    @tool(readonly=False)
    def set_state(self, value: str) -> str:
        """Set the state value."""
        self._param1 = value
        return f"State set to {value}"

```

### Discovery Criteria

A module class is discovered if it:

1. Inherits from `EnvBase` (directly or indirectly)
2. Has the `@tool` decorator on at least one method
3. Is in a file with "*.py" extension
4. Is within a recognized workspace directory

### Discovery Process

```python
def discover_modules(workspace_path: Path) -> dict[str, type]:
    """Discover all environment module classes in workspace."""
    modules = {}

    for py_file in workspace_path.rglob("*.py"):
        if "test" in str(py_file) or "__pycache__" in str(py_file):
            continue

        spec = importlib.util.spec_from_file_location("module", py_file)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        for name, obj in inspect.getmembers(module, inspect.isclass):
            if (issubclass(obj, EnvBase) and
                obj != EnvBase and
                hasattr(obj, '__module_tools__')):  # Set by @tool
                modules[name] = obj

    return modules
```

## Workspace Registration

### Configuration File

Create a `.agentsociety2` file in your workspace root:

```toml
# .agentsociety2 workspace configuration

[workspace]
name = "My AgentSociety 2 Project"
version = "0.1.0"

[search.paths]
# Directories to search for agents and modules
agents = ["src/agents", "agents"]
env_modules = ["src/env_modules", "env_modules"]
experiments = ["experiments"]

[search.exclude]
# Patterns to exclude
patterns = ["**/test_*.py", "**/__pycache__/**", "**/.venv/**"]

[registration]
# Auto-registration settings
auto_register = true
validate_on_load = true
```

### Programmatic Registration

```python
from agentsociety2.registration import WorkspaceRegistry

# Create registry
registry = WorkspaceRegistry.from_config(".agentsociety2")

# Discover components
agents = registry.discover_agents()
modules = registry.discover_modules()

# Register with router
from agentsociety2.env import ReActRouter

router = ReActRouter()
for module_cls in modules.values():
    instance = module_cls()
    router.register_module(instance)

# Use agents
for agent_cls in agents.values():
    agent = agent_cls(id=..., profile=...)
    agent.set_env(router)
```

## VSCode Extension Integration

### Extension Configuration

The VSCode extension reads the workspace configuration and:

1. Discovers agents and modules
2. Validates them
3. Registers them with the backend service
4. Makes them available in the UI

### Extension API

```python
# Extension-side discovery
class AgentSocietyExtension:
    def __init__(self, workspace_path: Path):
        self.workspace_path = workspace_path
        self.registry = WorkspaceRegistry.from_config(
            workspace_path / ".agentsociety2"
        )

    async def refresh_discovery(self):
        """Refresh discovered components."""
        await self.registry.refresh()

    def get_available_agents(self) -> list[dict]:
        """Get list of discovered agents."""
        return self.registry.list_agents()

    def get_available_modules(self) -> list[dict]:
        """Get list of discovered modules."""
        return self.registry.list_modules()

    async def instantiate_agent(
        self,
        agent_name: str,
        id: int,
        profile: dict,
        **kwargs
    ):
        """Instantiate an agent by name."""
        return await self.registry.create_agent(
            agent_name, id, profile, **kwargs
        )
```

## Validation

### Agent Validation

Agents are validated for:

1. **Base class**: Must inherit from `AgentBase`
2. **Required methods**: Must have `ask()` method
3. **MCP description**: Must have `mcp_description()` classmethod
4. **Type hints**: Parameters should have type hints
5. **Docstrings**: Should have descriptive docstrings

### Module Validation

Modules are validated for:

1. **Base class**: Must inherit from `EnvBase`
2. **Tools**: Must have at least one `@tool` decorated method
3. **Observation capability**: Expose observation through readonly `kind="observe"` tools when needed
4. **Type hints**: Tool parameters should have type hints
5. **Docstrings**: Tools should have descriptive docstrings

## Error Handling

```python
class DiscoveryError(Exception):
    """Base class for discovery errors."""

class InvalidAgentError(DiscoveryError):
    """Raised when an agent class is invalid."""

class InvalidModuleError(DiscoveryError):
    """Raised when a module class is invalid."""

try:
    agents = discover_agents(workspace_path)
except DiscoveryError as e:
    logger.error(f"Discovery failed: {e}")
    # Handle error, show user feedback
```

## Best Practices

1. **Use consistent naming**: `*Agent.py` for agents, `*_module.py` for modules
2. **Provide MCP descriptions**: Essential for UI integration
3. **Add type hints**: Helps with validation and auto-completion
4. **Write docstrings**: Improves discoverability and usability
5. **Organize files**: Separate agents and modules into different directories
6. **Exclude test files**: Use the search.exclude configuration
7. **Validate components**: Run validation before committing

## Example Workspace Structure

```
my_project/
├── .agentsociety2          # Workspace configuration
├── .env                    # Environment variables
├── pyproject.toml          # Project config
├── agents/                 # Custom agents
│   ├── __init__.py
│   ├── specialist_agent.py
│   └── emotional_agent.py
├── env_modules/            # Custom modules
│   ├── __init__.py
│   ├── weather_module.py
│   └── economy_module.py
├── experiments/            # Experiment scripts
│   ├── baseline.py
│   └── treatment.py
└── tests/                  # Tests (excluded from search)
    ├── test_agents.py
    └── test_modules.py
```
