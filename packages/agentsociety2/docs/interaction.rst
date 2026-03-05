Interacting with AgentSociety
==============================

This guide explains how to interact with AgentSociety 2 during experiments.

Overview
--------

AgentSociety 2 provides two main modes of interaction:

1. **Query Mode** (read-only): Ask questions without modifying the simulation state
2. **Intervention Mode** (read-write): Modify agent states or environment variables

These interactions can be performed:

* **During simulation**: Between steps or at specific time points
* **After simulation**: Query the final state or collect survey data

Basic Interaction Patterns
---------------------------

The ask() Method - Read-Only Queries
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Use ``society.ask()`` for read-only queries that don't modify the simulation:

.. code-block:: python

   # Query about agent state
   response = await society.ask("What is Agent 1's current mood?")

   # Query about environment
   response = await society.ask("What is the current weather?")

   # Query about multiple agents
   response = await society.ask("List all agents who are unhappy")

The intervene() Method - Read-Write Modifications
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Use ``society.intervene()`` to make changes to the simulation:

.. code-block:: python

   # Send a message to agents
   result = await society.intervene(
       "Send a message to all agents: 'Severe weather coming, go home!'"
   )

   # Modify environment variables
   result = await society.intervene(
       "Change the weather to rainy and temperature to 15°C"
   )

   # Modify agent states
   result = await society.intervene(
       "Set all agents' happiness to 0.8"
   )

Simulation Workflow
-------------------

Running with Step-by-Step Control
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   from datetime import datetime, timedelta

   # Create and initialize society
   society = AgentSociety(
       agents=agents,
       env_router=env_router,
       start_t=datetime.now(),
   )
   await society.init()

   # Run for specific number of steps
   for step_num in range(10):
       # Query before step
       state = await society.ask("What's happening?")
       print(f"Step {step_num}: {state}")

       # Execute step (tick = duration in seconds)
       await society.step(tick=3600, t=datetime.now())

       # Intervene based on conditions
       if "emergency" in state.lower():
           await society.intervene("Broadcast emergency alert")

   await society.close()

Running with Time Control
~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   from datetime import datetime, timedelta

   # Run until specific end time
   end_time = datetime.now() + timedelta(days=1)
   await society.run_to(end_t=end_time, tick=3600)

   # Or run for specific number of steps
   await society.run(num_steps=24, tick=3600)  # 24 hours

Data Collection
---------------

Collecting Agent Responses
~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   # Collect responses from all agents
   for agent in agents:
       response = await society.ask(
           f"Agent {agent.id}, how do you feel about the current situation?"
       )
       print(f"Agent {agent.id}: {response}")
       # Store for analysis

   # Collect survey responses
   survey_questions = [
       "How satisfied are you with your current situation? (1-5)",
       "What would improve your quality of life?",
   ]

   for agent in agents:
       for question in survey_questions:
           answer = await society.ask(f"Agent {agent.id}: {question}")
           # Save answer to database or file

Using ReplayWriter for Data Collection
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   from agentsociety2.storage import ReplayWriter

   writer = ReplayWriter("experiment.db")
   await writer.initialize()

   society = AgentSociety(
       agents=agents,
       env_router=env_router,
       start_t=datetime.now(),
       replay_writer=writer,
   )
   await society.init()

   # Run simulation - all interactions are automatically recorded
   await society.run(num_steps=10, tick=3600)

   # Read back collected data
   profiles = await writer.read_agent_profiles()
   dialogs = await writer.read_agent_dialogs()
   statuses = await writer.read_agent_status()

   await society.close()

Common Interaction Scenarios
-----------------------------

Scenario 1: Event Intervention
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   # Normal simulation
   await society.run(num_steps=5, tick=3600)

   # Event occurs (e.g., hurricane)
   await society.intervene(
       "Broadcast: 'Hurricane warning! Seek shelter immediately!'"
   )

   # Continue simulation to observe reactions
   await society.run(num_steps=5, tick=3600)

   # Collect impact data
   impact = await society.ask("How did the hurricane affect everyone?")
   print(impact)

Scenario 2: Policy Experiment
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   # Control group - no policy
   control_agents = [PersonAgent(id=i, profile=...) for i in range(1, 11)]
   control_society = AgentSociety(agents=control_agents, ...)
   await control_society.init()
   await control_society.run(num_steps=10, tick=3600)

   # Treatment group - with policy intervention
   treatment_agents = [PersonAgent(id=i+10, profile=...) for i in range(10)]
   treatment_society = AgentSociety(agents=treatment_agents, ...)
   await treatment_society.init()

   # Implement policy
   await treatment_society.intervene(
       "Implement UBI policy: everyone receives $1000 monthly"
   )

   await treatment_society.run(num_steps=10, tick=3600)

   # Compare outcomes
   control_outcome = await control_society.ask("What's the average happiness?")
   treatment_outcome = await treatment_society.ask("What's the average happiness?")

Scenario 3: Data Collection at Multiple Time Points
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   # Baseline data
   baseline = await society.ask("Record everyone's baseline mood")

   # Intervention
   await society.intervene("Announce new community program")

   # Short-term effects
   await society.run(num_steps=3, tick=3600)
   short_term = await society.ask("How is everyone feeling now?")

   # Long-term effects
   await society.run(num_steps=10, tick=3600)
   long_term = await society.ask("How is everyone feeling now?")

   # Analyze change over time

Best Practices
--------------

1. **Use ask() for queries**: Always use ``ask()`` when you only need information

2. **Use intervene() for changes**: Only use ``intervene()`` when you want to modify state

3. **Combine with ReplayWriter**: Enable replay recording for comprehensive data collection

4. **Query specific agents**: Direct questions to specific agents for targeted responses

5. **Time your interventions**: Intervene at appropriate simulation times for realistic effects
