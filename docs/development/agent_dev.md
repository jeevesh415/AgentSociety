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

`PersonAgent` 是默认的 **skills-first** 智能体：它本身是一个轻量的“工具调度器”，通过 **技能目录（skill catalog）+ 工具调用** 在每个 step 内自主完成任务。

关键特性：

- 每个 Person 是 **独立会话线程 + 独立工作目录**（agent workspace），避免多 agent 互相污染
- **渐进式披露**：默认只暴露少量核心技能（`core_skills`），其余技能需要显式启用/激活
- 技能作者只需写 `SKILL.md`（以及可选脚本），无需了解 `PersonAgent` 内部实现

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

PersonAgent 的技能体系遵循 “先看到目录 → 再激活技能说明 → 再执行” 的工作流：

1. **目录（catalog）**：system prompt 中包含可见技能的名称与简述
2. **激活（activate）**：用 `activate_skill` 加载某个 skill 的完整说明
3. **执行（execute）**：用 `execute_skill` 运行技能入口逻辑

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

当前版本不推荐通过 `PersonAgent` 暴露“直接改技能列表”的 Python 方法（避免业务逻辑耦合到 agent 内部）。
推荐做法：

- 在创建 agent 时通过 `core_skills` 控制默认可见的核心技能集合
- 运行过程中通过工具调用（如 `enable_skill` / `disable_skill` / `activate_skill`）完成技能启用与说明加载

## Memory Integration

当前版本的记忆属于 skill（例如 `memory`），由技能自行定义“写什么、何时写、写到哪里”。`PersonAgent` 只负责提供工作目录与工具能力，并不绑定某个第三方记忆库实现。

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
