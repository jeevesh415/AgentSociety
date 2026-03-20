Agent 模块
==========

本模块提供智能体的核心类和数据模型。

核心类
------

AgentBase
~~~~~~~~~

.. autoclass:: agentsociety2.agent.AgentBase
   :members:
   :undoc-members:
   :show-inheritance:

PersonAgent
~~~~~~~~~~~

.. autoclass:: agentsociety2.agent.PersonAgent
   :members:
   :undoc-members:
   :show-inheritance:
   :special-members: __init__

DoNothingAgent
~~~~~~~~~~~~~~

.. autoclass:: agentsociety2.agent.DoNothingAgent
   :members:
   :undoc-members:
   :show-inheritance:

数据模型
--------

情感模型
~~~~~~~~

.. autoclass:: agentsociety2.agent.models.EmotionType
   :members:

.. autoclass:: agentsociety2.agent.models.Emotion
   :members:

需求模型
~~~~~~~~

.. autoclass:: agentsociety2.agent.models.Satisfactions
   :members:

.. autoclass:: agentsociety2.agent.models.Need
   :members:

计划模型
~~~~~~~~

.. autoclass:: agentsociety2.agent.models.PlanStepStatus
   :members:

.. autoclass:: agentsociety2.agent.models.PlanStep
   :members:

.. autoclass:: agentsociety2.agent.models.Plan
   :members:

意图模型
~~~~~~~~

.. autoclass:: agentsociety2.agent.models.Intention
   :members:

Skill 选择
~~~~~~~~~~

.. autoclass:: agentsociety2.agent.models.SkillSelection
   :members:
