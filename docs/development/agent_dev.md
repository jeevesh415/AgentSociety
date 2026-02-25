# Agent Development Guide

This guide explains how to develop custom agents for AgentSociety 2.

## Overview

Agents in AgentSociety 2 are autonomous entities that interact with environments through LLM-powered reasoning. This guide covers how to create custom agents for your specific use cases.

## Base Agent Classes

### AgentBase

The `AgentBase` is the abstract base class for all agents:

```python
from agentsociety2.agent import AgentBase
from agentsociety2.config import get_llm_router_and_model

class MyAgent(AgentBase):
    def __init__(self, id: int, profile: dict, **kwargs):
        super().__init__(id=id, profile=profile, **kwargs)
        # Your custom initialization
        self._custom_attribute = "value"

    async def ask(self, question: str, readonly: bool = True) -> str:
        """Override to customize behavior."""
        # Your custom logic here
        return await super().ask(question, readonly=readonly)
```

### PersonAgent

`PersonAgent` is a ready-to-use implementation with common person agent features:

```python
from agentsociety2 import PersonAgent

agent = PersonAgent(
    id=1,
    profile={
        "name": "Alice",
        "age": 28,
        "personality": "friendly and curious"
    }
)
```

## Creating Custom Agents

### Step 1: Define Your Agent Class

```python
from agentsociety2.agent import AgentBase
from typing import Optional
from agentsociety2.storage import ReplayWriter

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
        self._knowledge_base = []  # Custom knowledge storage
```

### Step 2: Override Key Methods

#### The ask() Method

This is the primary interaction method:

```python
async def ask(self, question: str, readonly: bool = True) -> str:
    """Process a question with specialty context."""

    # Add specialty context
    enhanced_question = (
        f"You are a specialist in {self._specialty}. "
        f"Answer this question from that perspective: {question}"
    )

    # Call parent implementation
    return await super().ask(enhanced_question, readonly=readonly)
```

#### Adding Custom Methods

```python
async def consult_knowledge_base(self, query: str) -> str:
    """Search the agent's knowledge base."""
    results = [item for item in self._knowledge_base if query.lower() in item.lower()]
    if results:
        return f"Found in knowledge base: {results[0]}"
    return "No relevant information found in knowledge base."

async def learn(self, information: str) -> str:
    """Add new information to knowledge base."""
    self._knowledge_base.append(information)
    return f"Learned: {information}"
```

### Step 3: Implement MCP Discovery (Optional)

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

## Memory Integration

Enable mem0ai for persistent memory:

```python
from agentsociety2 import PersonAgent

agent = PersonAgent(
    id=1,
    profile={"name": "Alice"},
    enable_memory=True  # Enable memory
)

# The agent will now remember past interactions
await agent.ask("My favorite color is blue", readonly=True)
await agent.ask("What's my favorite color?", readonly=True)  # Will remember!
```

## Example Implementations

### Specialist Agent

```python
class SpecialistAgent(AgentBase):
    """Domain expert agent."""

    def __init__(self, id: int, profile: dict, specialty: str, **kwargs):
        super().__init__(id=id, profile=profile, **kwargs)
        self._specialty = specialty

    async def ask(self, question: str, readonly: bool = True) -> str:
        context = f"As a {self._specialty} specialist, answer: {question}"
        return await super().ask(context, readonly=readonly)
```

### Chain-of-Thought Agent

```python
class CoTAgent(AgentBase):
    """Agent that uses explicit chain-of-thought reasoning."""

    async def ask(self, question: str, readonly: bool = True) -> str:
        # First, think step by step
        thought_prompt = (
            "Think step by step to solve this problem. "
            f"Show your reasoning: {question}"
        )
        thoughts = await super().ask(thought_prompt, readonly=True)

        # Then, provide final answer
        answer_prompt = (
            f"Based on this reasoning: {thoughts}\n\n"
            f"Provide a clear, concise answer to: {question}"
        )
        return await super().ask(answer_prompt, readonly=readonly)
```

### Emotional Agent

```python
class EmotionalAgent(AgentBase):
    """Agent with dynamic emotional state."""

    def __init__(self, id: int, profile: dict, **kwargs):
        super().__init__(id=id, profile=profile, **kwargs)
        self._emotions = {
            "happiness": 0.5,
            "sadness": 0.1,
            "anger": 0.1,
            "fear": 0.1,
            "surprise": 0.2
        }

    async def ask(self, question: str, readonly: bool = True) -> str:
        # Add emotional context to the question
        dominant_emotion = max(self._emotions, key=self._emotions.get)
        emotional_context = (
            f"You are feeling {dominant_emotion} (intensity: {self._emotions[dominant_emotion]}). "
            f"This affects your response. {question}"
        )
        return await super().ask(emotional_context, readonly=readonly)

    async def update_emotion(self, emotion: str, delta: float):
        """Update an emotion by delta value."""
        self._emotions[emotion] = max(0, min(1, self._emotions.get(emotion, 0) + delta))
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
    agent = MyAgent(
        id=1,
        profile={"name": "Test Agent"},
        specialty="testing"
    )
    agent.set_env(env)

    # Test it
    response = await agent.ask("Hello! Who are you?")
    print(response)

asyncio.run(test_my_agent())
```

## Best Practices

1. **Keep profiles specific**: Detailed profiles lead to more consistent behavior
2. **Use type hints**: Helps with IDE support and documentation
3. **Add docstrings**: Essential for MCP discovery
4. **Test thoroughly**: Test with various questions and scenarios
5. **Handle errors gracefully**: Use try-except for external API calls
6. **Log important events**: Use the logger for debugging

## Integration with VSCode Extension

To make your agent discoverable by the VSCode extension:

1. Place your agent file in a known location
2. Implement `mcp_description()` classmethod
3. Follow naming conventions: `*Agent.py`
4. Add type hints for all parameters

The extension will automatically discover and register your agent.
