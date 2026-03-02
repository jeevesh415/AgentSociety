# Analysis Sub-Agent Module

> 基于 LLM 驱动的分析子智能体，为 AgentSociety 仿真实验提供自动化数据分析、可视化及报告生成。

## 目录

- [概述](#概述)
- [架构](#架构)
- [模块结构](#模块结构)
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
│  Cognitive & Execution Layer                                │
│  InsightAgent (定性分析) · DataExplorer (定量分析) · AnalysisRunner │
├─────────────────────────────────────────────────────────────┤
│  Reporting Layer                                            │
│  Reporter · AssetProcessor                                  │
└─────────────────────────────────────────────────────────────┘
```

### 组件说明

| 组件 | 职责 |
|------|------|
| `Analyzer` | 单实验分析生命周期管理 |
| `Synthesizer` | 跨实验综合与对比分析 |
| `InsightAgent` | 定性分析、假设验证、报告叙事 |
| `DataExplorer` | 定量分析、SQL 查询、Python 可视化代码生成 |
| `AnalysisRunner` | 沙箱执行 Python 代码 |
| `Reporter` | 洞察与图表组装为 Markdown/HTML 报告 |
| `AssetProcessor` | 静态资源管理与报告嵌入 |

---

## 模块结构

```
analysis/
├── service.py          # 编排入口 (Analyzer, Synthesizer, run_analysis, run_synthesis)
├── agents.py           # 核心智能体 (InsightAgent, DataExplorer)
├── tool_executor.py    # 执行环境 (AnalysisRunner)
├── report_generator.py # 报告引擎 (Reporter, AssetProcessor)
├── models.py           # 数据模型与配置 (Pydantic)
├── prompts.py          # LLM 提示模板
├── utils.py            # 路径管理、Schema 提取、XML 解析
├── eda.py              # EDA 集成 (ydata-profiling, sweetviz, quick_stats)
└── skills/             # 智能体能力定义
    ├── 00_xml_contract.md
    ├── 10_visualization_reliability.md
    └── 20_core_skills.md
```

---

## 公共接口

### 工具入口（主 Agent 调用）

通过 `agentsociety2.backend.tools` 暴露：

| 工具 | 作用 | 底层 |
|------|------|------|
| `analyze` | 单实验分析 | `Analyzer.analyze()` |
| `synthesize` | 跨实验综合 | `Synthesizer.synthesize()` |

### Python API

```python
from agentsociety2.backend.analysis import (
    Analyzer,
    Synthesizer,
    run_analysis,
    run_synthesis,
    AnalysisConfig,
)
```

| 入口 | 说明 |
|------|------|
| `Analyzer(config).analyze(hypothesis_id, experiment_id, ...)` | 单实验分析 |
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

---

## 快速开始

```python
import asyncio
from agentsociety2.backend.analysis import Analyzer, AnalysisConfig

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
- **自我修正**：DataExplorer 解析错误日志并重试代码生成
