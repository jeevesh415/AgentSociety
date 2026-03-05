Environment Modules
==================

This section covers how to create and work with environment modules.

Creating Custom Modules
------------------------

Inherit from EnvBase
~~~~~~~~~~~~~~~~~~~~

To create a custom environment module, inherit from
``EnvBase`` and implement the required methods:

Required Methods to Implement
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

When creating a custom environment module, you must implement:

1. **def observe(self) -> str**

   Return a string description of the current state of the module.
   This is used to generate the world description for agents.

   Returns:
       A string describing the module's current state

2. **async def step(self, tick: int, t: datetime) -> None**

   Execute one simulation step. This is called automatically during
   AgentSociety simulations. Use this to update time-dependent state.

   Args:
       tick: Duration of this step in seconds
       t: Current simulation datetime after this step

3. **Tools decorated with @tool**

   Use the ``@tool`` decorator to expose methods as callable functions
   for agents.

   .. code-block:: python

      from agentsociety2.env import EnvBase, tool

      class MyModule(EnvBase):
          def __init__(self):
              super().__init__()
              # Your initialization

          def observe(self) -> str:
              """Return the current state of the module."""
              return "Current state description"

          @tool(readonly=True, kind="observe")
          def get_value(self, agent_id: int) -> str:
              """Get a value for an agent."""
              return f"Value for agent {agent_id}"

          @tool(readonly=False)
          def set_value(self, agent_id: int, value: int) -> str:
              """Set a value for an agent."""
              self._values[agent_id] = value
              return f"Set value for agent {agent_id}"

Reference Implementation
^^^^^^^^^^^^^^^^^^^^^^^^

For complete reference implementations, see:

* ``SimpleSocialSpace`` - Social interaction module
* ``PublicGoodsGame`` - Public goods game module
* ``PrisonersDilemma`` - Prisoner's dilemma module

The @tool Decorator
~~~~~~~~~~~~~~~~~~~

The ``@tool`` decorator marks methods as callable by agents:

.. code-block:: python

   from agentsociety2.env import tool

   @tool(readonly=True, kind="observe")
   def get_status(self, agent_id: int) -> str:
       """Get the status of an agent."""
       return f"Agent {agent_id} status"

Parameters:

* **readonly** (bool): Whether the tool modifies the environment
  * ``True`` = read-only, can be used in queries
  * ``False`` = modifies state, can be used in interventions

* **kind** (str): The type of tool
  * ``"observe"``: Single-parameter observations (requires readonly=True)
  * ``"statistics"``: Aggregate queries (no parameters, requires readonly=True)
  * ``None`` or omitted: Regular tool (any signature, any readonly value)

Tool Types
----------

* **observe**: Single-parameter observations (readonly=True required)
* **statistics**: Aggregate queries (no parameters, readonly=True required)
* **regular**: Any other tool (can be readonly or read-write)

See :doc:`concepts` for more details on tool types.

Registering Modules
--------------------

.. code-block:: python

   from agentsociety2.env import CodeGenRouter

   router = CodeGenRouter()
   router.register_module(MyModule(), name="my_module")

   # Or with default name (class name)
   router.register_module(MyModule())

Complete Example
-----------------

.. code-block:: python

   from typing import Dict
   from datetime import datetime
   from agentsociety2.env import EnvBase, tool, CodeGenRouter
   from agentsociety2 import PersonAgent
   from agentsociety2.society import AgentSociety

   class WeatherEnvironment(EnvBase):
       """A simple weather environment module."""

       def __init__(self):
           super().__init__()
           self._weather = "sunny"
           self._temperature = 25
           self._agent_locations: Dict[int, str] = {}

       @tool(readonly=True, kind="observe")
       def get_weather(self, agent_id: int) -> str:
           """Get the current weather for an agent's location."""
           location = self._agent_locations.get(agent_id, "unknown")
           return f"The weather in {location} is {self._weather} with {self._temperature}°C."

       @tool(readonly=False)
       def change_weather(self, weather: str, temperature: int) -> str:
           """Change the weather conditions."""
           self._weather = weather
           self._temperature = temperature
           return f"Weather changed to {weather} at {temperature}°C."

       def observe(self) -> str:
           """Return the overall state of the environment."""
           return (
               f"Environment State:\n"
               f"- Weather: {self._weather}\n"
               f"- Temperature: {self._temperature}°C"
           )

       async def step(self, tick: int, t: datetime) -> None:
           """Update environment state for one simulation step."""
           self.t = t
           # Update time-dependent state here if needed

   # Use the custom module
   env_router = CodeGenRouter(env_modules=[WeatherEnvironment()])

   agent = PersonAgent(id=1, profile={"name": "Bob"})

   society = AgentSociety(
       agents=[agent],
       env_router=env_router,
       start_t=datetime.now(),
   )
   await society.init()

Examples
--------

See the :mod:`agentsociety2.contrib.env` package for example modules:

* :mod:`~agentsociety2.contrib.env.SimpleSocialSpace`
* :mod:`~agentsociety2.contrib.env.PublicGoodsGame`
* :mod:`~agentsociety2.contrib.env.PrisonersDilemma`
* :mod:`~agentsociety2.contrib.env.TrustGame`
