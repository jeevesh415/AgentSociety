Core Concepts
=============

This section explains the core concepts of AgentSociety 2.

Architecture Overview
---------------------

AgentSociety 2 is built around three main components:

* **Agents**: Autonomous entities that interact with environments using LLMs
* **Environment Modules**: Composable components that define simulation rules
* **AgentSociety**: The coordinator that manages agents and environments

.. graphviz::

   digraph agentsociety2 {
       rankdir=TB;
       node [shape=box, style=rounded];

       Agent [label="Agent"];
       CodeGenRouter [label="CodeGenRouter"];
       EnvModule [label="Env Module"];
       Tool [label="@tool()"];

       Agent -> CodeGenRouter [label="ask/intervene"];
       CodeGenRouter -> EnvModule [label="calls tools"];
       EnvModule -> Tool [label="decorated with"];
   }

Agent-Environment Interface
----------------------------

Agents interact with environments through two main methods:

* **ask()**: Query or observe the environment state
* **intervene()**: Modify the environment state

This unified interface allows agents to communicate naturally with any environment module.

The @tool Decorator
-------------------

Environment modules expose their functionality through the ``@tool`` decorator:

.. code-block:: python

   from agentsociety2.env import EnvBase, tool

   class MyEnvironment(EnvBase):
       @tool(readonly=True, kind="observe")
       def get_weather(self, agent_id: int) -> str:
           """Get the current weather for an agent."""
           return f"Weather for agent {agent_id}"

       @tool(readonly=False)
       def set_temperature(self, temp: int) -> str:
           """Set the temperature."""
           self._temperature = temp
           return f"Temperature set to {temp}"

**Parameters:**

* ``readonly`` (bool): Whether the function modifies state
  * ``True`` = read-only observation
  * ``False`` = modifies environment

* ``kind`` (str): Function category for optimization
  * ``"observe"``: Single-parameter observations
  * ``"statistics"``: Aggregate queries (no parameters)
  * ``None``: Regular tool

CodeGenRouter
-------------

CodeGenRouter connects agents to environment modules by:

1. Extracting tool signatures from environment modules
2. Generating code to call appropriate tools based on agent input
3. Executing the code safely in a sandboxed environment
4. Returning results to the agent

This approach allows agents to interact with any combination of environment modules without code changes.

Tool Categories
---------------

**Observe Tools** (``readonly=True``, ``kind="observe"``)

Agent-specific observations with a single ``agent_id`` parameter:

.. code-block:: python

   @tool(readonly=True, kind="observe")
   def get_agent_location(self, agent_id: int) -> str:
       """Get the current location of an agent."""
       return f"Agent {agent_id} is at location X"

**Statistics Tools** (``readonly=True``, ``kind="statistics"``)

Aggregate queries with no parameters (except ``self``):

.. code-block:: python

   @tool(readonly=True, kind="statistics")
   def get_average_happiness(self) -> str:
       """Get the average happiness of all agents."""
       avg = sum(self.happiness.values()) / len(self.happiness)
       return f"Average happiness: {avg}"

**Regular Tools**

General-purpose tools with any signature:

.. code-block:: python

   @tool(readonly=False)
   def set_happiness(self, agent_id: int, value: float) -> str:
       """Set an agent's happiness level."""
       self.happiness[agent_id] = value
       return f"Set agent {agent_id} happiness to {value}"
