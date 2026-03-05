Storage and Replay System
=========================

The ReplayWriter system provides tracking of agent-environment interactions for experiment analysis.

Overview
--------

AgentSociety 2 includes a SQLite-based storage system that captures:

* **Agent Profiles**: Static characteristics and personality traits
* **Agent Status**: Dynamic states updated during simulation
* **Agent Dialogs**: Conversation history with LLM inputs/outputs
* **Custom Tables**: Module-specific data

Basic Usage
-----------

**Enabling Replay Tracking:**

.. code-block:: python

   from datetime import datetime
   from agentsociety2.storage import ReplayWriter
   from agentsociety2 import PersonAgent
   from agentsociety2.env import CodeGenRouter
   from agentsociety2.contrib.env import SimpleSocialSpace
   from agentsociety2.society import AgentSociety

   # Initialize replay writer
   writer = ReplayWriter("experiment.db")
   await writer.initialize()

   # Create environment router with replay
   env_router = CodeGenRouter(env_modules=[SimpleSocialSpace(...)])
   env_router.set_replay_writer(writer)

   # Create agents with replay tracking
   agents = [
       PersonAgent(id=i, profile=..., replay_writer=writer)
       for i in range(1, 11)
   ]

   # Create society with replay enabled
   society = AgentSociety(
       agents=agents,
       env_router=env_router,
       start_t=datetime.now(),
       replay_writer=writer,
   )
   await society.init()

   # Run simulation - all interactions are automatically recorded
   await society.run(num_steps=100, tick=3600)
   await society.close()

**Reading Data:**

.. code-block:: python

   # Read all profiles
   profiles = await writer.read_agent_profiles()
   for profile in profiles:
       print(f"Agent {profile.agent_id}: {profile.profile}")

   # Read recent dialogs
   dialogs = await writer.read_agent_dialogs(limit=100)
   for dialog in dialogs:
       print(f"{dialog.agent_id}: {dialog.question[:50]}...")

   # Read current status
   statuses = await writer.read_agent_status()
   for status in statuses:
       print(f"Agent {status.agent_id}: {status.status}")

Framework Tables
----------------

AgentProfile
~~~~~~~~~~~~

Stores static agent characteristics:

**Fields:**

* ``agent_id`` (int): Unique agent identifier
* ``profile`` (dict): JSON-encoded profile data (name, personality, etc.)

AgentStatus
~~~~~~~~~~~

Stores dynamic agent states:

**Fields:**

* ``agent_id`` (int): Unique agent identifier
* ``status`` (str): Current status (``"active"``, ``"inactive"``, etc.)
* ``current_activity`` (str): Text description of current activity
* ``step_count`` (int): Number of simulation steps completed

AgentDialog
~~~~~~~~~~~

Stores conversation history:

**Fields:**

* ``agent_id`` (int): Agent who generated this dialog
* ``question`` (str): The input/question to the agent or LLM
* ``answer`` (str): The response
* ``dialog_type`` (int): Type of dialog
  * ``0``: Reflection (agent's internal reasoning)
  * ``1``: Intervention (environment modification)
* ``step`` (int): Simulation step when this occurred
* ``timestamp`` (str): ISO format timestamp

Custom Tables
-------------

Environment modules can register custom tables:

**Register a Custom Table:**

.. code-block:: python

   from agentsociety2.storage import ColumnDef, TableSchema

   schema = TableSchema(
       name="location_history",
       columns=[
           ColumnDef(name="id", dtype="INTEGER", primary_key=True),
           ColumnDef(name="agent_id", dtype="INTEGER"),
           ColumnDef(name="location", dtype="TEXT"),
           ColumnDef(name="timestamp", dtype="TEXT"),
       ]
   )

   await writer.register_table(schema)

**Write to Custom Table:**

.. code-block:: python

   await writer.write(
       table_name="location_history",
       data={
           "agent_id": agent.id,
           "location": "Central Park",
           "timestamp": datetime.now().isoformat()
       }
   )

**Read from Custom Table:**

.. code-block:: python

   results = await writer.read(table_name="location_history")

   recent = await writer.read(
       table_name="location_history",
       filters={"agent_id": 1}
   )

Data Export
-----------

**Export to Pandas:**

.. code-block:: python

   import pandas as pd

   dialogs = await writer.read_agent_dialogs()
   df = pd.DataFrame([{
       "agent_id": d.agent_id,
       "question": d.question,
       "answer": d.answer,
       "timestamp": d.timestamp
   } for d in dialogs])

**Export to CSV:**

.. code-block:: python

   import csv

   dialogs = await writer.read_agent_dialogs()
   with open("dialogs.csv", "w") as f:
       writer = csv.DictWriter(f, fieldnames=[
           "agent_id", "question", "answer", "timestamp"
       ])
       writer.writeheader()
       for d in dialogs:
           writer.writerow({
               "agent_id": d.agent_id,
               "question": d.question,
               "answer": d.answer,
               "timestamp": d.timestamp
           })
