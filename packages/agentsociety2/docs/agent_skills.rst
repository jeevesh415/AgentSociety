Agent Skills（智能体技能）
==========================

Agent Skills 是 PersonAgent 的认知能力模块，采用 **渐进式加载** 设计。

概述
--------

每个 Agent Skill 提供 Agent 的一项认知能力：

* **observation** — 环境感知（每步必执行）
* **needs** — 需求系统（饥饿、精力、安全、社交）
* **cognition** — 情感、思考与意图形成
* **plan** — 规划与 ReAct 执行
* **memory** — 记忆管理（收尾阶段）

设计哲学
------------

PersonAgent 遵循 **"原始人 + 技能"** 的设计：

* Agent 本身是一个"裸人" — 只提供编排能力和共享状态容器
* 所有认知能力通过 Skill 提供 — 感知、记忆、需求、思考、规划
* LLM 自主选择 — Agent 的 LLM 阅读 skill 描述，自主判断每步需要激活哪些能力
* 渐进式披露 — 按需加载，技能越少 Agent 越快

三层 Pipeline
-----------------

每个 simulation tick，``PersonAgent.step()`` 执行三层 pipeline：

Layer 1: Always-on（基础感知）
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

每步必执行，提供 Agent 的"五感"。

.. code-block:: text

   observation (priority=0) → 向环境发送 <observe>，获取当前环境描述

如果环境返回 ``status: in_progress``，pipeline 短路退出。

Layer 2: Dynamic（核心认知）
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

LLM 选中的 skill 按 priority 排序执行。

.. code-block:: text

   needs (priority=30)     → 调整需求满意度
   cognition (priority=40) → 更新情感/思考/意图
   plan (priority=50)      → 意图 → 计划 → ReAct 执行

**Skill Selector**：Layer 1 完成后，LLM 阅读所有可用 dynamic skill 的描述，结合当前 observation 和状态，自主判断这一步需要激活哪些能力。

Layer 3: Finalize（收尾）
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

所有 dynamic skill 完成后执行。

.. code-block:: text

   memory (priority=90) → 将 cognition_memory 批量 flush 到长期记忆

Skill 目录结构
----------------------

每个 skill 是一个独立的目录：

.. code-block:: text

   skills/
   ├── observation/
   │   ├── SKILL.md             # 元数据 + 行为规范
   │   └── scripts/
   │       └── observation.py   # async def run(agent, ctx)
   ├── cognition/
   │   ├── SKILL.md
   │   └── scripts/
   │       └── cognition.py
   └── ...

SKILL.md 格式
------------------

SKILL.md 包含 YAML frontmatter 和 Markdown 内容：

.. code-block:: yaml

   ---
   name: cognition
   description: Update emotions, generate thoughts, and form intentions (TPB).
   priority: 40
   auto_load: dynamic
   ---

   # Cognition

   Handles the agent's inner mental life...

| 字段 | 含义 |
|------|------|
| ``name`` | Skill 唯一标识 |
| ``description`` | 简短描述 — **给 LLM 看的，用于 skill selection** |
| ``priority`` | 执行优先级（数字越小越先执行） |
| ``auto_load`` | 加载策略：always / dynamic / finalize / manual |

入口脚本约定
---------------------

.. code-block:: python

   async def run(agent: Any, ctx: dict[str, Any]) -> None:
       """
       agent — PersonAgent 实例，可读写其共享状态
       ctx   — 当前 step 的上下文字典，包含：
         step_log:      list[str]  — 日志条目
         tick:          int        — 当前 tick
         t:             datetime   — 当前模拟时间
         stop:          bool       — 设为 True 则终止 pipeline
         cognition_ran: bool       — cognition skill 是否已运行
       """
       ...

Skill 来源
-------------

.. list-table::
   :widths: 20 40 20
   :header-rows: 1

   * - 来源
     - 说明
     - 可移除
   * - ``builtin``
     - 随包分发的内置 skill（``agent/skills/``）
     - ❌
   * - ``custom``
     - 用户在 ``workspace/custom/skills/`` 创建或导入
     - ✅
   * - ``env:ClassName``
     - 环境模块附带的 skill
     - ❌

渐进式加载
------------------

Agent Skills 采用两阶段加载：

**阶段 1 — 扫描**：只解析 SKILL.md 的 YAML frontmatter 元数据，不读取完整文件内容。

**阶段 2 — 启用**：当 skill 被选中或请求详情时，才加载完整的 skill_md 和 Python 模块。

这种设计优化了内存使用，特别是当存在大量 skill 时。

自定义 Skill 开发
-------------------------

用户可以在 ``workspace/custom/skills/`` 下创建自定义 skill：

.. code-block:: text

   custom/skills/
   └── my-skill/
       ├── SKILL.md
       └── scripts/
           └── my-skill.py

SKILL.md 示例：

.. code-block:: yaml

   ---
   name: market-analyst
   description: 分析市场价格趋势。当观测到市场、交易、价格等信息时应激活。
   priority: 60
   auto_load: dynamic
   ---

   # Market Analyst

   分析环境中的市场信息，为 agent 提供投资决策支持。

**关键点**：``description`` 字段要写清楚 skill 的功能和适用场景，因为 Skill Selector 的 LLM 完全依据这段描述来判断是否激活该 skill。

API 管理
-------------

通过 FastAPI 提供 RESTful 管理接口（``/api/v1/agent-skills/``）：

.. list-table::
   :widths: 30 15 40
   :header-rows: 1

   * - 端点
     - 方法
     - 功能
   * - ``/list``
     - GET
     - 列出所有 skill
   * - ``/enable``
     - POST
     - 启用 skill
   * - ``/disable``
     - POST
     - 禁用 skill
   * - ``/scan``
     - POST
     - 重新扫描 custom skill
   * - ``/import``
     - POST
     - 从外部路径导入 skill
   * - ``/{name}/info``
     - GET
     - 获取 skill 详情
   * - ``/reload``
     - POST
     - 热重载 skill
   * - ``/remove``
     - POST
     - 移除自定义 skill

参考
-------

* :doc:`agents` — 智能体使用指南
* :doc:`custom_modules` — 自定义模块开发
* Agent Architecture 文档（``agentsociety2/agent/ARCHITECTURE.md``）
