# Analysis Sub-Agent Module

> 基于 LLM 驱动的分析子智能体，为 AgentSociety 仿真实验提供自动化数据分析、可视化及报告生成。

## 目录

- [概述](#概述)
- [架构](#架构)
- [模块结构](#模块结构)
- [输出文件结构](#输出文件结构)
- [公共接口](#公共接口)
- [配置](#配置)
- [快速开始](#快速开始)
- [扩展与集成](#扩展与集成)

---

## 概述

分析子智能体封装数据科学相关逻辑，向主 Agent 暴露最小化接口，实现关注点分离：

| 角色 | 职责 |
|------|------|
| **主 Agent** | 决定何时触发分析、分析范围（单实验 vs 跨实验综合） |
| **分析子智能体** | 制定分析策略、执行数据处理、生成可视化、撰写综合报告 |

**核心能力**：假设驱动、Schema 感知、沙箱代码执行、自我修正、叙事报告、跨实验综合。

---

## 架构

### 分层结构

```
┌─────────────────────────────────────────────────────────────┐
│  Orchestration Layer                                        │
│  Analyzer (单实验) · Synthesizer (跨实验综合)                  │
├─────────────────────────────────────────────────────────────┤
│  Unified Analysis Agent                                     │
│  AnalysisAgent (数据优先分析：读取数据 → 生成洞察 → 可视化)     │
├─────────────────────────────────────────────────────────────┤
│  Execution Layer                                            │
│  AnalysisRunner (沙箱执行) · Reporter (报告生成)              │
└─────────────────────────────────────────────────────────────┘
```

### 数据优先分析流程

```
┌──────────────┐    ┌──────────────┐    ┌──────────────┐    ┌──────────────┐
│ 读取数据结构  │ →  │ 生成洞察     │ →  │ 数据分析     │ →  │ 可视化报告    │
│ (Schema/样本) │    │ (基于实际数据) │    │ (执行代码)   │    │ (MD/HTML)    │
└──────────────┘    └──────────────┘    └──────────────┘    └──────────────┘
```

### 组件说明

| 组件 | 职责 |
|------|------|
| `Analyzer` | 单实验分析生命周期管理 |
| `Synthesizer` | 跨实验综合与对比分析 |
| `AnalysisAgent` | **统一分析智能体**：数据优先的分析流程，合并洞察、策略、执行与可视化 |
| `AnalysisRunner` | 沙箱执行 Python 代码 |
| `Reporter` | 洞察与图表组装为 Markdown/HTML 报告 |
| `AssetProcessor` | 静态资源管理与报告嵌入 |

---

## 模块结构

```
analysis/
├── service.py          # 编排入口 (Analyzer, Synthesizer, run_analysis, run_synthesis)
├── agents.py           # 统一分析智能体 (AnalysisAgent)
├── tool_executor.py    # 执行环境 (AnalysisRunner)
├── report_generator.py # 报告引擎 (Reporter, AssetProcessor)
├── models.py           # 数据模型与配置 (Pydantic)
├── prompts.py          # LLM 提示模板
├── utils.py            # 路径管理、Schema 提取、XML 解析
├── eda.py              # EDA 集成（多种工具）
└── skills/             # 智能体能力定义
    ├── 00_xml_contract.md
    ├── 05_subagent_workflow.md
    ├── 10_visualization_reliability.md
    ├── 20_core_skills.md
    └── 30_advanced_analysis.md
```

### EDA 工具矩阵

| 函数 | 功能 | 输出 |
|------|------|------|
| `generate_eda_profile()` | ydata-profiling 全面画像 | `eda_profile.html` |
| `generate_sweetviz_profile()` | Sweetviz 相关性分析 | `eda_sweetviz.html` |
| `generate_missingno_visualization()` | 缺失值可视化 | `eda_missingno.png` |
| `generate_multitable_summary()` | 多表汇总图 | `eda_table_summary.png` |
| `generate_quick_stats()` | pandas 统计摘要 | Markdown 文本 |
| `generate_full_eda_report()` | 完整 EDA 套件 | 所有上述文件 |

### 数据优先分析原则

`AnalysisAgent` 遵循**数据优先**原则，确保分析基于实际数据而非假设：

1. **先读数据**：分析前先读取数据库 schema、行数、样本数据
2. **洞察接地**：洞察生成时能看到实际数据结构，避免空洞分析
3. **性能安全**：大数据集自动采样，防止内存溢出
4. **总结先行**：每轮工具执行后先压缩总结，再进入下一轮策略迭代（默认开启）

### 可用分析库

| 库 | 用途 | 场景 |
|----|------|------|
| `pandas` / `numpy` | 数据处理 | 基础操作 |
| `matplotlib` / `seaborn` | 静态可视化 | 报告图表 |
| `scipy.stats` | 统计检验 | t-test, ANOVA, chi-square |
| `statsmodels` | 回归分析 | OLS, 时间序列 |
| `networkx` | 网络分析 | Agent 交互图 |
| `sklearn` | 机器学习 | 聚类、降维 |

**技能选择逻辑**：
- `required: true` 的技能始终加载（如 `xml_contract`）
- 在严格模式下（`analysis_skill_strict_selection=true`），仅加载 `analysis_skill_names` 中列出的技能 + 必需技能
- 性能安全规则已在代码层面（`tool_executor.py`）强制执行，不再依赖 LLM 提示

---

## 输出文件结构

分析模块运行后，在 `workspace/presentation/` 和 `workspace/synthesis/` 下生成以下结构，供下游工具（如 generate_paper）或人工查阅使用。

### 单实验分析产物（`analyze` 工具）

路径：`{workspace}/presentation/hypothesis_{id}/experiment_{id}/`

```
presentation/
└── hypothesis_{id}/
    └── experiment_{id}/
        ├── report.md              # Markdown 报告（主输出）
        ├── report.html            # HTML 报告（含嵌入式 EDA 链接）
        ├── README.md              # 本目录文件说明
        ├── data/
        │   ├── analysis_summary.json   # 分析结果结构化数据（insights, findings, conclusions, recommendations）
        │   ├── eda_profile.html        # ydata-profiling EDA 概览（可选）
        │   └── eda_sweetviz.html       # Sweetviz EDA 报告（可选）
        ├── charts/                # AnalysisAgent 生成的图表与中间数据
        │   ├── *.png              # 可视化图表（如 cooperation_by_group.png）
        │   ├── *.csv, *.json      # 分析中间数据、诊断输出
        │   └── analysis_*/       # 代码执行临时目录（可含子图）
        └── assets/                # 报告引用的静态资源（从 charts + run/artifacts 复制）
            └── *.png, *.jpg, ...  # 报告内嵌图片
```

| 文件/目录 | 说明 |
|-----------|------|
| `report.md` | 主报告 Markdown，含洞察、发现、结论、推荐及图表引用 |
| `report.html` | 完整 HTML 报告，可嵌入 EDA 链接 |
| `data/analysis_summary.json` | 结构化分析结果，含 `insights`、`findings`、`conclusions`、`recommendations` |
| `data/eda_profile.html` | ydata-profiling 生成的数据画像（表统计、分布、缺失） |
| `data/eda_sweetviz.html` | Sweetviz 目标分析与相关性报告 |
| `charts/` | AnalysisAgent 执行 Python 代码的输出目录，图表与中间数据 |
| `assets/` | 报告实际引用的图片，由 AssetProcessor 从 charts 与 run/artifacts 复制 |

### 跨实验综合分析产物（`synthesize` 工具）

路径：`{workspace}/synthesis/`（默认，可由 `AnalysisConfig.synthesis_output_dir_name` 配置）

```
synthesis/
├── synthesis_report_{YYYYMMDD_HHMMSS}.md    # 综合报告 Markdown
├── synthesis_report_{YYYYMMDD_HHMMSS}.html  # 综合报告 HTML
└── assets/
    └── synthesis_comparison.png             # 跨假设对比图（完成度、成功实验数）
```

| 文件 | 说明 |
|------|------|
| `synthesis_report_*.md` | 跨假设综合报告，含策略、对比分析、结论与推荐 |
| `synthesis_report_*.html` | 综合报告 HTML 版本 |
| `assets/synthesis_comparison.png` | 各假设完成度与成功实验数柱状图 |

---

## 公共接口

### 工具入口（主 Agent 调用）

通过 Claude Code skills 暴露：

| Skill | 作用 | 底层 |
|------|------|------|
| `agentsociety-analysis` | 单实验分析 | `Analyzer.analyze()` |
| `agentsociety-synthesize` | 跨实验综合 | `Synthesizer.synthesize()` |

### Python API

```python
from agentsociety2.skills.analysis import (
    Analyzer,
    Synthesizer,
    AnalysisAgent,  # 新的统一分析智能体
    run_analysis,
    run_synthesis,
    AnalysisConfig,
)
```

| 入口 | 说明 |
|------|------|
| `Analyzer(config).analyze(hypothesis_id, experiment_id, ...)` | 单实验分析（推荐） |
| `AnalysisAgent(config).analyze(context, db_path, output_dir, ...)` | 直接使用分析智能体 |
| `Synthesizer(workspace_path, config).synthesize(...)` | 跨实验综合 |
| `run_analysis(workspace_path, hypothesis_id, experiment_id, ...)` | 便捷函数 |
| `run_synthesis(workspace_path, ...)` | 便捷函数 |

---

## 配置

`AnalysisConfig` 定义于 `models.py`，关键参数：

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `workspace_path` | 必填 | 仿真工作区根目录 |
| `max_analysis_retries` | 5 | 分析/报告生成最大重试 |
| `code_execution_timeout` | 600 | 代码执行超时（秒） |
| `temperature` | 0.7 | LLM 温度 |
| `llm_profile_default` | "default" | 洞察/报告/策略用 LLM 配置 |
| `llm_profile_coder` | "coder" | 代码生成用 LLM 配置 |
| `analysis_skill_names` | `[xml_contract, subagent_workflow, visualization_reliability, core_skills, advanced_analysis]` | 显式启用的分析提示技能名称列表（必需技能始终加载） |
| `analysis_skill_strict_selection` | `true` | 严格模式：只注入 `analysis_skill_names` 中列出的技能（必需技能除外） |

---

## 快速开始

```python
import asyncio
from agentsociety2.skills.analysis import Analyzer, AnalysisConfig

async def main():
    config = AnalysisConfig(workspace_path="./workspace")
    analyzer = Analyzer(config)

    result = await analyzer.analyze(
        hypothesis_id="hyp_1",
        experiment_id="exp_1",
        custom_instructions="Focus on agent cooperation rates.",
    )

    if result["success"]:
        print(f"Report: {result['generated_files']['html']}")

if __name__ == "__main__":
    asyncio.run(main())
```

---

## 扩展与集成

### 支持的库

| 库 | 用途 | 启用方式 |
|----|------|----------|
| ydata-profiling | HTML 画像报告 | 配置启用 |
| sweetviz | 目标分析与对比 | 配置启用 |
| pandas / matplotlib / seaborn | 沙箱内分析与绘图 | 内置支持 |

### 容错机制

- **错误传播**：执行失败通过 STDERR 反馈给 Reporter
- **优雅降级**：部分图表缺失仍可生成报告
- **自我修正**：AnalysisAgent 解析错误日志并重试代码生成
