Quick Start
===========

This guide will help you get started with AgentSociety 2 quickly.

Your First Agent
----------------

Let's create a simple agent and interact with it using **AgentSociety**:

.. code-block:: python

   import asyncio
   from datetime import datetime
   from agentsociety2 import PersonAgent
   from agentsociety2.env import CodeGenRouter
   from agentsociety2.contrib.env import SimpleSocialSpace
   from agentsociety2.society import AgentSociety

   async def main():
       # Create an agent with a profile
       agent = PersonAgent(
           id=1,
           profile={
               "name": "Alice",
               "age": 28,
               "personality": "friendly and curious",
               "bio": "A software engineer who loves hiking."
           }
       )

       # Create environment module with agent info
       social_env = SimpleSocialSpace(
           agent_id_name_pairs=[(agent.id, agent.name)]
       )

       # Create environment router
       env_router = CodeGenRouter(env_modules=[social_env])

       # Create the society
       society = AgentSociety(
           agents=[agent],
           env_router=env_router,
           start_t=datetime.now(),
       )

       # Initialize (sets up agents with environment)
       await society.init()

       # Query (read-only)
       response = await society.ask("What's your favorite activity?")
       print(f"Agent: {response}")

       # Close the society
       await society.close()

   if __name__ == "__main__":
       asyncio.run(main())

Running this code will produce output like:

.. code-block:: text

   Agent: I really enjoy hiking! There's something peaceful about being
   out in nature, exploring new trails, and taking in the beautiful scenery.
   It's a great way to clear my mind and stay active.

Creating a Custom Environment
------------------------------

Environment modules allow agents to interact with specific functionality:

.. code-block:: python

   from agentsociety2.env import EnvBase, tool, CodeGenRouter

   class MyEnvironment(EnvBase):
       """A custom environment module."""

       @tool(readonly=True, kind="observe")
       def get_weather(self, agent_id: int) -> str:
           """Get the current weather."""
           return "The weather is sunny and 25°C."

       @tool(readonly=False)
       def set_mood(self, agent_id: int, mood: str) -> str:
           """Change the mood of an agent."""
           return f"Agent {agent_id}'s mood is now {mood}."

   # Use the custom module with AgentSociety
   agent = PersonAgent(id=1, profile={"name": "Bob"})

   env_router = CodeGenRouter(env_modules=[MyEnvironment()])

   society = AgentSociety(
       agents=[agent],
       env_router=env_router,
       start_t=datetime.now(),
   )
   await society.init()

   # Agent can now use the environment's tools
   response = await society.ask("What's the weather like?")
   print(response)

   await society.close()

Running an Experiment
---------------------

Here's a complete experiment with multiple agents using AgentSociety:

.. code-block:: python

   import asyncio
   from datetime import datetime
   from agentsociety2 import PersonAgent
   from agentsociety2.env import CodeGenRouter
   from agentsociety2.contrib.env import SimpleSocialSpace
   from agentsociety2.storage import ReplayWriter
   from agentsociety2.society import AgentSociety

   async def main():
       # Setup replay writer for tracking
       writer = ReplayWriter("my_experiment.db")
       await writer.initialize()

       # Create agents first (needed for SimpleSocialSpace)
       agents = [
           PersonAgent(
               id=i,
               profile={"name": f"Player{i}", "personality": "competitive"},
               replay_writer=writer
           )
           for i in range(1, 4)
       ]

       # Create environment router
       env_router = CodeGenRouter(
           env_modules=[SimpleSocialSpace(
               agent_id_name_pairs=[(a.id, a.name) for a in agents]
           )]
       )
       env_router.set_replay_writer(writer)

       # Create the society with replay enabled
       society = AgentSociety(
           agents=agents,
           env_router=env_router,
           start_t=datetime.now(),
           replay_writer=writer,
       )
       await society.init()

       # Run interactions
       for agent in agents:
           response = await society.ask(
               f"Tell {agent._name} to introduce themselves to the group!"
           )
           print(f"{agent._name}: {response}")

       await society.close()

   if __name__ == "__main__":
       asyncio.run(main())

Next Steps
----------

Now that you have the basics, explore:

* :doc:`agents` - Learn about agents in detail
* :doc:`env_modules` - Create custom environment modules
* :doc:`concepts` - Understand core concepts
* :doc:`storage` - Learn about the replay system
* :doc:`examples` - See more examples

Common Patterns
---------------

Read-Only Queries
~~~~~~~~~~~~~~~~~

For queries that don't modify state, use ``society.ask()``:

.. code-block:: python

   # society.ask() ensures read-only access
   response = await society.ask("What agents are in the simulation?")

Making Changes
~~~~~~~~~~~~~~

For actions that modify the environment, use ``society.intervene()``:

.. code-block:: python

   # society.intervene() allows environment modifications
   result = await society.intervene("Set everyone's mood to happy")

Querying Specific Agents
~~~~~~~~~~~~~~~~~~~~~~~~~

To direct questions to specific agents:

.. code-block:: python

   # Ask a specific agent
   response = await society.ask(
       "Alice, what do you think about the current situation?"
   )
