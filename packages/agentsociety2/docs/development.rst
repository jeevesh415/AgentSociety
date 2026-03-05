开发指南
=================

本指南面向 AgentSociety 2 的贡献者。

设置开发环境
-----------------------------------

1. Fork 并克隆仓库：

.. code-block:: bash

   git clone https://github.com/your-username/agentsociety.git
   cd agentsociety

2. 以开发模式安装：

.. code-block:: bash

   # Using uv (recommended)
   uv sync

   # Or using pip
   pip install -e "packages/agentsociety2[dev]"

3. 安装 pre-commit hooks：

.. code-block:: bash

   cd packages/agentsociety2
   pre-commit install

运行测试
-------------

.. code-block:: bash

   cd packages/agentsociety2
   pytest

使用覆盖率：

.. code-block:: bash

   pytest --cov=agentsociety2 --cov-report=html

代码风格
----------

AgentSociety 2 使用 `ruff`_ 进行检查和格式化：

.. code-block:: bash

   # Check code
   ruff check .

   # Format code
   ruff format .

我们还使用 `mypy`_ 进行类型检查：

.. code-block:: bash

   mypy agentsociety2/

.. _ruff: https://github.com/astral-sh/ruff
.. _mypy: https://github.com/python/mypy

项目结构
-----------------

.. code-block:: text

   agentsociety2/
   ├── agent/           # 智能体实现
   ├── backend/         # FastAPI 后端服务
   ├── code_executor/   # Docker 中的代码执行
   ├── config/          # 配置和 LLM 路由
   ├── contrib/         # 贡献的智能体和环境
   ├── designer/        # 实验设计器
   ├── env/             # 环境模块和路由器
   ├── logger/          # 日志工具
   ├── mcp/             # Model Context Protocol 服务器
   ├── society/         # 社会辅助工具
   ├── storage/         # 回放存储系统
   └── web_ui/          # Gradio Web 界面

贡献
------------

请参阅 :doc:`contributing` 了解贡献指南。

构建文档
----------------------

.. code-block:: bash

   cd packages/agentsociety2/docs
   make html

构建的文档将位于 ``_build/html/``。

要在编辑时进行实时预览：

.. code-block:: bash

   make livehtml

发布流程
---------------

1. 更新 ``pyproject.toml`` 中的版本
2. 更新 ``CHANGELOG.md``
3. 提交更改
4. 创建标签：``git tag agentsociety2-vX.Y.Z``
5. 推送：``git push --tags``
6. GitHub Actions 将构建并发布到 PyPI
