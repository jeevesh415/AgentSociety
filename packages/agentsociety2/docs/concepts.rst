核心概念
=============

本部分解释 AgentSociety 2 的核心概念。

架构概述
---------------------

AgentSociety 2 围绕三个主要组件构建：

* **智能体 (Agents)**: 使用 LLM 与环境交互的自主实体
* **环境模块 (Environment Modules)**: 定义模拟规则的可组合组件
* **AgentSociety**: 管理智能体和环境的协调器

.. graphviz::

   digraph agentsociety2 {
       rankdir=TB;
       node [shape=box, style=rounded];

       Agent [label="Agent"];
       CodeGenRouter [label="CodeGenRouter"];
       EnvModule [label="Env Module"];
       Tool [label="@tool()"];

       Agent -> CodeGenRouter [label="ask/intervene"];
       CodeGenRouter -> EnvModule [label="calls tools"];
       EnvModule -> Tool [label="decorated with"];
   }

智能体-环境接口
----------------------------

智能体通过两个主要方法与环境交互：

* **ask()**: 查询或观察环境状态
* **intervene()**: 修改环境状态

这个统一接口允许智能体与任何环境模块自然通信。

@tool 装饰器
-------------------

环境模块通过 ``@tool`` 装饰器公开其功能：

.. code-block:: python

   from agentsociety2.env import EnvBase, tool

   class MyEnvironment(EnvBase):
       @tool(readonly=True, kind="observe")
       def get_weather(self, agent_id: int) -> str:
           """获取智能体的当前天气。"""
           return f"智能体 {agent_id} 的天气"

       @tool(readonly=False)
       def set_temperature(self, temp: int) -> str:
           """设置温度。"""
           self._temperature = temp
           return f"温度设置为 {temp}"

**参数：**

* ``readonly`` (bool): 函数是否修改状态
  * ``True`` = 只读观察
  * ``False`` = 修改环境

* ``kind`` (str): 用于优化的函数类别
  * ``"observe"``: 单参数观察
  * ``"statistics"``: 聚合查询（无参数）
  * ``None``: 常规工具

CodeGenRouter
-------------

CodeGenRouter 通过以下方式将智能体连接到环境模块：

1. 从环境模块中提取工具签名
2. 根据智能体输入生成调用适当工具的代码
3. 在沙盒环境中安全执行代码
4. 将结果返回给智能体

这种方法允许智能体与任何环境模块组合交互，而无需更改代码。

工具类别
---------------

**观察工具** (``readonly=True``, ``kind="observe"``)

具有单个 ``agent_id`` 参数的智能体特定观察：

.. code-block:: python

   @tool(readonly=True, kind="observe")
   def get_agent_location(self, agent_id: int) -> str:
       """获取智能体的当前位置。"""
       return f"智能体 {agent_id} 在位置 X"

**统计工具** (``readonly=True``, ``kind="statistics"``)

没有参数的聚合查询（除了 ``self``）：

.. code-block:: python

   @tool(readonly=True, kind="statistics")
   def get_average_happiness(self) -> str:
       """获取所有智能体的平均幸福感。"""
       avg = sum(self.happiness.values()) / len(self.happiness)
       return f"平均幸福感: {avg}"

**常规工具**

具有任何签名的通用工具：

.. code-block:: python

   @tool(readonly=False)
   def set_happiness(self, agent_id: int, value: float) -> str:
       """设置智能体的幸福感水平。"""
       self.happiness[agent_id] = value
       return f"设置智能体 {agent_id} 的幸福感为 {value}"
