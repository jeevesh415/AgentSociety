存储和回放系统
=========================

ReplayWriter 系统提供智能体-环境交互的跟踪，用于实验分析。

概述
--------

AgentSociety 2 包含一个基于 SQLite 的存储系统，用于捕获：

* **智能体配置文件**: 静态特征和个性特征
* **智能体状态**: 模拟期间更新的动态状态
* **自定义表**: 特定于模块的数据

存储架构
~~~~~~~~~~~~~~~~~

.. graphviz::

   digraph storage_architecture {
       rankdir=TB;
       node [shape=box, style=rounded];

       subgraph cluster_db {
           label = "SQLite 数据库 (experiment.db)";
           style=filled;
           color=lightblue;

           Profile [label="agent_profile\n静态配置"];
           Status [label="agent_status\n动态状态"];
           Custom [label="自定义表\n模块数据"];
       }

       ReplayWriter [label="ReplayWriter"];
       Agent [label="智能体"];
       Env [label="环境模块"];

       Agent --> ReplayWriter;
       Env --> ReplayWriter;
       ReplayWriter --> Profile;
       ReplayWriter --> Status;
       ReplayWriter --> Custom;

       Profile [shape=folder, style=filled];
       Status [shape=folder, style=filled];
       Custom [shape=folder, style=filled];
   }

数据写入流程
~~~~~~~~~~~~~~~~~

.. graphviz::

   digraph write_flow {
       rankdir=LR;
       node [shape=box, style=rounded];

       Agent [label="智能体行动"];
       ReplayWriter [label="ReplayWriter.write()"];
       Validator [label="数据验证"];
       SQLite [label="SQLite 写入"];
       Disk [(磁盘存储)];

       Agent -> ReplayWriter;
       ReplayWriter -> Validator;
       Validator -> SQLite;
       SQLite -> Disk;
   }

* **智能体配置文件**: 静态特征和个性特征
* **智能体状态**: 模拟期间更新的动态状态
* **自定义表**: 特定于模块的数据

基本使用
-----------

**启用回放跟踪：**

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

**读取数据：**

.. code-block:: python

   # Read all profiles
   profiles = await writer.read_agent_profiles()
   for profile in profiles:
       print(f"Agent {profile.agent_id}: {profile.profile}")

   # Read current status
   statuses = await writer.read_agent_status()
   for status in statuses:
       print(f"Agent {status.agent_id}: {status.status}")

框架表
----------------

AgentProfile
~~~~~~~~~~~~

存储静态智能体特征：

**字段：**

* ``agent_id`` (int): 唯一的智能体标识符
* ``profile`` (dict): JSON 编码的配置文件数据（姓名、个性等）

AgentStatus
~~~~~~~~~~~

存储动态智能体状态：

**字段：**

* ``agent_id`` (int): 唯一的智能体标识符
* ``status`` (str): 当前状态（``"active"``、``"inactive"`` 等）
* ``current_activity`` (str): 当前活动的文本描述
* ``step_count`` (int): 已完成的模拟步数

自定义表
-------------

环境模块可以注册自定义表：

**注册自定义表：**

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

**写入自定义表：**

.. code-block:: python

   await writer.write(
       table_name="location_history",
       data={
           "agent_id": agent.id,
           "location": "Central Park",
           "timestamp": datetime.now().isoformat()
       }
   )

**从自定义表读取：**

.. code-block:: python

   results = await writer.read(table_name="location_history")

   recent = await writer.read(
       table_name="location_history",
       filters={"agent_id": 1}
   )

数据导出
-----------

**导出到 Pandas：**

.. code-block:: python

   import pandas as pd

   statuses = await writer.read_agent_status()
   df = pd.DataFrame([{
       "agent_id": s.agent_id,
       "status": s.status,
   } for s in statuses])

**导出到 CSV：**

.. code-block:: python

   import csv

   statuses = await writer.read_agent_status()
   with open("statuses.csv", "w") as f:
       writer = csv.DictWriter(f, fieldnames=[
           "agent_id", "status"
       ])
       writer.writeheader()
       for s in statuses:
           writer.writerow({
               "agent_id": s.agent_id,
               "status": s.status
           })
