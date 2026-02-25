Examples
========

This section contains example code demonstrating AgentSociety 2's capabilities.

Running Examples
----------------

All examples are located in the ``packages/agentsociety2/examples/`` directory.

**Prerequisites:**

1. Install AgentSociety 2: ``pip install agentsociety2``
2. Configure LLM API credentials (see :doc:`installation`)
3. Navigate to the examples directory

.. code-block:: bash

   cd packages/agentsociety2/examples
   python basics/01_hello_agent.py

Basic Examples
--------------

These examples demonstrate fundamental AgentSociety 2 concepts:

**Hello Agent** (``basics/01_hello_agent.py``)

A minimal example showing:

* Creating a single agent with a personality profile
* Setting up the SimpleSocialSpace environment
* Using AgentSociety to coordinate agent-environment interaction

.. code-block:: python

   # Create agent with profile
   agent = PersonAgent(
       id=1,
       profile={
           "name": "Alice",
           "age": 28,
           "personality": "friendly, curious, optimistic",
           "bio": "A software engineer who loves hiking and reading."
       }
   )

   # Create environment and society
   society = AgentSociety(agents=[agent], env_router=..., start_t=datetime.now())
   await society.init()

   # Interact
   response = await society.ask("What's your favorite activity?")
   print(f"Agent: {response}")

**Custom Environment Module** (``basics/02_custom_env_module.py``)

Demonstrates creating custom environment modules:

* Defining a custom environment with @tool decorators
* Implementing observe(), step(), and tool methods
* Registering the module with CodeGenRouter

**Replay System** (``basics/03_replay_system.py``)

Shows comprehensive data tracking:

* Setting up ReplayWriter for automatic data capture
* Recording agent profiles, dialogs, and status
* Reading back recorded data for analysis

Game Theory Examples
---------------------

**Prisoner's Dilemma** (``games/01_prisoners_dilemma.py``)

A classic game theory scenario:

* Two agents with different personalities
* Sequential decision-making with payoffs
* Reflection on outcomes

**Public Goods Game** (``games/02_public_goods.py``)

Multi-round collective action experiment:

* Four agents with different personality traits
* Contribution decisions over multiple rounds
* Group outcome calculation

Advanced Examples
-----------------

**Custom Agent** (``advanced/01_custom_agent.py``)

Extending AgentSociety 2 with custom agent types:

* Implementing required abstract methods (ask, step, dump, load)
* Creating specialized agents for research needs

**Multi-Router Comparison** (``advanced/02_multi_router.py``)

Compares different reasoning strategies:

* ReActRouter: Iterative reasoning and acting
* PlanExecuteRouter: Plan-first execution
* CodeGenRouter: Generative code execution (recommended)
