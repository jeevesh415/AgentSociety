Backend API 模块
================

本模块提供 FastAPI 后端服务。

FastAPI 应用
------------

.. autofunction:: agentsociety2.backend.app.create_app

路由模块
--------

Agent Skills 路由
~~~~~~~~~~~~~~~~~

.. automodule:: agentsociety2.backend.routers.agent_skills
   :members:
   :undoc-members:

请求/响应模型
-------------

SkillItem
~~~~~~~~~

.. autoclass:: agentsociety2.backend.routers.agent_skills.SkillItem
   :members:

ListResponse
~~~~~~~~~~~~

.. autoclass:: agentsociety2.backend.routers.agent_skills.ListResponse
   :members:
