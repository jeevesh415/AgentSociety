Installation
============

Requirements
------------

AgentSociety 2 requires Python 3.11 or later.

Install from PyPI
-----------------

The easiest way to install AgentSociety 2 is using pip:

.. code-block:: bash

   pip install agentsociety2

This will install the core package. If you want to install with development
dependencies:

.. code-block:: bash

   pip install "agentsociety2[dev]"

For documentation dependencies:

.. code-block:: bash

   pip install "agentsociety2[docs]"

Install everything:

.. code-block:: bash

   pip install "agentsociety2[all]"

Install from Source
-------------------

To install from the latest source code:

.. code-block:: bash

   git clone https://github.com/tsinghua-fib-lab/agentsociety.git
   cd agentsociety/packages/agentsociety2
   pip install -e .

Verify Installation
-------------------

To verify your installation, run:

.. code-block:: python

   import agentsociety2
   print(agentsociety2.__version__)

You should see the version number printed.

Configuration
-------------

AgentSociety 2 requires LLM API credentials. Set the following environment
variables:

**Required Configuration**

.. code-block:: bash

   # Default LLM (required - used for most operations)
   export AGENTSOCIETY_LLM_API_KEY="your-api-key"
   export AGENTSOCIETY_LLM_API_BASE="https://api.openai.com/v1"
   export AGENTSOCIETY_LLM_MODEL="gpt-4o-mini"

**Optional Configuration**

For specialized tasks, you can configure separate LLM instances. If these are not set,
they will fall back to the default LLM configuration:

.. code-block:: bash

   # Code Generation LLM (for code-related tasks)
   # Falls back to: AGENTSOCIETY_LLM_API_KEY, AGENTSOCIETY_LLM_API_BASE
   export AGENTSOCIETY_CODER_LLM_API_KEY="your-coder-api-key"      # Optional
   export AGENTSOCIETY_CODER_LLM_API_BASE="https://api.openai.com/v1"  # Optional
   export AGENTSOCIETY_CODER_LLM_MODEL="gpt-4o"                    # Optional

   # Nano LLM (for high-frequency, low-latency operations)
   # Falls back to: AGENTSOCIETY_LLM_API_KEY, AGENTSOCIETY_LLM_API_BASE
   export AGENTSOCIETY_NANO_LLM_API_KEY="your-nano-api-key"        # Optional
   export AGENTSOCIETY_NANO_LLM_API_BASE="https://api.openai.com/v1"  # Optional
   export AGENTSOCIETY_NANO_LLM_MODEL="gpt-4o-mini"                # Optional

   # Embedding Model (for text embeddings and semantic search)
   # Falls back to: AGENTSOCIETY_LLM_API_KEY, AGENTSOCIETY_LLM_API_BASE
   export AGENTSOCIETY_EMBEDDING_API_KEY="your-embedding-api-key"  # Optional
   export AGENTSOCIETY_EMBEDDING_API_BASE="https://api.openai.com/v1"  # Optional
   export AGENTSOCIETY_EMBEDDING_MODEL="text-embedding-3-small"   # Optional
   export AGENTSOCIETY_EMBEDDING_DIMS="1536"                      # Optional

**Data Directory**

.. code-block:: bash

   # Directory for storing agent data, memories, and persistent files
   # Default: ./agentsociety_data
   export AGENTSOCIETY_HOME_DIR="/path/to/your/data"

**Using a .env File**

You can also create a ``.env`` file in your project directory:

.. code-block:: bash

   # Required
   AGENTSOCIETY_LLM_API_KEY=your-api-key
   AGENTSOCIETY_LLM_API_BASE=https://api.openai.com/v1
   AGENTSOCIETY_LLM_MODEL=gpt-4o-mini

   # Optional (examples)
   AGENTSOCIETY_CODER_LLM_MODEL=gpt-4o
   AGENTSOCIETY_NANO_LLM_MODEL=gpt-4o-mini
   AGENTSOCIETY_EMBEDDING_MODEL=text-embedding-3-small
   AGENTSOCIETY_EMBEDDING_DIMS=1536
   AGENTSOCIETY_HOME_DIR=./agentsociety_data

Supported LLM Providers
------------------------

AgentSociety 2 uses `litellm`_ which supports many LLM providers:

- OpenAI (GPT-4, GPT-3.5)
- Anthropic (Claude)
- Azure OpenAI
- Google (Gemini)
- Cohere
- And many more...

See the `litellm documentation`_ for a complete list.

.. _litellm: https://github.com/BerriAI/litellm
.. _litellm documentation: https://docs.litellm.ai/
