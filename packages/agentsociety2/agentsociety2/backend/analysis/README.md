# Analysis Module

基于大语言模型的智能实验分析框架，为 AgentSociety 仿真实验提供自动化数据分析、可视化和报告生成能力。

## ✨ 核心特性

- **🤖 智能分析决策**: LLM Agent 自主决定分析策略、数据处理方法和可视化方案
- **📊 Schema-First 代码生成**: 先发现数据库结构，再生成代码，避免硬编码错误
- **🛠️ 灵活工具集成**: 
  - 内置文件系统工具（读写、搜索、替换）
  - 本地 Python 代码执行器（自动依赖检测和安装）
  - 自动工具发现和执行
- **📈 自动可视化**: LLM 决定需要的图表类型并自动生成代码
- **📄 多格式报告**: Markdown + HTML 双格式报告，支持嵌入式图片
- **🔄 多实验综合**: 跨假设对比分析，自动识别最佳策略
- **🧩 统一工具函数**: 通过 `utils.py` 提供标准化的 JSON 解析和模型验证
- **🎨 标准化资源处理**: 使用 Python `mimetypes` 自动识别文件类型

## 📦 模块组成

```
analysis/
├── models.py            # 数据模型和常量
├── utils.py             # 通用工具函数
├── analysis_agent.py    # 智能分析代理
├── data_analysis_agent.py # 数据分析代理
├── tool_executor.py     # 工具执行引擎
├── report_generator.py  # 报告生成器
└── service.py           # 主服务 + 综合分析器
```

### 核心类

| 文件 | 主要类 | 职责 |
|------|-------|------|
| `service.py` | `AnalysisService`<br>`ExperimentSynthesizer` | 主服务入口<br>多实验综合分析 |
| `analysis_agent.py` | `AnalysisAgent` | 生成洞察、发现、结论 |
| `data_analysis_agent.py` | `DataAnalysisAgent` | 执行数据分析和可视化 |
| `tool_executor.py` | `ToolExecutor` | 管理和执行工具 |
| `report_generator.py` | `ReportGenerator`<br>`AssetProcessor` | 生成报告<br>处理可视化资源 |
| `models.py` | 9 个数据模型 | 类型安全的数据结构 |
| `utils.py` | 2 个工具函数 | JSON 解析和模型验证 |

## 🚀 快速开始

### 安装和配置

```bash
# 配置 LLM (可选，默认使用配置文件)
export AGENTSOCIETY_LLM_API_KEY="your_api_key"
export AGENTSOCIETY_LLM_API_BASE="https://your.api.endpoint/v1"
```

### 单实验分析

```python
import asyncio
from agentsociety2.backend.analysis import analyze_experiment

async def main():
    # 便捷函数：一行代码完成分析
    result = await analyze_experiment(
        workspace_path="./experiment_suite",
        hypothesis_id="1",
        experiment_id="1",
        custom_instructions="重点关注收敛性和合作率"  # 可选
    )
    
    if result['success']:
        print(f"✓ 分析完成")
        print(f"  报告: {result['generated_files']['markdown']}")
        print(f"  HTML: {result['generated_files']['html']}")
        print(f"  状态: {result['execution_status']}")
        print(f"  完成度: {result['completion_percentage']}%")
    else:
        print(f"✗ 分析失败: {result.get('error')}")

asyncio.run(main())
```

### 使用服务类（更多控制）

```python
from agentsociety2.backend.analysis import AnalysisService, AnalysisConfig

# 1. 创建配置
config = AnalysisConfig(workspace_path="./experiment_suite")

# 2. 初始化服务
service = AnalysisService(config)

# 3. 执行分析
result = await service.analyze(
    hypothesis_id="1",
    experiment_id="1",
    custom_instructions="重点分析性能指标和收敛速度"
)
```

### 多实验综合分析

```python
from agentsociety2.backend.analysis import synthesize_experiments

# 自动发现所有假设和实验并综合分析
synthesis = await synthesize_experiments(
    workspace_path="./experiment_suite",
    custom_instructions="对比不同通信模式的效果"
)

print(f"最佳假设: {synthesis.best_hypothesis}")
print(f"原因: {synthesis.best_hypothesis_reason}")
print(f"报告: {synthesis.synthesis_report_path}")
```

### 使用工具函数

```python
from agentsociety2.backend.analysis import (
    parse_llm_json_response,
    parse_llm_json_to_model
)

# 解析 JSON 响应
data = parse_llm_json_response(llm_response_text)
insights = data.get("insights", [])

# 解析并验证为 Pydantic 模型
from pydantic import BaseModel

class AnalysisOutput(BaseModel):
    insights: list[str]
    conclusions: str

result = parse_llm_json_to_model(llm_response_text, AnalysisOutput)
```

## 🏗️ 系统架构

### 组件关系图

```
┌──────────────────────────────────────────────────────────┐
│                    AnalysisService                        │
│                     (主入口)                              │
└────────┬─────────────────────────────────────────────────┘
         │
         ├──► AnalysisAgent
         │    • 使用 LLM 生成洞察和结论
         │    • 支持自定义指令
         │    • 自动重试和质量判断
         │
         ├──► DataAnalysisAgent
         │    • 决定分析策略
         │    • 多轮对话调整方案
         │    • 生成可视化
         │    │
         │    └──► ToolExecutor
         │         ├─ 内置工具 (文件操作)
         │         └─ 代码执行器 (Python)
         │
         └──► ReportGenerator
              • 生成 Markdown 报告
              • 生成 HTML 报告
              │
              └──► AssetProcessor
                   • 发现可视化资源
                   • 处理图片和 PDF
                   • Base64 编码

┌──────────────────────────────────────────────────────────┐
│              ExperimentSynthesizer                        │
│              (多实验综合分析)                             │
└────────┬─────────────────────────────────────────────────┘
         │
         ├──► 自动发现假设和实验
         ├──► 复用 AnalysisService 逐个分析
         ├──► 汇总统计信息
         └──► LLM 生成综合报告
```

### 数据流

```
用户请求
   ↓
AnalysisService.analyze()
   ↓
1. _load_context()
   ├─ 读取 HYPOTHESIS.md / EXPERIMENT.md 原始 Markdown 文本
   ├─ 将完整 Markdown 文本原样作为后续 LLM 提示词上下文的一部分
   ├─ 查找数据库文件
   └─ 检查数据库表结构
   ↓
2. AnalysisAgent.analyze()
   ├─ 生成分析提示词
   ├─ 调用 LLM
   ├─ 解析响应
   └─ 质量判断和重试
   ↓
3. AssetProcessor.discover_assets()
   └─ 发现可视化文件
   ↓
4. DataAnalysisAgent.analyze_data() [如果数据库存在]
   ├─ 决定分析策略 (LLM)
   ├─ 执行工具
   │  └─ ToolExecutor.execute_tool()
   │     ├─ 内置工具
   │     └─ 代码执行器
   │        ├─ 生成代码 (LLM + Schema)
   │        ├─ 检测依赖
   │        ├─ 执行代码
   │        └─ 判断结果 (LLM)
   ├─ 决定可视化方案 (LLM)
   └─ 生成可视化
   ↓
5. AssetProcessor.process_assets()
   ├─ 复制到输出目录
   └─ 生成 Base64 编码
   ↓
6. ReportGenerator.generate()
   ├─ 生成 Markdown (LLM)
   ├─ 生成 HTML (LLM)
   └─ 判断质量和重试
   ↓
输出: 报告文件 + 可视化 + 数据
```

## 📖 API 参考

### AnalysisService

主服务入口，协调整个分析流程。

```python
class AnalysisService:
    def __init__(self, config: AnalysisConfig)
    
    async def analyze(
        self,
        hypothesis_id: str,
        experiment_id: str,
        custom_instructions: Optional[str] = None
    ) -> Dict[str, Any]
```

**返回字典**:
```python
{
    'success': bool,
    'experiment_id': str,
    'hypothesis_id': str,
    'analysis_result': AnalysisResult,
    'generated_files': {
        'markdown': str,  # 报告路径
        'html': str,      # HTML 路径
        'result_data': str,  # JSON 数据路径
        'readme': str     # README 路径
    },
    'output_directory': str,
    'execution_status': ExperimentStatus,
    'completion_percentage': float,
    'error_messages': List[str]
}
```

### AnalysisAgent

智能分析代理，生成洞察和结论。

```python
class AnalysisAgent:
    def __init__(
        self,
        llm_router=None,           # LLM 路由器（可选）
        model_name: Optional[str] = None,  # 模型名称
        temperature: float = 0.7   # 生成温度
    )
    
    async def analyze(
        self,
        context: ExperimentContext,
        custom_instructions: Optional[str] = None
    ) -> AnalysisResult
```

**AnalysisResult 字段**:
- `insights`: List[str] - 关键洞察
- `findings`: List[str] - 主要发现
- `conclusions`: str - 总结性结论
- `recommendations`: List[str] - 建议
- `generated_at`: datetime - 生成时间

### DataAnalysisAgent

数据分析代理，执行数据处理和可视化。

```python
class DataAnalysisAgent:
    def __init__(
        self,
        llm_router=None,
        model_name: Optional[str] = None,
        temperature: float = 0.7,
        workspace_path: Optional[Path] = None
    )
    
    async def analyze_data(
        self,
        context: ExperimentContext,
        analysis_result: AnalysisResult,
        db_path: Path,
        output_dir: Path
    ) -> Dict[str, Any]
```

**返回字典**:
```python
{
    'analysis_plan': Dict,      # LLM 决定的分析计划
    'tool_results': Dict,       # 工具执行结果
    'visualization_plan': List, # 可视化计划
    'generated_charts': List[Path]  # 生成的图表路径
}
```

### ToolExecutor

工具执行引擎，管理内置工具和代码执行器。

```python
class ToolExecutor:
    def __init__(
        self,
        workspace_path: Path,
        output_dir: Path
    )
    
    def discover_tools(self) -> Dict[str, Dict[str, Any]]
    
    async def execute_tool(
        self,
        tool_name: str,
        tool_type: str,  # "builtin" 或 "code_executor"
        parameters: Dict[str, Any]
    ) -> Dict[str, Any]


### ReportGenerator

报告生成器，生成 Markdown 和 HTML 格式报告。

```python
class ReportGenerator:
    def __init__(self, agent: AnalysisAgent)
    
    async def generate(
        self,
        context: ExperimentContext,
        analysis_result: AnalysisResult,
        processed_assets: Dict[str, Any],
        output_dir: Path
    ) -> Dict[str, str]  # 文件路径字典
```

### AssetProcessor

资源处理器，发现和处理可视化资源。

```python
class AssetProcessor:
    def __init__(self, workspace_path: Path)
    
    def discover_assets(
        self,
        experiment_id: str,
        hypothesis_id: str
    ) -> List[ReportAsset]
    
    def process_assets(
        self,
        assets: List[ReportAsset],
        output_dir: Path
    ) -> Dict[str, Any]
```

### ExperimentSynthesizer

多实验综合分析器。

```python
class ExperimentSynthesizer:
    def __init__(
        self,
        workspace_path: str,
        llm_temperature: float = 0.7
    )
    
    async def synthesize(
        self,
        hypothesis_ids: Optional[List[str]] = None,
        experiment_ids: Optional[List[str]] = None,
        custom_instructions: Optional[str] = None
    ) -> ExperimentSynthesis
```

### 工具函数

```python
# utils.py

def parse_llm_json_response(content: str) -> Dict[str, Any]:
    """
    解析 LLM 返回的 JSON 响应
    
    自动提取 JSON 代码块并修复常见错误
    """

def parse_llm_json_to_model(
    content: str,
    model_class: Type[T]
) -> T:
    """
    解析 LLM 响应并验证为 Pydantic 模型
    
    Raises:
        ValidationError: JSON 不符合模型结构
        JSONDecodeError: JSON 解析失败
    """
```

## 🔧 核心机制详解

### 1. Schema-First 代码生成

**问题**: LLM 生成的代码可能硬编码错误的列名。

**解决方案**: 三步策略
1. **发现阶段**: 查询数据库获取实际的表结构
2. **验证阶段**: 生成的代码必须先执行 schema discovery
3. **安全访问**: 使用发现的列名，避免硬编码

**示例代码模式**:
```python
# 步骤 1: 发现表结构
cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = [row[0] for row in cursor.fetchall()]

# 步骤 2: 获取列信息
schema = {}
for table in tables:
    cursor.execute(f"PRAGMA table_info({table})")
    columns = [row[1] for row in cursor.fetchall()]
    schema[table] = columns

# 步骤 3: 检查并使用
if 'as_experiment' in schema:
    table_cols = schema['as_experiment']
    # 使用发现的列名进行查询
```

### 2. 数据库表检查机制

在访问数据库前，自动检查表是否存在：

```python
# service.py 中的 _analyze_status 方法

# 检查文件
if not db_path.exists():
    return ExperimentStatus.FAILED, 0.0, ["Database file not found"]

# 检查表
cursor.execute(
    "SELECT name FROM sqlite_master WHERE type='table' AND name='as_experiment'"
)
if not cursor.fetchone():
    # 优雅降级：返回 UNKNOWN 而不是崩溃
    return ExperimentStatus.UNKNOWN, 0.0, [
        "Database structure incomplete: as_experiment table not found"
    ]
```

### 3. 统一 JSON 解析

所有 LLM 响应解析都通过 `utils.py` 统一处理：

```python
# 在各个 Agent 中使用
from .utils import parse_llm_json_response, parse_llm_json_to_model

# 简单解析
data = parse_llm_json_response(llm_response)

# 带验证的解析
judgment = parse_llm_json_to_model(llm_response, AnalysisJudgment)
```

### 4. MIME 类型自动识别

使用 Python 标准库 `mimetypes`：

```python
import mimetypes

mime_type, _ = mimetypes.guess_type(file_path)
if not mime_type:
    mime_type = "application/octet-stream"
```


### 5. 循环依赖处理

使用局部导入打破循环：

```python
# service.py

# 不在文件顶部导入 (会导致循环依赖)
# from .data_analysis_agent import DataAnalysisAgent  ❌

# 而是在需要时导入
async def analyze(self, ...):
    if db_path:
        from .data_analysis_agent import DataAnalysisAgent  # ✓
        data_agent = DataAnalysisAgent(...)
```

**循环链**: service → DataAnalysisAgent → ToolExecutor → ToolRegistry → DataAnalysisTool → AnalysisService

**解决方案**: 局部导入在运行时打破循环

### 6. 智能重试机制

**代码执行重试** (最多 5 次):
```python
for attempt in range(MAX_RETRIES):
    # 生成代码
    generated_code = await code_generator.generate(...)
    
    # 执行代码
    result = await executor.execute(generated_code)
    
    # LLM 判断结果
    judgment = await self._judge_execution_result(result)
    
    if judgment.success:
        break
    
    # 根据 LLM 的反馈改进代码
    feedback = f"Previous attempt failed: {judgment.reason}\n"
    feedback += f"What to fix: {judgment.retry_instruction}"
```

**报告生成重试** (最多 5 次):
- LLM 生成报告
- LLM 判断质量
- 如果不满足要求，根据反馈重新生成

## 📁 文件结构

### 源代码结构

```
agentsociety2/backend/analysis/
├── __init__.py                - 模块接口导出
├── models.py                  - 9 个数据模型 + 常量
├── utils.py                   - 2 个工具函数
├── analysis_agent.py          - 智能分析代理
├── data_analysis_agent.py     - 数据分析代理
├── tool_executor.py           - 工具执行引擎
├── report_generator.py        - 报告生成器
├── service.py                 - 主服务 + 综合分析器
└── README.md                # 本文档

```

### 工作空间结构

```
workspace/
├── hypothesis_1/
│   ├── HYPOTHESIS.md                    # 假设定义
│   ├── experiment_1/
│   │   ├── EXPERIMENT.md                # 实验定义
│   │   └── run/
│   │       ├── sqlite.db                # 实验数据
│   │       └── artifacts/               # 生成的文件
│   │           └── *.png
│   └── experiment_2/
│       └── ...
├── hypothesis_2/
│   └── ...
└── presentation/                        # 分析结果输出
    ├── hypothesis_1/
    │   ├── experiment_1/
    │   │   ├── analysis_report.md       # Markdown 报告
    │   │   ├── analysis_report.html     # HTML 报告
    │   │   ├── README.md                # 文件说明
    │   │   ├── assets/                  # 可视化资源
    │   │   │   ├── chart_1.png
    │   │   │   └── chart_2.png
    │   │   └── data/
    │   │       └── analysis_result.json # 原始数据
    │   └── experiment_2/
    │       └── ...
    └── synthesis/                       # 综合分析报告
        └── synthesis_report_YYYYMMDD_HHMMSS.md
```

## ⚙️ 配置

### 环境变量

```bash
# LLM 配置 (可选，使用配置文件中的默认值)
export AGENTSOCIETY_LLM_API_KEY="sk-xxx"
export AGENTSOCIETY_LLM_API_BASE="https://api.example.com/v1"

# 日志级别 (可选)
export AGENTSOCIETY_LOG_LEVEL="INFO"
```

### 配置对象

```python
from agentsociety2.backend.analysis import AnalysisConfig

config = AnalysisConfig(
    workspace_path="./experiment_suite"  # 必需：工作空间根目录
)
```

**自动验证**:
- ✅ 路径必须存在
- ✅ 自动转换为绝对路径
- ✅ 自动创建 presentation 目录

### 支持的文件格式

```python
# 图片格式
SUPPORTED_IMAGE_FORMATS = {".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp"}

# 所有资产格式
SUPPORTED_ASSET_FORMATS = SUPPORTED_IMAGE_FORMATS | {".pdf"}
```

## 💡 使用示例

### 示例 1: 基础分析

```python
import asyncio
from agentsociety2.backend.analysis import analyze_experiment

async def main():
    result = await analyze_experiment(
        workspace_path="./experiments",
        hypothesis_id="1",
        experiment_id="1"
    )
    
    print(f"Status: {result['execution_status']}")
    print(f"Insights: {len(result['analysis_result'].insights)}")

asyncio.run(main())
```

### 示例 2: 自定义分析指令

```python
result = await analyze_experiment(
    workspace_path="./experiments",
    hypothesis_id="1",
    experiment_id="1",
    custom_instructions="""
    请重点关注以下方面:
    1. 收敛速度和稳定性
    2. 合作率的演化趋势
    3. 异常值和离群点分析
    4. 不同阶段的性能对比
    """
)
```

### 示例 3: 批量分析多个实验

```python
from agentsociety2.backend.analysis import AnalysisService, AnalysisConfig

config = AnalysisConfig(workspace_path="./experiments")
service = AnalysisService(config)

experiments = [("1", "1"), ("1", "2"), ("2", "1")]

for hyp_id, exp_id in experiments:
    result = await service.analyze(hyp_id, exp_id)
    print(f"Hypothesis {hyp_id}, Experiment {exp_id}: {result['success']}")
```

### 示例 4: 综合分析并导出

```python
from agentsociety2.backend.analysis import ExperimentSynthesizer

synthesizer = ExperimentSynthesizer("./experiments")
synthesis = await synthesizer.synthesize()

# 访问结果
print(f"分析了 {len(synthesis.hypothesis_summaries)} 个假设")
print(f"最佳假设: {synthesis.best_hypothesis}")
print(f"原因: {synthesis.best_hypothesis_reason}")

# 查看每个假设的统计
for summary in synthesis.hypothesis_summaries:
    print(f"\n假设 {summary.hypothesis_id}:")
    print(f"  实验数: {summary.experiment_count}")
    print(f"  成功数: {summary.successful_experiments}")
    print(f"  平均完成度: {summary.total_completion:.1f}%")
```

### 示例 5: 使用工具函数

```python
from agentsociety2.backend.analysis import parse_llm_json_to_model
from pydantic import BaseModel
from typing import List

class CustomAnalysis(BaseModel):
    key_points: List[str]
    summary: str
    score: float

# 假设从 LLM 获得响应
llm_response = """
这是分析结果:
```json
{
    "key_points": ["点1", "点2", "点3"],
    "summary": "总体表现良好",
    "score": 8.5
}
```
"""

# 解析并验证
analysis = parse_llm_json_to_model(llm_response, CustomAnalysis)
print(f"得分: {analysis.score}")
print(f"要点: {', '.join(analysis.key_points)}")
```

## ❓ 常见问题

### Q1: 数据库表不存在怎么办？

**问题**: `sqlite3.OperationalError: no such table: as_experiment`

**原因**: 数据库文件存在但表结构不完整

**解决**: 系统会自动处理，返回 `UNKNOWN` 状态并继续其他分析
```python
# 自动检查
cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='as_experiment'")
if not cursor.fetchone():
    return ExperimentStatus.UNKNOWN, 0.0, ["Database structure incomplete"]
```

### Q2: 如何自定义 LLM 模型？

```python
from agentsociety2.backend.analysis import AnalysisAgent

# 方法 1: 创建 Agent 时指定
agent = AnalysisAgent(model_name="qwen2.5-72b-instruct")

# 方法 2: 使用环境变量
# export AGENTSOCIETY_ANALYSIS_LLM_MODEL="qwen2.5-72b-instruct"
```

### Q3: 可视化没有生成？

**检查清单**:
1. ✅ 数据库文件存在: `workspace/hypothesis_X/experiment_Y/run/sqlite.db`
2. ✅ Python 环境可用: 能安装 matplotlib, pandas 等
3. ✅ 输出目录可写: `presentation/hypothesis_X/experiment_Y/assets/`
4. ✅ 查看日志: 搜索 "visualization" 或 "chart" 关键词

**调试**:
```python
# 查看工具执行结果
result = await service.analyze(hyp_id, exp_id)
# 检查日志中的工具执行状态
```

### Q4: 如何查看详细日志？

```python
import logging

# 设置日志级别
logging.basicConfig(level=logging.DEBUG)

# 或使用环境变量
# export AGENTSOCIETY_LOG_LEVEL="DEBUG"
```

### Q5: 报告生成失败？

**可能原因**:
1. LLM 返回的不是有效 JSON
2. 网络问题导致请求失败
3. Token 超限

**解决**:
- 系统会自动重试最多 5 次
- 检查 LLM 配置和网络连接
- 查看日志中的错误信息

### Q6: 为什么有些导入是局部的？

**原因**: 避免循环依赖

**示例**:
```python
# service.py 中
if db_path:
    from .data_analysis_agent import DataAnalysisAgent  # 局部导入
```

这是**设计选择**，用于打破循环依赖链。

### Q7: 如何扩展内置工具？

```python
# 在 tool_executor.py 中添加新工具类
from agentsociety2.backend.tools.your_tool import YourTool

class ToolExecutor:
    def _initialize_builtin_tools(self):
        tool_classes = [
            # ... 现有工具
            YourTool,  # 添加新工具
        ]
```

### Q8: 执行代码时找不到依赖？

**系统会自动**:
1. 检测代码中的 import 语句
2. 尝试 import
3. 如果失败，自动 pip install
4. 重新执行代码

**如果仍然失败**:
- 检查网络连接
- 检查 pip 配置
- 手动预装依赖: `pip install pandas matplotlib seaborn`

## 🚀 性能和优化

### 代码质量提升

**v2.0 优化** (最近完成):
- ✅ 删除 16+ 处不必要的 try-except
- ✅ 统一 JSON 解析逻辑 (减少重复)
- ✅ 使用标准库替代硬编码
- ✅ 改进数据库检查机制
- ✅ 正确处理循环依赖

### 模块大小

| 指标 | 数值 |
|------|------|
| 总代码行数 | 3,139 行 |
| 类数量 | 15 个 |
| 主要函数 | 50+ 个 |
| 工具函数 | 2 个 (utils.py) |

### 执行效率

- **单实验分析**: 约 1-3 分钟 (取决于 LLM 速度和数据量)
- **多实验综合**: 约 N × (1-3) 分钟 + 综合时间
- **代码执行**: 支持超时控制 (默认 600 秒)
- **自动重试**: 最多 5 次 (避免无限循环)

## 📝 更新日志

### v2.0 (2026-01-28)

**核心改进**:
- ✅ 创建 `utils.py` 统一 JSON 解析
- ✅ 使用 `mimetypes` 替代硬编码
- ✅ 删除不必要的异常处理
- ✅ 数据库表存在性检查
- ✅ 循环依赖处理优化

**新增功能**:
- `parse_llm_json_response()` - 通用 JSON 解析
- `parse_llm_json_to_model()` - 带验证的模型解析
- 数据库表自动检查机制

**Bug 修复**:
- 修复数据库表不存在时崩溃
- 修复循环依赖导入错误
- 修复 MIME 类型缺失问题

### v1.0 (初始版本)

- 基础分析框架
- LLM 集成
- 代码执行器
- 报告生成

## 📄 许可证

本模块是 AgentSociety 项目的一部分。

## 🤝 贡献指南

欢迎贡献！请遵循以下步骤:

1. Fork 项目
2. 创建特性分支 (`git checkout -b feature/AmazingFeature`)
3. 提交更改 (`git commit -m 'Add some AmazingFeature'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 开启 Pull Request

### 代码规范

- 遵循 PEP 8
- 使用类型提示
- 编写文档字符串
- 添加单元测试

## 📧 联系方式

如有问题或建议，请在项目仓库提交 Issue。

---

**文档版本**: 2.0  
**最后更新**: 2026-01-28  
**维护状态**: ✅ 积极维护
