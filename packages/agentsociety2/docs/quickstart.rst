快速入门
===========

本指南将帮助您快速上手 AgentSociety 2。

您的第一个智能体
----------------

让我们使用 **AgentSociety** 创建一个简单的智能体并与它交互：

.. code-block:: python

   import asyncio
   from datetime import datetime
   from agentsociety2 import PersonAgent
   from agentsociety2.env import CodeGenRouter
   from agentsociety2.contrib.env import SimpleSocialSpace
   from agentsociety2.society import AgentSociety

   async def main():
       # 创建具有配置文件的智能体
       agent = PersonAgent(
           id=1,
           profile={
               "name": "Alice",
               "age": 28,
               "personality": "友好且好奇",
               "bio": "一名热爱徒步的软件工程师。"
           }
       )

       # 创建包含智能体信息的环境模块
       social_env = SimpleSocialSpace(
           agent_id_name_pairs=[(agent.id, agent.name)]
       )

       # 创建环境路由器
       env_router = CodeGenRouter(env_modules=[social_env])

       # 创建社会
       society = AgentSociety(
           agents=[agent],
           env_router=env_router,
           start_t=datetime.now(),
       )

       # 初始化（为智能体设置环境）
       await society.init()

       # 查询（只读）
       response = await society.ask("你最喜欢的活动是什么？")
       print(f"智能体: {response}")

       # 关闭社会
       await society.close()

   if __name__ == "__main__":
       asyncio.run(main())

运行此代码将产生类似以下输出：

.. code-block:: text

   智能体: 我真的很喜欢徒步！在大自然中，探索新的步道，欣赏美丽的风景，有一种平静感。
   这是放松心情和保持活力的好方法。

创建自定义环境
--------------

环境模块允许智能体与特定功能进行交互：

.. code-block:: python

   from agentsociety2.env import EnvBase, tool, CodeGenRouter

   class MyEnvironment(EnvBase):
       """一个自定义环境模块。"""

       @tool(readonly=True, kind="observe")
       def get_weather(self, agent_id: int) -> str:
           """获取当前天气。"""
           return "天气晴朗，温度 25°C。"

       @tool(readonly=False)
       def set_mood(self, agent_id: int, mood: str) -> str:
           """改变智能体的情绪。"""
           return f"智能体 {agent_id} 的情绪现在是 {mood}。"

   # 在 AgentSociety 中使用自定义模块
   agent = PersonAgent(id=1, profile={"name": "Bob"})

   env_router = CodeGenRouter(env_modules=[MyEnvironment()])

   society = AgentSociety(
       agents=[agent],
       env_router=env_router,
       start_t=datetime.now(),
   )
   await society.init()

   # 智能体现在可以使用环境的工具
   response = await society.ask("天气怎么样？")
   print(response)

   await society.close()

运行实验
---------

下面是一个使用 AgentSociety 的多智能体完整实验示例：

.. code-block:: python

   import asyncio
   from datetime import datetime
   from agentsociety2 import PersonAgent
   from agentsociety2.env import CodeGenRouter
   from agentsociety2.contrib.env import SimpleSocialSpace
   from agentsociety2.storage import ReplayWriter
   from agentsociety2.society import AgentSociety

   async def main():
       # 设置回放写入器用于跟踪
       writer = ReplayWriter("my_experiment.db")
       await writer.initialize()

       # 首先创建智能体（SimpleSocialSpace 需要）
       agents = [
           PersonAgent(
               id=i,
               profile={"name": f"Player{i}", "personality": "竞争型"},
               replay_writer=writer
           )
           for i in range(1, 4)
       ]

       # 创建环境路由器
       env_router = CodeGenRouter(
           env_modules=[SimpleSocialSpace(
               agent_id_name_pairs=[(a.id, a.name) for a in agents]
           )]
       )
       env_router.set_replay_writer(writer)

       # 创建启用了回放的社会
       society = AgentSociety(
           agents=agents,
           env_router=env_router,
           start_t=datetime.now(),
           replay_writer=writer,
       )
       await society.init()

       # 运行交互
       for agent in agents:
           response = await society.ask(
               f"告诉 {agent._name} 向小组做自我介绍！"
           )
           print(f"{agent._name}: {response}")

       await society.close()

   if __name__ == "__main__":
       asyncio.run(main())

下一步
----------

既然您已经掌握了基础知识，可以继续探索：

* :doc:`agents` - 详细了解智能体
* :doc:`env_modules` - 创建自定义环境模块
* :doc:`concepts` - 理解核心概念
* :doc:`storage` - 了解回放系统
* :doc:`examples` - 查看更多示例

常见模式
---------------

只读查询
~~~~~~~~~~~~~~~~

对于不修改状态的查询，使用 ``society.ask()``：

.. code-block:: python

   # society.ask() 确保只读访问
   response = await society.ask("模拟中有哪些智能体？")

进行修改
~~~~~~~~~~~~~~

对于修改环境的操作，使用 ``society.intervene()``：

.. code-block:: python

   # society.intervene() 允许环境修改
   result = await society.intervene("让所有人的心情变好")

查询特定智能体
~~~~~~~~~~~~~~~~~~~~~~~~~

向特定智能体提问：

.. code-block:: python

   # 向特定智能体提问
   response = await society.ask(
       "Alice，你对当前情况有什么看法？"
   )
