# Agent Development Guide

This guide explains how to develop custom agents for AgentSociety 2.

## Overview

Agents in AgentSociety 2 are autonomous entities that interact with environments through LLM-powered reasoning. This guide covers how to create custom agents for your specific use cases.

## Base Agent Classes

### AgentBase

The `AgentBase` is the abstract base class for all agents:

```python
from agentsociety2.agent import AgentBase

class MyAgent(AgentBase):
    def __init__(self, id: int, profile: dict, **kwargs):
        super().__init__(id=id, profile=profile, **kwargs)
        # Your custom initialization

    async def ask(self, message: str, readonly: bool = True) -> str:
        """Process a question and return response."""
        # Your custom logic here
        return "Response"

    async def step(self, tick: int, t: datetime) -> str:
        """Execute one simulation step."""
        return "Step completed"

    async def dump(self) -> dict:
        """Serialize agent state."""
        return {"id": self.id}

    async def load(self, dump_data: dict):
        """Restore agent state from dict."""
        pass
```

### PersonAgent

`PersonAgent` is a sophisticated agent with memory, needs, emotions, and planning capabilities. It uses a **skills-based architecture** where capabilities are provided by pluggable skill modules.

```python
from agentsociety2 import PersonAgent

agent = PersonAgent(
    id=1,
    profile={
        "name": "Alice",
        "age": 28,
        "personality": "friendly and curious",
        "profile_text": "A software engineer who loves hiking and reading."
    }
)
```

## Agent Skills Architecture

PersonAgent follows a **metadata-first, selected-only** model. Skills are self-contained modules that provide specific capabilities.

### Built-in Skills

Skills are located in `agent/skills/`:

```
agent/skills/
├── observation/        # SKILL.md + scripts/observation.py
├── memory/             # SKILL.md + scripts/memory.py
├── needs/              # SKILL.md + scripts/needs.py
├── cognition/          # SKILL.md + scripts/cognition.py
└── plan/               # SKILL.md + scripts/plan.py
```

Each skill has:
- `SKILL.md` — YAML frontmatter (name, description, priority, requires/provides) + behavior docs
- `scripts/<name>.py` — exports `async def run(agent, ctx)`

### Skill Selection Process

Skills follow metadata-first selection:

1. **Selection Stage**: LLM reads compact metadata (name/description/priority/requires/provides)
2. **Execution Stage**: Only LLM-selected skills are loaded and run
3. **Unselected Skills**: Not loaded, not executed

### Custom Skills

Custom skills can be placed in `workspace/custom/skills/` and hot-loaded at runtime via the API or VSCode extension.

#### Creating a Custom Skill

1. Create a directory with `SKILL.md`:

```markdown
---
name: my_custom_skill
description: A custom skill for X
priority: 100
requires: []
provides: [custom_capability]
---

# My Custom Skill

This skill does X, Y, Z.

## Behavior
...
```

2. Create the script `scripts/my_custom_skill.py`:

```python
"""My custom skill implementation."""

async def run(agent, ctx):
    """
    Execute the skill.

    Args:
        agent: The PersonAgent instance
        ctx: Context dict with step_log, tick, t, stop, etc.

    Returns:
        None (modifies agent state in-place)
    """
    # Your skill logic here
    agent._logger.info("Running custom skill")

    # Optionally stop further skill execution
    # ctx["stop"] = True

    # Log what happened
    ctx["step_log"].append("Custom skill executed")
```

### Skill State Management

Agents can store skill-specific state using the built-in state container:

```python
# In skill's run() function
async def run(agent, ctx):
    # Initialize state on first run
    if agent.get_skill_state("my_skill") is None:
        agent.set_skill_state("my_skill", {
            "counter": 0,
            "last_action": None
        })

    # Get and modify state
    state = agent.get_skill_state("my_skill")
    state["counter"] += 1
    state["last_action"] = "acted"
    agent.set_skill_state("my_skill", state)

    # Check if state exists
    if agent.has_skill_state("my_skill"):
        state = agent.get_skill_state("my_skill")

    # Clear state if needed
    agent.clear_skill_state("my_skill")
```

### Enabling/Disabling Skills

```python
# Enable only specific skills
agent = PersonAgent(
    id=1,
    profile={"name": "Alice"},
    skill_names=["observation", "memory", "plan"]  # Only these skills
)

# Dynamically add/remove skills at runtime
agent.add_skill("needs")
agent.remove_skill("plan")

# Reload all skills
agent.reload_skills()
```

## Memory Integration

PersonAgent automatically uses mem0ai for persistent memory. Configuration is managed via `Config.get_mem0_config()`.

The agent maintains:
- **Short-term memory**: Recent N interactions (configurable via `short_memory_window_size`)
- **Long-term memory**: Persistent storage via mem0
- **Cognition memory**: Temporary buffer for cognitive processes, flushed to long-term memory

```python
# Memory is automatically initialized
agent = PersonAgent(id=1, profile={"name": "Alice"})

# Access memory directly if needed
memories = await agent.memory.search("query", user_id=agent._memory_user_id, limit=10)
```

## Creating Custom Agents

### Step 1: Define Your Agent Class

```python
from agentsociety2.agent import AgentBase
from typing import Optional
from agentsociety2.storage import ReplayWriter
from datetime import datetime

class SpecialistAgent(AgentBase):
    """An agent with domain-specific expertise."""

    def __init__(
        self,
        id: int,
        profile: dict,
        specialty: str,
        replay_writer: Optional[ReplayWriter] = None,
        **kwargs
    ):
        super().__init__(id=id, profile=profile, replay_writer=replay_writer, **kwargs)
        self._specialty = specialty

    async def ask(self, message: str, readonly: bool = True) -> str:
        """Process a question with specialty context."""
        enhanced_question = (
            f"You are a specialist in {self._specialty}. "
            f"Answer this question from that perspective: {message}"
        )
        # Use LLM to generate response
        response = await self.acompletion(
            [{"role": "user", "content": enhanced_question}],
            stream=False
        )
        return response.choices[0].message.content

    async def step(self, tick: int, t: datetime) -> str:
        """Execute one simulation step."""
        return f"Specialist step completed"

    async def dump(self) -> dict:
        return {"id": self.id, "specialty": self._specialty}

    async def load(self, dump_data: dict):
        self._specialty = dump_data.get("specialty", "")
```

### Step 2: Implement MCP Description (Optional)

For VSCode extension integration:

```python
@classmethod
def mcp_description(cls) -> str:
    """Return description for MCP discovery."""
    return """SpecialistAgent - A domain-specialist agent.

Attributes:
    specialty (str): The domain of expertise

Usage:
    Create with a specialty parameter to give the agent
    domain-specific knowledge and perspective.
"""
```

## Agent Profiles

Design effective agent profiles with these components:

### Identity

```python
profile = {
    "name": "Dr. Sarah Chen",
    "age": 35,
    "occupation": "climate scientist",
    "location": "San Francisco, CA"
}
```

### Personality

```python
profile.update({
    "personality": "analytical, passionate, slightly anxious about climate change",
    "traits": ["detail-oriented", "empathetic", "curious"],
    "communication_style": "clear, scientific but accessible"
})
```

### Background

```python
profile.update({
    "education": "PhD in Atmospheric Science, MIT",
    "experience": "10 years in climate research",
    "achievements": [
        "Published 30+ peer-reviewed papers",
        "Nobel Prize nominee",
        "IPCC contributing author"
    ]
})
```

### Goals and Values

```python
profile.update({
    "goals": [
        "raise awareness about climate change",
        "influence policy decisions",
        "mentor young scientists"
    ],
    "values": ["scientific integrity", "environmental protection", "education"],
    "fears": ["sea level rise", "ecosystem collapse", "policy inaction"]
})
```

## LLM Integration

### Using the Agent's LLM

```python
# Simple completion
response = await agent.acompletion(
    [{"role": "user", "content": "What should I do today?"}],
    stream=False
)

# With system prompt (includes time context)
response = await agent.acompletion_with_system_prompt(
    messages=[{"role": "user", "content": "Hello"}],
    tick=3600,  # 1 hour
    t=datetime.now()
)

# With Pydantic validation
from pydantic import BaseModel

class MyResponse(BaseModel):
    action: str
    reasoning: str

result = await agent.acompletion_with_pydantic_validation(
    model_type=MyResponse,
    messages=[{"role": "user", "content": "Decide what to do"}],
    tick=3600,
    t=datetime.now()
)
print(result.action, result.reasoning)
```

### Token Usage Tracking

```python
# Get token usage statistics
usage = agent.get_token_usages()
for model_name, stats in usage.items():
    print(f"{model_name}: {stats.call_count} calls, "
          f"{stats.input_tokens} input, {stats.output_tokens} output")

# Reset statistics
agent.reset_token_usages()
```

## Testing Your Agent

```python
import asyncio
from agentsociety2.env import ReActRouter
from agentsociety2.contrib.env import SimpleSocialSpace

async def test_my_agent():
    # Setup environment
    env = ReActRouter()
    env.register_module(SimpleSocialSpace())

    # Create your agent
    agent = SpecialistAgent(
        id=1,
        profile={"name": "Test Agent"},
        specialty="testing"
    )
    await agent.init(env)

    # Test ask
    response = await agent.ask("Hello! Who are you?")
    print(response)

    # Test step
    result = await agent.step(tick=3600, t=datetime.now())
    print(result)

    # Clean up
    await agent.close()

asyncio.run(test_my_agent())
```

## Best Practices

1. **Keep profiles specific**: Detailed profiles lead to more consistent behavior
2. **Use type hints**: Helps with IDE support and documentation
3. **Add docstrings**: Essential for MCP discovery
4. **Test thoroughly**: Test with various questions and scenarios
5. **Handle errors gracefully**: Use try-except for external API calls
6. **Log important events**: Use the agent's logger for debugging
7. **Leverage skill states**: Store skill-specific data in `_skill_states`
8. **Use ReplayWriter**: Persist important state changes for experiment replay

## Integration with VSCode Extension

To make your agent discoverable by the VSCode extension:

1. Place your agent file in a known location (e.g., `custom/agents/`)
2. Implement `mcp_description()` classmethod
3. Follow naming conventions: `*Agent.py`
4. Add type hints for all parameters

The extension will automatically discover and register your agent.
