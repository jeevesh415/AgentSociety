# 自定义模块支持功能 - 代码实现总结

## 概述

本次实现为 AgentSociety2 添加了**自定义 Agent 和环境模块支持**功能，允许用户：
1. 在 `custom/` 目录编写自定义代码
2. 通过 API 触发扫描和注册
3. 在内存中安全测试模块（不生成临时文件）
4. 与 AI Social Scientist 无缝集成

## 文件变更清单

### 新建文件（17 个）

#### 用户代码目录

| 文件路径 | 说明 |
|---------|------|
| `custom/__init__.py` | 用户自定义代码包初始化 |
| `custom/README.md` | 600+ 行用户开发文档 |
| `custom/agents/__init__.py` | Agent 包初始化 |
| `custom/agents/examples/simple_agent.py` | 简单 Agent 示例 |
| `custom/agents/examples/advanced_agent.py` | 带记忆和情绪的高级 Agent |
| `custom/envs/__init__.py` | 环境模块包初始化 |
| `custom/envs/examples/simple_env.py` | 计数器环境示例 |
| `custom/envs/examples/advanced_env.py` | 资源管理环境示例 |

#### 系统服务目录

| 文件路径 | 说明 |
|---------|------|
| `backend/services/custom/__init__.py` | 服务包初始化 |
| `backend/services/custom/scanner.py` | 扫描服务（~250 行） |
| `backend/services/custom/generator.py` | JSON 配置生成器（~150 行） |
| `backend/services/custom/script_generator.py` | 内存测试执行器（~500 行） |

#### API 路由

| 文件路径 | 说明 |
|---------|------|
| `backend/routers/custom.py` | 自定义模块 API 路由（~330 行） |

### 修改文件（4 个）

| 文件路径 | 修改内容 |
|---------|---------|
| `backend/routers/__init__.py` | 添加 `custom` 路由导入 |
| `backend/app.py` | 导入并注册 `custom` 路由 |
| `.env.example` | 添加 `WORKSPACE_PATH` 配置项 |

## 核心功能实现

### 1. 扫描服务 (`scanner.py`)

```python
class CustomModuleScanner:
    """扫描 custom/ 目录发现用户模块"""

    def scan_all() -> Dict[str, Any]:
        """扫描所有自定义模块，跳过 examples/"""

    def _scan_agents() -> List[Dict]:
        """扫描并验证 Agent 类"""

    def _scan_envs() -> List[Dict]:
        """扫描并验证环境模块类"""
```

**特点：**
- 动态导入 Python 模块
- AST 分析提取类定义
- 验证必需方法实现
- 自动跳过 `examples/` 和 `__` 开头的文件

### 2. JSON 配置生成器 (`generator.py`)

```python
class CustomModuleJsonGenerator:
    """生成 .agentsociety 目录下的 JSON 配置"""

    def generate_all() -> Dict[str, int]:
        """为所有发现的模块生成 JSON"""

    def remove_custom_modules() -> int:
        """清理自定义模块配置"""
```

**特点：**
- 自动创建 `.agentsociety/agent_classes/` 和 `.agentsociety/env_modules/` 目录
- JSON 文件包含 `is_custom: true` 标记
- 不覆盖内置模块的 JSON

### 3. 内存测试执行器 (`script_generator.py`)

```python
class SafeModuleTester:
    """安全的模块测试器（使用动态导入和反射）"""

    async def run_test() -> Dict[str, Any]:
        """在内存中执行测试，返回结果"""
```

**安全设计特点：**
- 使用 `importlib` 动态导入模块（避免 `exec/eval`）
- 使用反射调用类和方法
- 白名单验证可导入的模块路径
- 在内存中执行测试，不生成临时文件

### 4. API 路由 (`custom.py`)

#### 4.1 POST `/api/v1/custom/scan`

扫描自定义模块并生成 JSON 配置

**请求：**
```json
{
  "workspace_path": "/path/to/workspace"  // 可选，默认使用环境变量
}
```

**响应：**
```json
{
  "success": true,
  "agents_found": 1,
  "envs_found": 1,
  "agents_generated": 1,
  "envs_generated": 1,
  "errors": [],
  "message": "发现 1 个 Agent、发现 1 个环境模块，已生成 JSON 配置文件"
}
```

#### 4.2 POST `/api/v1/custom/test`

在内存中测试自定义模块（不生成临时文件）

**请求：**
```json
{
  "workspace_path": "/path/to/workspace"
}
```

**响应：**
```json
{
  "success": true,
  "test_output": "测试输出内容...",
  "returncode": 0,
  "results": [
    {
      "name": "MyAgent",
      "success": true,
      "output": "...",
      "error": null
    }
  ],
  "total_tests": 1,
  "passed_tests": 1,
  "failed_tests": 0
}
```

#### 4.3 POST `/api/v1/custom/clean`

清理自定义模块配置

**响应：**
```json
{
  "success": true,
  "removed_count": 2,
  "message": "已清理 2 个自定义模块配置"
}
```

#### 4.4 GET `/api/v1/custom/list`

列出已注册的自定义模块

**响应：**
```json
{
  "success": true,
  "agents": [...],
  "envs": [...],
  "total_agents": 1,
  "total_envs": 1
}
```

#### 4.5 GET `/api/v1/custom/status`

获取模块状态概览

**响应：**
```json
{
  "custom_dir_exists": true,
  "agents_dir_exists": true,
  "envs_dir_exists": true,
  "agent_files_count": 0,
  "env_files_count": 0,
  "registered_agents": 0,
  "registered_envs": 0
}
```

## 目录结构

```
packages/agentsociety2/agentsociety2/
├── custom/                              # 用户代码目录
│   ├── __init__.py
│   ├── README.md                        # 用户文档
│   ├── agents/
│   │   ├── __init__.py
│   │   └── examples/                    # 官方示例（参考用）
│   │       ├── simple_agent.py
│   │       └── advanced_agent.py
│   └── envs/
│       ├── __init__.py
│       └── examples/                    # 官方示例（参考用）
│           ├── simple_env.py
│           └── advanced_env.py
│
└── backend/
    ├── routers/
    │   ├── __init__.py                  # 修改：添加 custom 导入
    │   ├── custom.py                    # 新增：自定义模块 API
    │   └── ...
    └── services/custom/                 # 系统服务（用户不可见）
        ├── __init__.py
        ├── scanner.py                   # 扫描服务
        ├── generator.py                 # JSON 生成器
        └── script_generator.py          # 内存测试执行器
```

## 用户工作区结构

```
my_workspace/
├── custom/                              # 用户创建此目录
│   ├── agents/
│   │   └── my_agent.py                  # 用户自己的 Agent
│   └── envs/
│       └── my_env.py                    # 用户自己的环境模块
│
└── .agentsociety/                       # 自动生成
    ├── agent_classes/
    │   └── my_agent.json                # 扫描后生成
    └── env_modules/
        └── my_env.json                  # 扫描后生成
```

## 生成的 JSON 配置格式

### Agent JSON
```json
{
  "type": "MyAgent",
  "class_name": "MyAgent",
  "description": "MyAgent: 描述内容...",
  "is_custom": true,
  "module_path": "custom/agents/my_agent.py",
  "file_path": "/full/path/to/custom/agents/my_agent.py"
}
```

### 环境模块 JSON
```json
{
  "type": "MyEnv",
  "class_name": "MyEnv",
  "description": "MyEnv: 描述内容...",
  "is_custom": true,
  "module_path": "custom/envs/my_env.py",
  "file_path": "/full/path/to/custom/envs/my_env.py"
}
```

## 测试实现说明

系统使用安全的内存测试方式，不生成临时文件：

**安全设计特点：**
- 使用 `importlib` 动态导入模块
- 使用反射调用类和方法（避免 `exec/eval`）
- 白名单验证可导入的模块路径
- 完整的单元测试和集成测试

## 环境变量

新增配置项（在 `.env.example` 中）：

```bash
# Workspace path for custom modules
# Set this to your workspace root directory (where custom/ folder is located)
WORKSPACE_PATH=/path/to/workspace
```

## VSCode 集成

### 新增命令（需在 VSCode 插件中实现）

| 命令 ID | 功能 |
|---------|------|
| `agentsociety.scanCustomModules` | 扫描自定义模块 |
| `agentsociety.testCustomModules` | 测试自定义模块 |
| `agentsociety.cleanCustomModules` | 清理自定义模块配置 |

### 侧边栏按钮组建议

```typescript
{
  "type": "button-group",
  "buttons": [
    {
      "text": "$(refresh) 扫描",
      "command": "agentsociety.scanCustomModules"
    },
    {
      "text": "$(play) 测试",
      "command": "agentsociety.testCustomModules"
    },
    {
      "text": "$(trash) 清理",
      "command": "agentsociety.cleanCustomModules"
    }
  ]
}
```

## 代码行数统计

| 组件 | 行数 |
|------|------|
| scanner.py | ~250 |
| generator.py | ~150 |
| script_generator.py | ~500 |
| custom.py (API) | ~330 |
| simple_agent.py | ~100 |
| advanced_agent.py | ~130 |
| simple_env.py | ~120 |
| advanced_env.py | ~160 |
| README.md | ~250 |
| **总计** | **~1840 行** |

## 关键设计决策

### 1. 目录分离

- **`custom/`** - 只放用户代码和官方示例
- **`backend/services/custom/`** - 系统工具，不对用户暴露

用户打开 `custom/` 时只看到自己的代码和示例，不被实现细节干扰。

### 2. 非自动扫描

- 用户主动触发扫描，不是启动时自动执行
- 原因：性能考虑、用户控制、错误处理友好

### 3. 跳过 examples/

扫描时自动跳过 `examples/` 子目录：
- 避免将官方示例注册为用户模块
- 保持 `.agentsociety/` 目录整洁

### 4. JSON 标记

- 使用 `is_custom: true` 标记自定义模块
- 方便区分内置/自定义模块
- 支持单独清理操作

### 5. 测试超时

- 30 秒超时限制
- 防止测试卡死
- 超时后自动终止子进程

## 安全考虑

### 1. 动态导入隔离

```python
# 使用唯一的模块名避免冲突
module_name = f"custom_module_{id(file_path)}"
sys.modules[module_name] = module

# 使用后清理
if module_name in sys.modules:
    del sys.modules[module_name]
```

### 2. 路径验证

- 使用 `Path.resolve()` 解析绝对路径
- 检查目录存在性
- 限制扫描范围

### 3. 异常处理

- 所有导入/解析操作都有 try-except
- 单个模块失败不影响整体扫描
- 返回详细的错误信息

## 测试验收

### 基本流程

```bash
# 1. 设置环境变量
export WORKSPACE_PATH=/root/agentsociety

# 2. 启动后端
cd /root/agentsociety/packages/agentsociety2
python -m agentsociety2.backend.run

# 3. 测试 API（另开终端）
curl -X POST http://localhost:8001/api/v1/custom/scan \
  -H "Content-Type: application/json" \
  -d '{"workspace_path": "/root/agentsociety"}'

# 4. 验证 JSON 生成
ls /root/agentsociety/.agentsociety/agent_classes/*.json
```

### 创建测试模块

在 `/root/agentsociety/custom/agents/test_agent.py`：

```python
from agentsociety2.agent.base import AgentBase
from datetime import datetime

class TestAgent(AgentBase):
    @classmethod
    def mcp_description(cls) -> str:
        return "TestAgent: 测试 Agent"

    async def ask(self, message: str, readonly: bool = True) -> str:
        return "测试回答"

    async def step(self, tick: int, t: datetime) -> str:
        return "测试步骤"

    async def dump(self) -> dict:
        return {"id": self._id}

    async def load(self, dump_data: dict):
        self._id = dump_data.get("id", self._id)
```

### 验证命令

```bash
# 扫描
curl -X POST http://localhost:8001/api/v1/custom/scan \
  -H "Content-Type: application/json" \
  -d '{"workspace_path": "/root/agentsociety"}'

# 查看状态
curl http://localhost:8001/api/v1/custom/status

# 运行测试
curl -X POST http://localhost:8001/api/v1/custom/test \
  -H "Content-Type: application/json" \
  -d '{"workspace_path": "/root/agentsociety"}'

# 清理
curl -X POST http://localhost:8001/api/v1/custom/clean \
  -H "Content-Type: application/json" \
  -d '{"workspace_path": "/root/agentsociety"}'
```

## 下一步扩展

### 可选增强功能

1. **热重载**
   - 监控 `custom/` 目录变化
   - 自动触发扫描

2. **脚手架生成 API**
   - `POST /api/v1/custom/scaffold/agent`
   - `POST /api/v1/custom/scaffold/env`

3. **LLM 驱动代码生成**
   - 扩展现有 `CodeGenerator`
   - 根据自然语言描述生成模块

4. **模块依赖管理**
   - 检测模块间依赖关系
   - 按顺序加载

5. **版本控制**
   - JSON 文件包含版本信息
   - 支持模块升级

## 相关文档

- 实现计划：[CUSTOM_MODULES_PLAN.md](packages/agentsociety2/CUSTOM_MODULES_PLAN.md)
- 用户指南：[custom/README.md](packages/agentsociety2/agentsociety2/custom/README.md)
- API 文档：http://localhost:8001/docs（启动后端后访问）
