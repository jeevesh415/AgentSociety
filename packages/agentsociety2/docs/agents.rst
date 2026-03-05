Working with Agents
===================

This section covers how to work with agents in AgentSociety 2.

Creating Agents
---------------

PersonAgent
~~~~~~~~~~~

The ``PersonAgent`` class is a ready-to-use agent
implementation:

.. code-block:: python

   from agentsociety2 import PersonAgent

   agent = PersonAgent(
       id=1,
       profile={
           "name": "Alice",
           "age": 28,
           "personality": "friendly and curious",
           "bio": "A software engineer who loves hiking."
       }
   )

The profile can contain any fields you want. The agent will use this
information to shape its responses and decisions.

Custom Agents
~~~~~~~~~~~~~

To create a custom agent, inherit from ``AgentBase``
and implement the required abstract methods:

Required Methods to Implement
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

When creating a custom agent, you must implement these abstract methods from
``AgentBase``:

1. **async def ask(self, message: str, readonly: bool = True) -> str**

   Process a question from the environment or user and return a response.

   Args:
       message: The question or instruction to process
       readonly: Whether the agent can modify the environment (False = can modify)

   Returns:
       The agent's response as a string

2. **async def step(self, tick: int, t: datetime) -> str**

   Execute one simulation step. This is called by AgentSociety during
   simulation runs.

   Args:
       tick: Duration of this step in seconds
       t: Current simulation datetime after this step

   Returns:
       A description of the agent's action during this step

3. **async def dump(self) -> dict**

   Serialize the agent's state to a dictionary for saving/loading.

4. **async def load(self, dump_data: dict)**

   Restore the agent's state from a previously dumped dictionary.

Reference Implementation
^^^^^^^^^^^^^^^^^^^^^^^^

For a complete reference, see ``PersonAgent``
in the source code.

Example:
^^^^^^^^

.. code-block:: python

   from agentsociety2.agent import AgentBase
   from datetime import datetime

   class MyAgent(AgentBase):
       def __init__(self, id: int, profile: dict, **kwargs):
           super().__init__(id=id, profile=profile, **kwargs)
           # Add custom initialization
           self._custom_state = profile.get("custom_field", {})

       async def ask(self, question: str, readonly: bool = True) -> str:
           # Process the question and return a response
           # Use self._env to interact with the environment
           return await super().ask(question, readonly=readonly)

       async def step(self, tick: int, t: datetime) -> str:
           # Execute one simulation step
           return await super().step(tick, t)

       async def dump(self) -> dict:
           # Save state
           return {
               "custom_state": self._custom_state,
               "profile": self._profile,
           }

       async def load(self, dump_data: dict):
           # Restore state
           self._custom_state = dump_data.get("custom_state", {})

Agent Profiles
--------------

Profile Design
~~~~~~~~~~~~~~

A good agent profile should include:

* **Identity**: Name, age, role
* **Personality**: Traits, preferences, quirks
* **Background**: History, expertise, relationships
* **Goals**: Motivations, desires, fears

.. code-block:: python

   profile = {
       # Identity
       "name": "Dr. Sarah Chen",
       "age": 35,
       "occupation": "climate scientist",

       # Personality
       "personality": "analytical, passionate, slightly anxious",
       "traits": ["detail-oriented", "empathetic", "curious"],

       # Background
       "education": "PhD in Atmospheric Science",
       "experience": "10 years in climate research",
       "achievements": ["Published 30+ papers", "Nobel nominee"],

       # Goals
       "goal": "raise awareness about climate change",
       "fears": ["sea level rise", "ecosystem collapse"]
   }

Interacting with Agents
-----------------------

The ask() Method
~~~~~~~~~~~~~~~~

.. code-block:: python

   response = await agent.ask(
       "What's your opinion on renewable energy?",
       readonly=True  # No side effects
   )

The ``readonly`` parameter controls whether the agent can modify the
environment:

* ``readonly=True``: Query only, no side effects
* ``readonly=False``: May call environment tools that modify state

The step() Method
~~~~~~~~~~~~~~~~~

The ``step()`` method is called automatically during AgentSociety simulations:

.. code-block:: python

   # Called by AgentSociety.run() or AgentSociety.run_to()
   # tick = duration in seconds, t = current simulation time
   action_description = await agent.step(tick=3600, t=datetime.now())

Replay Tracking
~~~~~~~~~~~~~~~

.. code-block:: python

   from agentsociety2.storage import ReplayWriter

   writer = ReplayWriter("experiment.db")
   await writer.initialize()

   agent = PersonAgent(id=1, profile=..., replay_writer=writer)

Agent Memory
------------

AgentSociety 2 integrates with `mem0ai`_ for memory management:

.. code-block:: python

   # Enable memory for an agent
   from agentsociety2 import PersonAgent

   agent = PersonAgent(
       id=1,
       profile={"name": "Alice"},
       enable_memory=True  # Enable memory
   )

With memory enabled, agents can:

* Remember past interactions
* Recall relevant information
* Build context over time

.. _mem0ai: https://github.com/mem0ai/mem0
