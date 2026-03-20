# PersonAgent 架构设计文档

> 本文档面向团队成员和评审人员，系统阐述 AgentSociety 2 中 PersonAgent 的技能驱动（Skills-based）架构设计。

---

## 1. 设计理念

PersonAgent 遵循 **"原始人 + 技能"** 的设计哲学：

- **Agent 本身是一个"裸人"** — 只提供最基础的编排能力和共享状态容器
- **所有认知能力通过 Skill 提供** — 感知、记忆、需求、思考、规划，每一项都是独立的 Skill 模块
- **LLM 自主选择** — Agent 的 LLM 阅读 skill 描述（SKILL.md metadata），自主判断每步需要激活哪些能力，而非硬编码匹配
- **渐进式披露（Progressive Disclosure）** — 按需加载，技能越少 Agent 越快

这种设计的核心优势：

| 维度 | 传统 monolithic agent | Skills-based agent |
|------|----------------------|-------------------|
| 扩展性 | 修改主类、引入耦合 | 添加一个 skill 目录即可 |
| 性能控制 | 全量执行所有逻辑 | LLM 自主选择，未选中的 skill 不执行 |
| 自定义能力 | 需要继承/重写 | 用户在 workspace 中创建自己的 skill |
| 运行时灵活性 | 重启才能生效 | 热插拔：运行时添加/移除 skill |

---

## 2. 整体架构

```
┌─────────────────────────────────────────────────────────┐
│                     PersonAgent                         │
│                   (轻量编排器)                            │
│                                                         │
│  共享状态:                                                │
│    _observation, _memory, _satisfactions,                │
│    _emotion, _thought, _intention, _plan ...             │
│                                                         │
│  ┌─────────────────────────────────────────────────┐    │
│  │              Skills Pipeline                     │    │
│  │                                                  │    │
│  │  Layer 1 ─── always-on ──→  observation          │    │
│  │      │                                           │    │
│  │      ▼                                           │    │
│  │  Skill Selector (1 LLM call)                     │    │
│  │  ┌─ 读取 skill descriptions ─────────────────┐   │    │
│  │  │  + observation + agent state              │   │    │
│  │  │  → LLM 自主决定激活哪些 dynamic skills     │   │    │
│  │  └──────────────────────────────────────────┘   │    │
│  │      │                                           │    │
│  │      ▼                                           │    │
│  │  Layer 2 ─── dynamic ───→  needs (if selected)   │    │
│  │                             cognition (if sel.)  │    │
│  │                             plan (if selected)   │    │
│  │      │                                           │    │
│  │      ▼                                           │    │
│  │  Layer 3 ─── finalize ──→  memory (flush)        │    │
│  └─────────────────────────────────────────────────┘    │
│                                                         │
│  ┌────────────┐  ┌────────────┐  ┌────────────────┐    │
│  │ SkillRegistry│ │ short-term │  │ long-term mem  │    │
│  │ (发现/加载)   │ │ memory     │  │ (mem0)         │    │
│  └────────────┘  └────────────┘  └────────────────┘    │
└──────────────┬──────────────────────────────────────────┘
               │ ask_env / intervene
               ▼
        Environment Router
```

---

## 3. 三层 Pipeline 执行流程

每个 simulation tick，`PersonAgent.step()` 执行以下三层 pipeline：

### Layer 1: Always-on（基础感知）

> 每步必执行，提供 Agent 的"五感"。

| Skill | Priority | LLM 调用 | 作用 |
|-------|----------|---------|------|
| **observation** | 0 | 0 次 | 向环境发送 `<observe>`，获取当前环境描述，存入记忆 |

如果环境返回 `status: in_progress`（世界尚未稳定），pipeline 短路退出，跳过后续所有层。

### Skill Selector（LLM 自主选择）

Layer 1 完成后，Agent 的 LLM 阅读所有可用 dynamic skill 的描述（来自 SKILL.md frontmatter），结合当前 observation 和状态，**自主判断**这一步需要激活哪些能力。

**输入给 LLM 的信息**：
- 当前观测（observation）
- 当前状态摘要（需求、情绪、意图、计划）
- 所有可用 dynamic skill 的名称 + 描述

**LLM 返回**：
- `selected_skills` — 需要激活的 skill 名称列表
- `reasoning` — 选择理由

> 这是 Claude-style 的 skill 机制：SKILL.md 的 metadata 和描述是写给 LLM 看的，由 LLM 根据上下文自主决定使用哪些能力，而非硬编码规则匹配。

**容错**：如果 LLM 调用失败，fallback 到激活所有 dynamic skill。

### Layer 2: Dynamic（核心认知）

> LLM 选中的 skill 按 priority 排序执行。

| Skill | Priority | LLM 调用 | 作用 |
|-------|----------|---------|------|
| **needs** | 30 | 0-2 次 | 调整四维需求满意度，确定最紧迫需求 |
| **cognition** | 40 | 1 次 | 情感/思考/意图一次性更新（合并 LLM 调用） |
| **plan** | 50 | 2-6+ 次 | 意图 → 多步计划 → ReAct 执行 |

**优化设计**：cognition 运行时会设置 `ctx["cognition_ran"] = True`，needs 检测到这个标记后直接跳过（因为 cognition 的合并调用已包含需求调整），避免重复 LLM 调用。

### Layer 3: Finalize（收尾）

> 所有 dynamic skill 完成后执行的收尾操作，不受 skill selector 控制。

| Skill | Priority | LLM 调用 | 作用 |
|-------|----------|---------|------|
| **memory** | 90 | 0-1 次 | 将 cognition_memory 批量 flush 到长期记忆 |

memory 必须在 finalize 阶段执行，因为它需要 flush 的 `_cognition_memory` 是在 Layer 2 的 cognition skill 中产生的。

### 执行时序图

```
tick N
  │
  ├─ step() 开始
  │    ├─ 清空 _cognition_memory
  │    │
  │    ├─ [Layer 1] observation.run()
  │    │    └─ ask_env("<observe>") → 存入记忆
  │    │
  │    ├─ [Skill Selector] 1 次 LLM 调用
  │    │    ├─ 输入: observation + state + skill 描述
  │    │    └─ 输出: 选中 [cognition, plan]（举例）
  │    │
  │    ├─ [Layer 2] cognition.run()     ← 被选中
  │    │    └─ 1 次 LLM → 更新情感/思考/意图
  │    │    └─ 写入 cognition_memory
  │    │
  │    ├─ [Layer 2] plan.run()          ← 被选中
  │    │    └─ 意图 → 计划 → ReAct 执行
  │    │    └─ 与环境多次交互
  │    │
  │    ├─ [Layer 2] needs.run()         ← 未选中，跳过
  │    │
  │    ├─ [Layer 3] memory.run()        ← finalize，始终执行
  │    │    └─ flush cognition_memory → 长期记忆
  │    │
  │    └─ 记录 step details
  │
  └─ 返回 step summary
```

---

## 4. 内置 Skill 详解

### 4.1 Observation（感知）

```
auto_load: always | priority: 0 | LLM: 0 次
```

Agent 的"感官"。每步向环境路由器发送 `<observe>` 指令，获取结构化的环境描述（位置、周围 agent、物品、时间、天气等），存入短期和长期记忆。

**关键行为**：
- 如果环境返回 `in_progress`，当前 step 直接短路
- 观测文本会成为后续所有 skill 的输入基础

### 4.2 Needs（需求系统）

```
auto_load: dynamic | priority: 30 | LLM: 0-2 次
```

建模四种基本需求，满意度在 0.0–1.0 范围内浮动：

| 需求 | 含义 | 默认阈值 |
|------|------|---------|
| Satiety（饱食） | 饥饿/食物满足感 | T_H = 0.2 |
| Energy（精力） | 休息/睡眠满足感 | T_D = 0.2 |
| Safety（安全） | 身心安全感 | T_P = 0.2 |
| Social（社交） | 社交联系/归属感 | T_C = 0.3 |

**执行逻辑**：
1. 如果 cognition skill 已运行（`ctx["cognition_ran"]`），直接跳过
2. 否则，通过 LLM 根据近期记忆和环境调整各项满意度
3. 选择满意度最低（相对阈值）的需求作为 `current_need`

### 4.3 Cognition（认知）

```
auto_load: dynamic | priority: 40 | LLM: 1 次
```

Agent 的"内心世界"，一次合并 LLM 调用完成三件事：

1. **情感更新** — 6 维情感向量（sadness, joy, fear, disgust, anger, surprise），0–10 标度，外加 21 种离散情感类型（OCC 模型）
2. **思考生成** — 一句自然语言的内心独白
3. **意图形成** — 基于 TPB（计划行为理论），生成候选意图列表，按态度/社会规范/感知控制力评分，选出最高优先级意图

**关键输出**：
- `ctx["cognition_ran"] = True` — 通知 needs skill 跳过
- `agent._intention` — 驱动下游 plan skill
- 多条 cognition_memory — 等待 finalize 阶段 flush

### 4.4 Plan（规划与执行）

```
auto_load: dynamic | priority: 50 | LLM: 2-6+ 次
```

将意图转化为可执行的多步计划，通过 ReAct 循环与环境交互：

**计划生命周期**：
```
无意图 → 跳过
有意图 + 无计划 → LLM 生成计划
有计划 + 进行中 → 检查当前步骤完成情况
意图变化 → 判断是否中断旧计划
计划完成/失败 → 触发情感更新
```

**ReAct 执行循环**（每个计划步骤）：
```
Reasoning → 决定下一步行动
  ↓
Acting → 向环境发送指令（ask_env）
  ↓
Observing → 读取环境响应
  ↓
重复（最多 max_react_interactions_per_step 次）
```

**Template 模式**：开启 `template_mode_enabled` 后，指令使用 `{variable_name}` 占位符 + `variables` 字典，支持结构化环境 API。

### 4.5 Memory（记忆 — Finalize）

```
auto_load: finalize | priority: 90 | LLM: 0-1 次
```

Pipeline 收尾阶段，执行两项操作：

1. **Flush cognition_memory** — 将 cognition skill 产生的内部状态（需求变化、情感更新、思考内容）按 type 分组，批量写入长期记忆（纯内存操作，0 LLM）
2. **Intention 查询**（可选）— 每隔 2 步，如果 cognition 已运行，执行 1 次 LLM 查询当前意图

---

## 5. Skill 目录结构与 SKILL.md 格式

### 目录约定

```
skills/
├── observation/
│   ├── SKILL.md             # 元数据 + 行为规范
│   └── scripts/
│       └── observation.py   # async def run(agent, ctx)
├── memory/
│   ├── SKILL.md
│   └── scripts/
│       └── memory.py
└── ...
```

> **注意**：不再使用 `_order.txt` 文件。执行顺序由各 SKILL.md 中的 `priority` 字段决定。

### SKILL.md YAML Frontmatter

```yaml
---
name: cognition
description: Emotion, thought, and intention formation via TPB.
priority: 40
auto_load: dynamic          # always | dynamic | finalize | manual
requires:                    # 依赖的其他 skill 或能力标签
  - observation
provides:                    # 提供的能力标签
  - emotion_update
  - intention_formation
---
```

| 字段 | 含义 |
|------|------|
| `name` | Skill 唯一标识 |
| `description` | 简短描述 — **给 LLM 看的，用于 skill selection** |
| `priority` | 执行优先级（数字越小越先执行） |
| `auto_load` | 加载策略：always / dynamic / finalize / manual |
| `requires` | 依赖的其他 skill 名称或能力标签列表 |
| `provides` | 此 skill 提供的能力标签列表 |

> `description` 是 Skill Selector 的核心输入：LLM 通过阅读每个 skill 的 description 来判断当前步骤是否需要激活该能力。因此 description 应当简洁且准确地传达 skill 的功能和适用场景。

### 依赖声明

`requires` 字段支持两种形式：
1. **Skill 名称** — 直接依赖另一个 skill，如 `observation`
2. **能力标签** — 依赖某个能力，系统会自动查找提供该能力的 skill

```yaml
# plan skill 的依赖声明示例
requires:
  - observation              # skill 名称
  - intention_formation      # 能力标签（由 cognition 提供）
```

`provides` 字段声明此 skill 提供的能力标签，用于：
1. 能力发现 — 其他 skill 可以通过能力标签依赖
2. 文档化 — 明确 skill 的功能边界

### 入口脚本约定

```python
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
```

---

## 6. SkillRegistry 与运行时管理

`SkillRegistry` 是全局单例，负责 skill 的发现、加载、启用/禁用和热重载。

### 核心方法

| 方法 | 功能 |
|------|------|
| `scan_builtin()` | 扫描内置 skill 目录，只读取元数据 |
| `scan_custom(workspace_path)` | 扫描用户自定义 skill |
| `enable(name)` / `disable(name)` | 启用/禁用 skill |
| `load_filtered(names)` | 加载指定名称的 skill（完整加载） |
| `load_single(name)` | 按需加载单个 skill（渐进式加载） |
| `reload_skill(name)` | 热重载单个 skill |

### 渐进式加载流程

```
PersonAgent.__init__():
  │
  ├─→ scan_builtin()  → 只读取 SKILL.md frontmatter 元数据
  │                     skill_md = "" (延迟加载)
  │
  ├─→ 预加载 always + finalize skill
  │   (这些 skill 必须每步执行，所以预加载)
  │
  └─→ 记录 available_dynamic_names (元数据级别，不加载 Python)

PersonAgent.step():
  │
  ├─→ Layer 1: 执行 always skill (已预加载)
  │
  ├─→ _select_skills_for_step()  → LLM 选择
  │     └─→ 使用元数据构建 prompt，不加载 Python
  │
  ├─→ Layer 2: 按需加载并执行选中的 dynamic skill
  │     └─→ _get_or_load_skill() → 这时才加载 Python 模块
  │
  └─→ Layer 3: 执行 finalize skill (已预加载)
```

### Skill 来源

```
1. builtin  — 随包分发（agent/skills/ 下）
2. custom   — 用户在 workspace/custom/skills/ 下创建
```

Custom skill 优先级默认从 100 开始，可通过 SKILL.md frontmatter 自定义。

### API 端点

通过 FastAPI 提供 RESTful 管理接口（`/api/v1/agent-skills/`）：

| 端点 | 方法 | 功能 |
|------|------|------|
| `/list` | GET | 列出所有 skill |
| `/enable` | POST | 启用 skill |
| `/disable` | POST | 禁用 skill |
| `/scan` | POST | 重新扫描 skill |
| `/import` | POST | 导入外部 skill |
| `/{name}/info` | GET | 获取 skill 详情 |
| `/reload` | POST | 热重载 skill |
| `/remove` | DELETE | 移除自定义 skill |

---

## 7. 性能模型

### LLM 调用分析

Agent 的运行速度主要由 LLM 调用次数决定。每步固定开销：

| 阶段 | LLM 调用 | 说明 |
|------|---------|------|
| observation | 0 | 纯环境交互 |
| **Skill Selector** | **1** | LLM 选择激活哪些 dynamic skill |
| memory (finalize) | 0-1 | flush 无 LLM；intention 查询可选 |

Dynamic skill 的开销取决于 LLM 选择了哪些：

| Skill | LLM 调用 |
|-------|---------|
| needs（独立运行时） | 2 |
| cognition | 1（含 needs 合并） |
| plan | 2-6+ |

**典型场景**：

| 场景 | LLM 选择 | 总 LLM 调用/步 |
|------|---------|---------------|
| 平静无事 | 无 dynamic | 1（仅 selector） |
| 需要思考 | cognition | 2 |
| 思考 + 行动 | cognition + plan | 4-8 |
| 完整认知 | needs + cognition + plan | 4-8 |

### 优化要点

1. **Skill Selector** — 1 次 LLM 调用替代盲目全量执行，LLM 判断不需要的 skill 不会执行
2. **Cognition 合并调用** — 需求/情感/意图三合一，1 次 LLM 替代 3 次
3. **needs 条件跳过** — cognition 已运行时自动跳过，省 2 次 LLM
4. **Memory finalize** — 纯内存 flush 操作，0 LLM 调用
5. **渐进式披露** — 通过 `skill_names` 参数控制加载量
6. **Fallback 容错** — selector 失败时自动 fallback 到全部 dynamic skill

---

## 8. Agent 共享状态

PersonAgent 作为状态容器，所有 skill 共同读写以下状态：

| 状态 | 类型 | 写入者 | 用途 |
|------|------|-------|------|
| `_observation` | `str` | observation | 当前环境描述 |
| `_satisfactions` | `Satisfactions` | needs / cognition | 四维需求满意度 |
| `_need` | `NeedType` | needs / cognition | 当前最紧迫需求 |
| `_emotion` | `Emotion` | cognition | 6 维情感向量 |
| `_emotion_types` | `EmotionType` | cognition | 主导情感类型 |
| `_thought` | `str` | cognition | 内心独白 |
| `_intention` | `Intention` | cognition | 当前选定意图 |
| `_plan` | `Plan` | plan | 活跃执行计划 |
| `_cognition_memory` | `list[dict]` | cognition | 待 flush 的认知记录 |
| `_short_memory` | `list[dict]` | AgentBase | 短期记忆窗口 |
| `_memory` | `AsyncMemory` | AgentBase | 长期记忆（mem0） |

---

## 9. 自定义 Skill 开发

用户可以在 `workspace/custom/skills/` 下创建自定义 skill：

```
custom/skills/
└── my-skill/
    ├── SKILL.md          # 必须包含 YAML frontmatter
    └── scripts/
        └── my-skill.py   # 导出 async def run(agent, ctx)
```

### SKILL.md 示例

```yaml
---
name: market-analyst
description: 分析市场价格趋势并提供投资建议。当观测到市场、交易、价格等信息时应激活。
priority: 60
auto_load: dynamic
---

# Market Analyst

分析环境中的市场信息，为 agent 提供投资决策支持。

## What It Does
1. 从 observation 中提取市场相关信息
2. 查询历史记忆中的价格趋势
3. 生成投资建议并写入 cognition_memory
```

> **关键点**：`description` 字段要写清楚 skill 的功能和适用场景，因为 Skill Selector 的 LLM 完全依据这段描述来判断是否激活该 skill。

### 入口脚本示例

```python
# scripts/market-analyst.py
async def run(agent, ctx):
    observation = agent._observation or ""
    if not any(kw in observation.lower() for kw in ["market", "price", "trade"]):
        return

    _, result = await agent.ask_env(
        {"id": agent._id},
        "query current market prices",
        readonly=True,
    )
    agent._add_cognition_memory(
        f"Market analysis: {result}",
        type="market",
    )
    ctx["step_log"].append(f"MarketAnalyst: {result[:50]}")
```

自定义 skill 支持：
- 通过 VSCode 扩展 UI 导入和管理
- 通过 API 端点动态加载
- 运行时热重载

---

## 10. 环境模块附带的 Agent Skill

环境模块（EnvBase 子类）除了提供 `@tool` 接口外，还可以附带 **agent skill**，
为 agent 在该环境中提供特定的认知能力。

### 工作原理

```
EnvBase 提供的两层能力：

  @tool 方法  ────→  "agent 能做什么"（actions）
                      如：buy(), sell(), check_price()

  agent_skills/ ──→  "agent 应该怎么想"（cognition）
                      如：economic-reasoning skill
```

当 `PersonAgent.init(env=router)` 被调用时，agent 会自动扫描每个
env 模块的 skill 目录，注册到 SkillRegistry 中。这些 skill 和内置
skill 一样，参与 LLM Skill Selector 的选择流程。

### 目录约定

**单文件模块**（如 `economy_space.py`）：
```
contrib/env/
├── economy_space.py
└── economy_space_agent_skills/       ← <module_stem>_agent_skills/
    └── economic-reasoning/
        ├── SKILL.md
        └── scripts/economic_reasoning.py
```

**目录型模块**（如 `mobility_space/`）：
```
contrib/env/
└── mobility_space/
    ├── environment.py
    └── agent_skills/                 ← agent_skills/
        └── navigation/
            ├── SKILL.md
            └── scripts/navigation.py
```

### 使用方式

Env 模块无需额外代码——只要在约定位置放置 skill 目录即可。
`EnvBase.get_agent_skills_dir()` 会自动发现。

如需自定义路径，重写该方法：

```python
class MyCustomEnv(EnvBase):
    @classmethod
    def get_agent_skills_dir(cls) -> Path | None:
        return Path(__file__).parent / "my_special_skills"
```

### Env Skill vs Custom Skill

| 维度 | Env Skill | Custom Skill |
|------|-----------|-------------|
| 来源 | 随 env 模块分发 | 用户在 workspace 中创建 |
| source 标记 | `env:<ClassName>` | `custom` |
| 加载时机 | `PersonAgent.init()` 时自动扫描 | 手动扫描或 API 导入 |
| 优先级 | 不覆盖同名 builtin skill | 可覆盖同名 custom skill |
| 适用场景 | 环境特定的认知能力 | 实验特定的通用能力 |

---

## 11. 文件清单

```
agent/
├── __init__.py              # 导出 AgentBase, PersonAgent
├── base.py                  # AgentBase 抽象基类
├── models.py                # Pydantic 数据模型定义（含 SkillSelection）
├── person.py                # PersonAgent 编排器
├── ARCHITECTURE.md          # 本文档
└── skills/
    ├── __init__.py           # SkillRegistry 实现（必须）
    ├── observation/          # always-on: 环境感知
    │   ├── SKILL.md          # 元数据 + 行为规范
    │   └── scripts/
    │       └── observation.py
    ├── memory/               # finalize: 记忆 flush
    ├── needs/                # dynamic: 需求系统
    ├── cognition/            # dynamic: 认知与意图
    └── plan/                 # dynamic: 规划与执行
```

> **注意**：每个 skill 子目录**不需要** `__init__.py` 文件。它们只是存放 SKILL.md 和 scripts/ 的容器，不是 Python 包。

---

## 12. 性能基准

### 大规模 Agent 初始化性能

| Agent 数量 | 总时间 | 每 Agent 时间 |
|-----------|--------|--------------|
| 100 | 1.76ms | 0.018ms |
| 500 | 2.18ms | 0.004ms |
| 1000 | 4.09ms | 0.004ms |

### 按需加载 vs 全量加载

| 方式 | 100 Agents | 500 Agents | 加速比 |
|------|-----------|-----------|--------|
| 全量加载 | 0.47ms | 1.07ms | 1.0x |
| 按需加载 | 0.29ms | 0.75ms | **1.5x** |

### 内存占用

| 指标 | 数值 |
|------|------|
| 元数据大小（5 skills） | ~3KB |
| 加载后增量 | ~240 bytes |
| 100 Agents 共享 | 96 bytes/agent |

### 关键操作延迟

| 操作 | 延迟 |
|------|------|
| 扫描（元数据） | <1ms |
| 单个 skill 加载 | <0.2ms |
| 全量加载 (5 skills) | <0.3ms |
| 依赖解析 | <0.02ms |
| 能力查找 | <0.01ms |

### 并发性能

| 指标 | 数值 |
|------|------|
| 10 线程并发操作 | 3.60ms (1000 ops) |
| 每秒操作数 | **~280,000 ops/s** |

---

## 13. 依赖解析机制

### 依赖类型

1. **Skill 名称依赖** — 直接依赖另一个 skill
   ```yaml
   requires:
     - observation  # 直接使用 skill 名称
   ```

2. **能力标签依赖** — 依赖某个能力，系统自动查找提供该能力的 skill
   ```yaml
   requires:
     - intention_formation  # 能力标签，由 cognition 提供
   ```

### 解析流程

```
load_single("plan")
    │
    ├─→ 检查 requires: ["observation", "cognition"]
    │
    ├─→ 对每个依赖：
    │     ├─ 是 skill 名称？ → 直接加载
    │     └─ 是能力标签？ → find_skill_by_capability() 查找
    │
    └─→ 递归加载依赖的依赖
```

### 内置 Skill 依赖图

```
observation (priority: 0)
    │
    ├──→ needs (priority: 30)
    │      requires: [observation]
    │
    ├──→ cognition (priority: 40)
    │      requires: [observation]
    │      provides: [intention_formation, emotion_update, ...]
    │
    └──→ plan (priority: 50)
           requires: [observation, cognition]
           │
           └──→ memory (priority: 90)
                  requires: [observation]
```

### 相关 API

```python
# 获取 skill 的所有依赖（递归）
deps = registry.get_dependencies("plan")  # ["observation", "cognition"]

# 根据能力标签查找 skill
skill = registry.find_skill_by_capability("intention_formation")  # "cognition"

# 验证所有依赖是否满足
missing = registry.validate_dependencies()  # {} 如果全部满足
```
