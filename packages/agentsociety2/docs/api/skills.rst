Agent Skills 模块
==================

本模块提供智能体技能的注册与管理，支持渐进式加载和依赖管理。

SkillRegistry
-------------

.. autoclass:: agentsociety2.agent.skills.SkillRegistry
   :members:
   :undoc-members:
   :show-inheritance:

SkillInfo
---------

.. autoclass:: agentsociety2.agent.skills.SkillInfo
   :members:
   :undoc-members:

LoadedSkill
-----------

.. autoclass:: agentsociety2.agent.skills.LoadedSkill
   :members:
   :undoc-members:

工具函数
--------

.. autofunction:: agentsociety2.agent.skills.get_skill_registry

依赖管理
--------

Skill 支持 ``requires`` 和 ``provides`` 字段声明依赖关系：

.. code-block:: yaml

   ---
   name: cognition
   description: Update emotions and form intentions
   priority: 40
   requires:
     - observation           # skill 名称
     - intention_formation   # 或能力标签
   provides:
     - intention_formation
     - emotion_update
   ---

**能力标签 vs Skill 名称**：

- **Skill 名称**：直接引用其他 skill（如 ``observation``）
- **能力标签**：抽象能力描述，由 ``provides`` 声明（如 ``intention_formation``）

使用能力标签可以实现松耦合的依赖声明。
