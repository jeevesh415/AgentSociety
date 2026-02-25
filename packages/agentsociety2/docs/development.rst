Development Guide
=================

This guide is for contributors to AgentSociety 2.

Setting Up Development Environment
-----------------------------------

1. Fork and clone the repository:

.. code-block:: bash

   git clone https://github.com/your-username/agentsociety.git
   cd agentsociety

2. Install in development mode:

.. code-block:: bash

   # Using uv (recommended)
   uv sync

   # Or using pip
   pip install -e "packages/agentsociety2[dev]"

3. Install pre-commit hooks:

.. code-block:: bash

   cd packages/agentsociety2
   pre-commit install

Running Tests
-------------

.. code-block:: bash

   cd packages/agentsociety2
   pytest

With coverage:

.. code-block:: bash

   pytest --cov=agentsociety2 --cov-report=html

Code Style
----------

AgentSociety 2 uses `ruff`_ for linting and formatting:

.. code-block:: bash

   # Check code
   ruff check .

   # Format code
   ruff format .

We also use `mypy`_ for type checking:

.. code-block:: bash

   mypy agentsociety2/

.. _ruff: https://github.com/astral-sh/ruff
.. _mypy: https://github.com/python/mypy

Project Structure
-----------------

.. code-block:: text

   agentsociety2/
   ├── agent/           # Agent implementations
   ├── backend/         # FastAPI backend service
   ├── code_executor/   # Code execution in Docker
   ├── config/          # Configuration and LLM routing
   ├── contrib/         # Contributed agents and environments
   ├── designer/        # Experiment designer
   ├── env/             # Environment modules and routers
   ├── logger/          # Logging utilities
   ├── mcp/             # Model Context Protocol server
   ├── society/         # Society helper utilities
   ├── storage/         # Replay storage system
   └── web_ui/          # Gradio web interface

Contributing
------------

See :doc:`contributing` for contribution guidelines.

Building Documentation
----------------------

.. code-block:: bash

   cd packages/agentsociety2/docs
   make html

The built documentation will be in ``_build/html/``.

For live preview while editing:

.. code-block:: bash

   make livehtml

Release Process
---------------

1. Update version in ``pyproject.toml``
2. Update ``CHANGELOG.md``
3. Commit changes
4. Create a tag: ``git tag agentsociety2-vX.Y.Z``
5. Push: ``git push --tags``
6. GitHub Actions will build and publish to PyPI
