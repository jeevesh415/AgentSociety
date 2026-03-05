Custom Modules
==============

AgentSociety 2 supports creating and registering custom Agent and Environment modules,
allowing you to extend the platform with your own simulation components.

Overview
--------

The custom module system allows you to:

* Create custom Agent classes with specialized behaviors
* Create custom Environment modules with domain-specific tools
* Automatically discover and register modules via API
* Test custom modules with auto-generated test scripts
* Seamlessly integrate with the existing AgentSociety framework

Directory Structure
-------------------

Custom modules are placed in the ``custom/`` directory within your workspace::

   workspace/
   ├── custom/                    # User-created directory
   │   ├── agents/                # Custom Agent classes
   │   │   └── my_agent.py
   │   └── envs/                  # Custom Environment modules
   │       └── my_env.py
   └── .agentsociety/             # Auto-generated configs
       ├── agent_classes/
       └── env_modules/

Creating a Custom Agent
-------------------------

All custom Agents must inherit from :class:`~agentsociety2.agent.base.AgentBase`
and implement the required methods:

.. code-block:: python

   from agentsociety2.agent.base import AgentBase
   from datetime import datetime
   from typing import Any

   class MyAgent(AgentBase):
       """My custom Agent"""

       @classmethod
       def mcp_description(cls) -> str:
           return """MyAgent: A custom agent for specific tasks

       This agent demonstrates custom behavior.
       """

       async def ask(self, message: str, readonly: bool = True) -> str:
           """Respond to questions from the environment"""
           prompt = f"Question: {message}\nPlease answer:"
           response = await self.acompletion([{"role": "user", "content": prompt}])
           return response.choices[0].message.content or ""

       async def step(self, tick: int, t: datetime) -> str:
           """Execute one simulation step"""
           return f"Agent {self.id} executing step {tick}"

       async def dump(self) -> dict:
           """Serialize agent state"""
           return {"id": self._id, "profile": self._profile}

       async def load(self, dump_data: dict):
           """Load agent state"""
           self._id = dump_data.get("id", self._id)
           self._profile = dump_data.get("profile", self._profile)

Required Methods
~~~~~~~~~~~~~~~~

.. list-table::
   :header-rows: 1

   * - Method
     - Description
   * - :py:meth:`mcp_description`
     - Return module description (class method)
   * - :py:meth:`ask`
     - Answer questions from environment
   * - :py:meth:`step`
     - Execute one simulation step
   * - :py:meth:`dump`
     - Serialize agent state
   * - :py:meth:`load`
     - Load agent state from dictionary

Creating a Custom Environment
------------------------------

Custom environments must inherit from :class:`~agentsociety2.env.base.EnvBase`
and use the ``@tool`` decorator to register methods:

.. code-block:: python

   from agentsociety2.env import EnvBase, tool
   from datetime import datetime

   class MyEnv(EnvBase):
       """My custom environment"""

       def __init__(self, config=None):
           super().__init__()
           # Initialize your environment state

       @classmethod
       def mcp_description(cls) -> str:
           return """MyEnv: A custom environment

       This environment provides custom tools for agents.
       """

       @tool(readonly=True, kind="observe")
       async def get_state(self, agent_id: int) -> dict:
           """Get current environment state (observation tool)"""
           return {"agent_id": agent_id, "state": "normal"}

       @tool(readonly=False)
       async def do_action(self, agent_id: int, action: str) -> dict:
           """Perform an action (modification tool)"""
           return {"agent_id": agent_id, "action": action, "result": "success"}

       async def step(self, tick: int, t: datetime):
           """Environment step"""
           self.t = t

The @tool Decorator
~~~~~~~~~~~~~~~~~~~

The ``@tool`` decorator registers methods as agent-accessible tools:

.. list-table::
   :header-rows: 1

   * - Parameter
     - Description
   * - ``readonly=True``
     - Tool doesn't modify environment state
   * - ``readonly=False``
     - Tool can modify environment state
   * - ``kind="observe"``
     - Observation tool (single agent_id parameter, readonly=True)
   * - ``kind="statistics"``
     - Statistics tool (no parameters, readonly=True)
   * - ``kind=None``
     - Regular tool (any parameters, can be readonly=False)

Registering Custom Modules
---------------------------

After creating your custom modules, register them using the API:

**Scan and Register**

.. code-block:: bash

   curl -X POST http://localhost:8001/api/v1/custom/scan \
     -H "Content-Type: application/json" \
     -d '{"workspace_path": "/path/to/workspace"}'

**List Registered Modules**

.. code-block:: bash

   curl http://localhost:8001/api/v1/custom/list

**Test Custom Modules**

.. code-block:: bash

   curl -X POST http://localhost:8001/api/v1/custom/test \
     -H "Content-Type: application/json" \
     -d '{"workspace_path": "/path/to/workspace"}'

API Endpoints
~~~~~~~~~~~~~

.. list-table::
   :header-rows: 1

   * - Endpoint
     - Method
     - Description
   * - ``/api/v1/custom/scan``
     - POST
     - Scan and register custom modules
   * - ``/api/v1/custom/test``
     - POST
     - Test custom modules
   * - ``/api/v1/custom/clean``
     - POST
     - Clean custom module configs
   * - ``/api/v1/custom/list``
     - GET
     - List registered custom modules
   * - ``/api/v1/custom/status``
     - GET
     - Get module status overview

Examples
--------

Example agents and environments are available in the ``custom/`` directory:

* ``custom/agents/examples/simple_agent.py`` - Basic Agent example
* ``custom/agents/examples/advanced_agent.py`` - Agent with memory and mood
* ``custom/envs/examples/simple_env.py`` - Counter environment
* ``custom/envs/examples/advanced_env.py`` - Resource management environment

These examples demonstrate best practices for creating custom modules.

Configuration
-------------

Set the ``WORKSPACE_PATH`` environment variable to point to your workspace:

.. code-block:: bash

   export WORKSPACE_PATH=/path/to/workspace

Or add to your ``.env`` file:

.. code-block:: ini

   WORKSPACE_PATH=/path/to/workspace

This setting tells the system where to find the ``custom/`` directory.

Best Practices
--------------

**Naming Conventions**

* Agent class names should end with ``Agent``
* Environment class names should end with ``Env``
* File names should use lowercase with underscores: ``my_agent.py``

**Error Handling**

* Always wrap LLM calls in try-except blocks
* Return meaningful error messages
* Log important state changes

**State Management**

* Use :py:meth:`dump` and :py:meth:`load` for state persistence
* Record important state changes in replay
* Keep state serializable (JSON compatible)

**Tool Design**

* Use ``kind="observe"`` for read-only observations
* Use ``kind="statistics"`` for aggregate data
* Use ``kind=None`` with ``readonly=False`` for actions
