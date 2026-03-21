Agent Skills（智能体技能）
=================================

概述
------

Agent Skills 是 PersonAgent 的能力插件系统。PersonAgent 本身是轻量编排器，
真正的认知与行为能力由独立 skill 提供（如 observation、needs、cognition、plan、memory）。

当前实现采用两条核心原则：

1. **Metadata-first**：选择阶段只读取技能元数据，不加载完整内容。
2. **Selected-only**：每步只执行 LLM 选中的技能，不存在固定 always/dynamic/finalize 层。

这意味着：技能是否执行由当前上下文决定，而不是由“预设层级”决定。


设计目标
---------

* **按需加载**：降低每步不必要的加载与执行开销。
* **可解释选择**：选择依据来自 SKILL.md 元数据，便于调试与治理。
* **热更新友好**：支持运行时扫描、导入、启用/禁用与重载。
* **依赖可控**：用 requires/provides 声明依赖，避免硬编码耦合。


Skill 目录结构
----------------

内置技能位于包内目录，自定义技能位于工作区目录：

.. code-block:: text

   agentsociety2/agent/skills/
   ├── observation/
   │   ├── SKILL.md
   │   └── scripts/
   │       └── observation.py
   ├── cognition/
   │   ├── SKILL.md
   │   └── scripts/
   │       └── cognition.py
   └── ...

   {workspace}/custom/skills/
   └── my_skill/
       ├── SKILL.md
       └── scripts/
           └── my_skill.py

入口脚本约定：

.. code-block:: python

   async def run(agent, ctx):
       ...


SKILL.md 格式
--------------

每个 skill 目录应包含 ``SKILL.md``。文件头部使用 YAML frontmatter 描述元数据：

.. code-block:: markdown

   ---
   name: cognition
   description: Update emotions and form intentions from current context
   priority: 40
   requires:
     - observation
   provides:
     - emotion_update
     - intention_formation
   ---

   # Cognition Skill
   ...

字段说明：

.. list-table::
   :widths: 24 76
   :header-rows: 1

   * - 字段
     - 说明
   * - ``name``
     - Skill 名称（唯一标识）。
   * - ``description``
     - 给选择器看的功能描述，尽量具体、可判别。
   * - ``priority``
     - 执行优先级，数值越小越先执行。
   * - ``requires``
     - 依赖项，可写 skill 名称或能力标签。
   * - ``provides``
     - 本技能提供的能力标签。


每步执行流程
--------------

PersonAgent.step() 的流程如下：

1. 构建上下文 ``ctx``。
2. 调用 ``_select_skills_for_step()``：
   - 仅提供技能元数据目录给主 LLM。
   - 返回 ``selected_skills``。
3. 依赖校验：
   - 若缺依赖，要求 LLM 修正一次。
   - 若修正后仍缺依赖，裁剪不满足依赖的技能。
4. 按 ``priority`` 排序，按需加载并执行已选技能。
5. 若未选中 ``memory`` 但有认知缓冲，缓冲继续保留。
6. 记录本 step 细节。

关键点：

* **未被选中的技能不会执行**。
* **系统不会自动补选依赖技能**（由 LLM 修正或裁剪）。
* **执行顺序由 priority 决定**。


依赖管理
----------

依赖声明支持两种形式：

* **直接依赖 skill 名称**（例如 ``observation``）
* **依赖能力标签**（例如 ``intention_formation``）

能力标签由其他技能在 ``provides`` 中声明，注册表会把能力映射为可满足依赖的技能。

推荐实践：

* 用 ``requires`` 明确最小前置条件。
* 用 ``provides`` 暴露稳定能力名，减少技能间硬绑定。
* 保持 ``description`` 可操作，避免“泛描述”。


Memory 语义
------------

认知相关技能通常先把内容写入 ``_cognition_memory`` 缓冲：

* 当 ``memory`` 技能在本步被选中执行时，缓冲会被 flush 到长期记忆。
* 当 ``memory`` 未被选中时，缓冲不会丢失，会保留到后续 step。
* 在 Agent ``close()`` 时，会执行兜底 flush，避免遗留缓冲丢失。

因此，memory 行为不再是固定“Finalize 层”，而是由选择结果驱动。


运行时管理 API
----------------

后端提供 Agent Skills 管理接口（前缀 ``/api/v1/agent-skills``）：

* ``GET /list``：列出技能（builtin + custom）
* ``POST /enable``：启用技能
* ``POST /disable``：禁用技能
* ``POST /scan``：扫描 ``{workspace}/custom/skills``
* ``POST /import``：从外部目录导入技能
* ``POST /reload``：热重载单个技能
* ``POST /remove``：删除自定义技能
* ``GET /{name}/info``：查看技能详细信息（含 SKILL.md 内容）

这些接口同时被 VS Code 扩展与手动调试流程使用。


自定义 Skill 最小示例
----------------------

目录：

.. code-block:: text

   {workspace}/custom/skills/hello_skill/
   ├── SKILL.md
   └── scripts/
       └── hello_skill.py

``SKILL.md``：

.. code-block:: markdown

   ---
   name: hello_skill
   description: Add a short greeting into step log
   priority: 80
   requires: []
   provides: [greeting]
   ---

``scripts/hello_skill.py``：

.. code-block:: python

   async def run(agent, ctx):
       ctx.setdefault("step_log", []).append("hello_skill: greeted")

导入并启用后，主 LLM 会在合适上下文中选择它执行。


最佳实践
---------

1. ``description`` 写成“触发条件 + 输出结果”，便于选择器判断。
2. ``priority`` 按数据依赖排序，而不是按功能重要性排序。
3. ``requires`` 只声明必要依赖，避免过度耦合。
4. Skill 代码尽量幂等，避免重复执行造成状态污染。
5. 对关键技能保留清晰日志，便于复盘每步选择与执行。


参考
------

* :doc:`agents` - PersonAgent 使用说明
* :doc:`api/skills` - SkillRegistry API
* :doc:`development` - 开发指南
