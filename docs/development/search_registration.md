# Module Registry and Discovery

This document describes how custom agents and environment modules are discovered and registered in AgentSociety 2, particularly for VSCode extension integration.

## Overview

AgentSociety 2 provides a centralized `ModuleRegistry` for automatic discovery of:

1. **Custom Agents** - Classes inheriting from `AgentBase`
2. **Environment Modules** - Classes inheriting from `EnvBase`

The registry supports both built-in modules (from `contrib/`) and custom modules (from `custom/` directory).

## ModuleRegistry

The `ModuleRegistry` is a singleton class that manages all registered agents and environment modules.

### Basic Usage

```python
from agentsociety2.registry import get_registry, list_all_modules

# Get the global registry
registry = get_registry()

# List all registered modules
modules = list_all_modules()
print(modules["agents"])      # List of agent info dicts
print(modules["env_modules"]) # List of env module info dicts

# Get specific module class
from agentsociety2.registry import get_env_module_class, get_agent_module_class

env_class = get_env_module_class("SimpleSocialSpace")
agent_class = get_agent_module_class("PersonAgent")
```

### Lazy Loading

The registry implements **lazy loading** - modules are only discovered when first accessed:

```python
registry = get_registry()

# Modules are NOT loaded yet
# ...

# This triggers lazy loading of built-in modules
agents = registry.agent_modules

# This triggers lazy loading of custom modules (if workspace is set)
env_modules = registry.env_modules
```

To eagerly load all modules:

```python
registry.load_all_modules()
```

## Agent Discovery

### Built-in Agents

Built-in agents are discovered automatically from:

1. `agentsociety2.agent` - Core agents like `PersonAgent`
2. `agentsociety2.contrib.agent` - Contributed agent implementations

```python
from agentsociety2.registry import get_registered_agent_modules

# Get all registered agents
agents = get_registered_agent_modules()
for agent_type, agent_class in agents:
    print(f"{agent_type}: {agent_class.__name__}")
```

### Custom Agent Definition

To create a discoverable custom agent:

```python
# custom/agents/my_agent.py
from agentsociety2.agent import AgentBase
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from agentsociety2.storage import ReplayWriter
    from agentsociety2.env.router_base import RouterBase
    from datetime import datetime

class MyCustomAgent(AgentBase):
    """A custom agent with specific capabilities."""

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

    async def ask(self, message: str, readonly: bool = True) -> str:
        """Process questions with custom behavior."""
        return await super().ask(message, readonly=readonly)

    async def step(self, tick: int, t: "datetime") -> str:
        """Execute one simulation step."""
        return "Step completed"

    async def dump(self) -> dict:
        return {"id": self.id, "custom_param": self._custom_param}

    async def load(self, dump_data: dict):
        self._custom_param = dump_data.get("custom_param", "default")

    @classmethod
    def mcp_description(cls) -> str:
        """Return description for VSCode extension discovery."""
        return """MyCustomAgent - A custom agent for X.

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
2. Is in a Python file within the search paths
3. Is properly importable (no syntax errors)

## Environment Module Discovery

### Built-in Modules

Built-in environment modules are discovered from `agentsociety2.contrib.env`:

```python
from agentsociety2.registry import get_registered_env_modules

# Get all registered env modules
env_modules = get_registered_env_modules()
for module_type, module_class in env_modules:
    print(f"{module_type}: {module_class.__name__}")
```

### Custom Module Definition

```python
# custom/envs/my_module.py
from agentsociety2.env import EnvBase, tool

class MyCustomModule(EnvBase):
    """A custom environment module for X."""

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

## Custom Module Directory Structure

Place custom modules in the `custom/` directory:

```
workspace/
├── custom/
│   ├── agents/
│   │   ├── __init__.py
│   │   ├── specialist_agent.py
│   │   └── emotional_agent.py
│   ├── envs/
│   │   ├── __init__.py
│   │   ├── weather_module.py
│   │   └── economy_module.py
│   └── skills/
│       └── my_custom_skill/
│           ├── SKILL.md
│           └── scripts/
│               └── my_custom_skill.py
```

## Workspace Integration

### Setting Up Workspace

```python
from pathlib import Path
from agentsociety2.registry import get_registry, scan_and_register_custom_modules

# Set workspace path
workspace_path = Path("/path/to/workspace")
registry = get_registry()
registry.set_workspace(workspace_path)

# Or scan and register custom modules explicitly
result = scan_and_register_custom_modules(workspace_path)
print(f"Found {len(result.get('agents', []))} custom agents")
print(f"Found {len(result.get('envs', []))} custom env modules")
```

### Reloading Modules

When developing custom modules, you may need to reload:

```python
from agentsociety2.registry import reload_modules
from pathlib import Path

# Reload all modules
reload_modules(workspace_path=Path("/path/to/workspace"))
```

## Programmatic Registration

### Direct Registration

```python
from agentsociety2.registry import get_registry
from my_module import MyCustomAgent, MyCustomEnv

registry = get_registry()

# Register agent
registry.register_agent_module("MyCustomAgent", MyCustomAgent, is_custom=True)

# Register environment module
registry.register_env_module("MyCustomEnv", MyCustomEnv, is_custom=True)
```

### With Environment Router

```python
from agentsociety2.env import ReActRouter
from agentsociety2.registry import get_registry

# Get module class from registry
registry = get_registry()
EnvClass = registry.get_env_module("SimpleSocialSpace")

if EnvClass:
    # Create instance
    env_instance = EnvClass(agent_id_name_pairs=[(1, "Alice")])

    # Register with router
    router = ReActRouter()
    router.register_module(env_instance)
```

## VSCode Extension Integration

The VSCode extension uses the registry to discover and display available modules:

1. **Discovery**: Extension calls `list_all_modules()` to get available classes
2. **Validation**: Extension validates module structure and parameters
3. **Registration**: Extension registers custom modules from workspace
4. **Instantiation**: Extension creates instances via the backend API

### Extension API Usage

```python
# Backend API endpoint for listing modules
GET /api/v1/modules

# Response
{
    "env_modules": [
        {
            "type": "SimpleSocialSpace",
            "class_name": "SimpleSocialSpace",
            "description": "...",
            "is_custom": false
        }
    ],
    "agents": [
        {
            "type": "PersonAgent",
            "class_name": "PersonAgent",
            "description": "...",
            "is_custom": false
        }
    ]
}
```

## Module Information

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
registry = get_registry()

# Get agent info
info = registry.get_module_info("PersonAgent", kind="agent")
print(info["description"])
print(info["parameters"])

# Get env module info
info = registry.get_module_info("SimpleSocialSpace", kind="env_module")
print(info["description"])
print(info["parameters"])
```

## Best Practices

1. **Use MCP Descriptions**: Implement `mcp_description()` for VSCode extension discovery
2. **Type Hints**: Add type hints to all parameters for better documentation
3. **Docstrings**: Write clear docstrings for classes and methods
4. **Naming Conventions**:
   - Agents: `*Agent.py` (e.g., `specialist_agent.py`)
   - Environment modules: `*_module.py` or descriptive names
5. **__init__.py**: Include `__init__.py` in custom directories
6. **Error Handling**: Handle import errors gracefully in custom modules

## Troubleshooting

### Module Not Discovered

1. Check the class inherits from `AgentBase` or `EnvBase`
2. Verify the file is in the correct directory
3. Ensure no syntax errors in the module
4. Check `__init__.py` exists in the directory

### Custom Module Not Loading

1. Verify workspace path is set correctly
2. Call `scan_and_register_custom_modules()` explicitly
3. Check logs for import errors

### Clearing Registry

```python
from agentsociety2.registry import get_registry

registry = get_registry()

# Clear custom modules only
registry.clear_custom_modules()

# Clear everything and reload
registry._env_modules.clear()
registry._agent_modules.clear()
registry._builtin_loaded = False
registry._custom_loaded = False
```
