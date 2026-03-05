安装
============

系统要求
------------

AgentSociety 2 需要 Python 3.11 或更高版本。

从 PyPI 安装
-----------------

最简单的安装 AgentSociety 2 的方法是使用 pip：

.. code-block:: bash

   pip install agentsociety2

这将安装核心包。如果要安装开发依赖：

.. code-block:: bash

   pip install "agentsociety2[dev]"

对于文档依赖：

.. code-block:: bash

   pip install "agentsociety2[docs]"

安装所有内容：

.. code-block:: bash

   pip install "agentsociety2[all]"

从源码安装
-------------------

要从最新的源代码安装：

.. code-block:: bash

   git clone https://github.com/tsinghua-fib-lab/agentsociety.git
   cd agentsociety/packages/agentsociety2
   pip install -e .

验证安装
-------------------

要验证您的安装，运行：

.. code-block:: python

   import agentsociety2
   print(agentsociety2.__version__)

您应该能看到版本号被打印出来。

配置
-------------

AgentSociety 2 需要 LLM API 凭证。设置以下环境变量：

**必需配置**

.. code-block:: bash

   # 默认 LLM（必需 - 用于大多数操作）
   export AGENTSOCIETY_LLM_API_KEY="your-api-key"
   export AGENTSOCIETY_LLM_API_BASE="https://api.openai.com/v1"
   export AGENTSOCIETY_LLM_MODEL="gpt-4o-mini"

**可选配置**

对于专门的任务，您可以配置单独的 LLM 实例。如果未设置这些选项，
它们将回退到默认 LLM 配置：

.. code-block:: bash

   # 代码生成 LLM（用于代码相关任务）
   # 回退到: AGENTSOCIETY_LLM_API_KEY, AGENTSOCIETY_LLM_API_BASE
   export AGENTSOCIETY_CODER_LLM_API_KEY="your-coder-api-key"      # 可选
   export AGENTSOCIETY_CODER_LLM_API_BASE="https://api.openai.com/v1"  # 可选
   export AGENTSOCIETY_CODER_LLM_MODEL="gpt-4o"                    # 可选

   # Nano LLM（用于高频、低延迟操作）
   # 回退到: AGENTSOCIETY_LLM_API_KEY, AGENTSOCIETY_LLM_API_BASE
   export AGENTSOCIETY_NANO_LLM_API_KEY="your-nano-api-key"        # 可选
   export AGENTSOCIETY_NANO_LLM_API_BASE="https://api.openai.com/v1"  # 可选
   export AGENTSOCIETY_NANO_LLM_MODEL="gpt-4o-mini"                # 可选

   # 嵌入模型（用于文本嵌入和语义搜索）
   # 回退到: AGENTSOCIETY_LLM_API_KEY, AGENTSOCIETY_LLM_API_BASE
   export AGENTSOCIETY_EMBEDDING_API_KEY="your-embedding-api-key"  # 可选
   export AGENTSOCIETY_EMBEDDING_API_BASE="https://api.openai.com/v1"  # 可选
   export AGENTSOCIETY_EMBEDDING_MODEL="text-embedding-3-small"   # 可选
   export AGENTSOCIETY_EMBEDDING_DIMS="1536"                      # 可选

**数据目录**

.. code-block:: bash

   # 用于存储智能体数据、记忆和持久文件的目录
   # 默认值: ./agentsociety_data
   export AGENTSOCIETY_HOME_DIR="/path/to/your/data"

**使用 .env 文件**

您也可以在项目目录中创建 ``.env`` 文件：

.. code-block:: bash

   # 必需
   AGENTSOCIETY_LLM_API_KEY=your-api-key
   AGENTSOCIETY_LLM_API_BASE=https://api.openai.com/v1
   AGENTSOCIETY_LLM_MODEL=gpt-4o-mini

   # 可选（示例）
   AGENTSOCIETY_CODER_LLM_MODEL=gpt-4o
   AGENTSOCIETY_NANO_LLM_MODEL=gpt-4o-mini
   AGENTSOCIETY_EMBEDDING_MODEL=text-embedding-3-small
   AGENTSOCIETY_EMBEDDING_DIMS=1536
   AGENTSOCIETY_HOME_DIR=./agentsociety_data

支持的 LLM 提供商
------------------------

AgentSociety 2 使用 `litellm`_，支持许多 LLM 提供商：

- OpenAI (GPT-4, GPT-3.5)
- Anthropic (Claude)
- Azure OpenAI
- Google (Gemini)
- Cohere
- 以及更多...

查看 `litellm 文档`_ 获取完整列表。

.. _litellm: https://github.com/BerriAI/litellm
.. _litellm 文档: https://docs.litellm.ai/
