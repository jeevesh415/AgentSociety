# Environment Module Development Guide

This guide explains how to develop custom environment modules for AgentSociety 2.

## Overview

Environment modules in AgentSociety 2 encapsulate specific functionality through tools that agents can discover and use. This guide covers how to create custom modules.

## Base Classes

### EnvBase

All environment modules inherit from `EnvBase`:

```python
from agentsociety2.env import EnvBase, tool

class MyModule(EnvBase):
    """A custom environment module."""

    def __init__(self):
        super().__init__()
        # Your initialization
        self._state = {}
```

## Repository Compatibility Contract

Custom env modules in this repository are discovered from `custom/envs/*.py`. Keep these constraints in mind:

- The class must be defined in the target file directly.
- The registry key remains the class name.
- `step()` is required.
- The class should support `cls()` without required constructor args.
- If the module needs observation capability, provide it through readonly `kind="observe"` tools.
- `mcp_description()` should be callable and describe purpose, config, defaults, and tools.

## The @tool Decorator

The `@tool` decorator registers methods as discoverable tools:

```python
@tool(readonly=False, name="custom_action", description="A custom tool action")
async def my_tool(self, param1: str, param2: int) -> str:
    """Tool description for agents."""
    return f"Action completed with {param1} and {param2}"
```

### Parameters

- `readonly` (bool): Whether the tool modifies state (required for observe/statistics)
- `name` (str, optional): Custom tool name (defaults to method name)
- `description` (str, optional): Tool description for agents
- `kind` (str, optional): Tool kind - "observe", "statistics", or None (default)

## Tool Types

### 1. Observe Tools

For agent-specific observations. Must be `readonly=True` and take only `agent_id`:

```python
@tool(readonly=True, kind="observe")
async def get_agent_status(self, agent_id: int) -> str:
    """Get the current status of an agent."""
    status = self._agent_statuses.get(agent_id, "unknown")
    return f"Agent {agent_id} status: {status}"
```

### 2. Statistics Tools

For aggregate information. Must be `readonly=True` and take no parameters:

```python
@tool(readonly=True, kind="statistics")
async def get_average_happiness(self) -> str:
    """Get the average happiness across all agents."""
    if not self._happiness:
        return "No happiness data available"
    avg = sum(self._happiness.values()) / len(self._happiness)
    return f"Average happiness: {avg:.2f}"
```

### 3. Regular Tools

Can be read-only or read-write, with any parameters:

```python
@tool(readonly=False)
async def set_agent_happiness(self, agent_id: int, happiness: float) -> str:
    """Set the happiness level for an agent."""
    self._happiness[agent_id] = max(0, min(1, happiness))
    return f"Set agent {agent_id} happiness to {self._happiness[agent_id]}"
```

## Creating a Complete Module

### Example: Weather Module

```python
from agentsociety2.env import EnvBase, tool
from typing import Dict

class WeatherModule(EnvBase):
    """A weather simulation module."""

    def __init__(self, initial_temp: float = 20.0):
        super().__init__()
        self._temperature = initial_temp
        self._conditions = "sunny"
        self._agent_locations: Dict[int, str] = {}

    @classmethod
    def mcp_description(cls) -> str:
        return "WeatherModule: weather env with config and tool descriptions."

    @tool(readonly=True, kind="observe")
    async def get_weather(self, agent_id: int) -> str:
        """Get the current weather for an agent's location."""
        location = self._agent_locations.get(agent_id, "unknown")
        return (
            f"Weather at {location}: {self._conditions}, "
            f"{self._temperature}°C"
        )

    @tool(readonly=False)
    async def set_temperature(self, temperature: float) -> str:
        """Change the global temperature."""
        self._temperature = temperature
        return f"Temperature set to {self._temperature}°C"

    @tool(readonly=False)
    async def set_conditions(self, conditions: str) -> str:
        """Change the weather conditions."""
        valid = ["sunny", "cloudy", "rainy", "snowy"]
        if conditions.lower() not in valid:
            return f"Invalid conditions. Choose from: {valid}"
        self._conditions = conditions.lower()
        return f"Weather set to {self._conditions}"

    @tool(readonly=True, kind="statistics")
    async def get_global_temperature(self) -> str:
        """Get the current global temperature."""
        return f"Global temperature: {self._temperature}°C"

    @tool(readonly=False)
    async def set_agent_location(self, agent_id: int, location: str) -> str:
        """Set an agent's location."""
        self._agent_locations[agent_id] = location
        return f"Agent {agent_id} moved to {location}"

    async def step(self, tick: int, t: datetime):
        self.t = t
```

## State Management

### Using ReplayWriter for Persistence

```python
from agentsociety2.env import EnvBase, tool
from agentsociety2.storage import ReplayWriter
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from agentsociety2.storage import ReplayWriter

class PersistentModule(EnvBase):
    """A module with persistent state."""

    def __init__(self):
        super().__init__()
        self._writer: ReplayWriter | None = None
        self._state = {}

    async def initialize(self, writer: "ReplayWriter"):
        """Initialize with a replay writer."""
        self._writer = writer
        # Register custom table
        from agentsociety2.storage import ColumnDef, TableSchema
        schema = TableSchema(
            name="module_state",
            columns=[
                ColumnDef(name="id", dtype="INTEGER", primary_key=True),
                ColumnDef(name="key", dtype="TEXT"),
                ColumnDef(name="value", dtype="TEXT"),
            ]
        )
        writer.register_table(schema)

    @tool(readonly=False)
    def set_state(self, key: str, value: str) -> str:
        """Set a state value."""
        self._state[key] = value

        # Persist to database
        if self._writer:
            import asyncio
            asyncio.create_task(self._writer.write(
                table_name="module_state",
                data={"key": key, "value": value}
            ))

        return f"Set {key} = {value}"
```

## Error Handling

```python
@tool(readonly=False)
def risky_operation(self, value: int) -> str:
    """An operation that might fail."""
    try:
        if value < 0:
            raise ValueError("Value must be non-negative")
        # Do the operation
        return f"Success: {value * 2}"
    except ValueError as e:
        return f"Error: {str(e)}"
    except Exception as e:
        return f"Unexpected error: {str(e)}"
```

## Module Registration

### Basic Registration

```python
from agentsociety2.env import ReActRouter

# Create router
router = ReActRouter()

# Register module with default name (class name)
router.register_module(MyModule())

# Register with custom name
router.register_module(MyModule(), name="custom_name")
```

### Multiple Modules

```python
router = ReActRouter()
router.register_module(WeatherModule(), name="weather")
router.register_module(EconomyModule(), name="economy")
router.register_module(SocialModule(), name="social")
```

## MCP Discovery

For VSCode extension integration, your module should be discoverable:

### File Naming

Place your module in a file like `my_module.py` or `myenv/` directory.

### Module Structure

```python
# my_module.py
from agentsociety2.env import EnvBase, tool

class MyCustomModule(EnvBase):
    """A custom environment module for X."""

    @tool(readonly=True, kind="observe")
    def get_value(self, agent_id: int) -> str:
        """Get a value."""
        return "value"
```

The extension will automatically:
1. Discover the class
2. Extract tool definitions
3. Register tools with the router
4. Make it available to agents

## Best Practices

1. **Keep modules focused**: Each module should have a single responsibility
2. **Use clear names**: Tool and parameter names should be self-documenting
3. **Return descriptive messages**: Help agents understand what happened
4. **Validate inputs**: Check parameter ranges and types
5. **Handle errors gracefully**: Return error messages, don't raise
6. **Document tools**: Good docstrings help agents use tools correctly
7. **Consider replay**: Store important state changes in ReplayWriter
8. **Thread safety**: Use async properly if accessing shared resources

## Example Modules

See the `agentsociety2/contrib/env/` package for examples:

- `SimpleSocialSpace` - Basic social interaction
- `PublicGoodsGame` - Economic game
- `PrisonersDilemma` - Classic game theory
- `EconomySpace` - Economic simulation
- `MobilitySpace` - Geographic movement

## Testing Your Module

```python
import asyncio
from agentsociety2.env import ReActRouter
from agentsociety2 import PersonAgent

async def test_module():
    # Setup
    router = ReActRouter()
    module = MyModule()
    router.register_module(module)

    # Create agent
    agent = PersonAgent(id=1, profile={"name": "Tester"})
    agent.set_env(router)

    # Test
    response = await agent.ask("What can you tell me about this environment?")
    print(response)

asyncio.run(test_module())
```

## Integration Checklist

- [ ] Module inherits from EnvBase
- [ ] Tools use @tool decorator
- [ ] Observation capability exposed through readonly `kind="observe"` tool(s)
- [ ] Error handling in place
- [ ] Docstrings for all tools
- [ ] File follows naming convention
- [ ] Tested with agents
- [ ] State persistence considered
- [ ] Thread-safe (if needed)
