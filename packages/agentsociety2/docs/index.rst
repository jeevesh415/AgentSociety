AgentSociety
=============

**AgentSociety 2** is a modern, LLM-native agent simulation platform designed
for social science research and experimentation. It provides a flexible framework
for creating and managing intelligent agents in simulated environments.

.. image:: https://img.shields.io/pypi/v/agentsociety2.svg
   :target: https://pypi.org/project/agentsociety2/
   :alt: PyPI Version

.. image:: https://img.shields.io/pypi/pyversions/agentsociety2.svg
   :target: https://pypi.org/project/agentsociety2/
   :alt: Python Versions

.. image:: https://img.shields.io/badge/License-Apache%202.0-blue.svg
   :target: LICENSE
   :alt: License

Key Features
------------

* **LLM-Driven Agents**: Create agents with personality, memory, and reasoning
  capabilities powered by large language models.

* **Flexible Environment Modules**: Build custom simulation environments with
  composable tools and state management.

* **Async-First Design**: High-performance async architecture for efficient
  multi-agent simulations.

* **Replay & Analysis**: Built-in SQLite-based storage for experiment tracking
  and analysis.

* **Extensible**: Easy to extend with custom agents, environments, and tools.

Installation
------------

.. code-block:: bash

   pip install agentsociety2

See :doc:`installation` for detailed setup instructions.

Quick Start
-----------

.. code-block:: python

   from agentsociety2 import PersonAgent, AgentSociety

   # Create an agent
   agent = PersonAgent(
       id=1,
       profile={
           "name": "Alice",
           "age": 28,
           "personality": "friendly and curious",
           "bio": "A software engineer who loves hiking."
       }
   )

   # Ask the agent a question
   response = await agent.ask("What's your favorite hobby?")
   print(response)

See :doc:`quickstart` for more examples.

Documentation
-------------

.. toctree::
   :maxdepth: 2
   :caption: Getting Started:

   installation
   quickstart
   concepts
   interaction

.. toctree::
   :maxdepth: 2
   :caption: User Guide:

   agents
   env_modules
   storage
   custom_modules

.. toctree::
   :maxdepth: 2
   :caption: Developer Guide:

   development
   contributing

.. toctree::
   :maxdepth: 2
   :caption: Reference:

   examples

Links
-----

* **GitHub**: https://github.com/tsinghua-fib-lab/AgentSociety
* **PyPI**: https://pypi.org/project/agentsociety2/
* **Issues**: https://github.com/tsinghua-fib-lab/AgentSociety/issues

Search
------

* :ref:`search`
