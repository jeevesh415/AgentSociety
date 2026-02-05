# AgentSociety2 MCP Server

AgentSociety2 MCP Server 是一个基于 Model Context Protocol (MCP) 的服务器实现，用于管理和运行 AgentSociety 实例。它提供了通过 HTTP 协议访问的工具集，支持创建、运行、查询和干预多个 AgentSociety 仿真实例。

## 目录

- [概述](#概述)
- [架构设计](#架构设计)
- [快速开始](#快速开始)
- [核心组件](#核心组件)
- [API 工具说明](#api-工具说明)
- [数据模型](#数据模型)
- [注册表机制](#注册表机制)
- [客户端示例](#客户端示例)
- [使用说明](#使用说明)

## 概述

AgentSociety2 MCP Server 允许客户端通过标准化的 MCP 协议与 AgentSociety 仿真系统交互。服务器支持：

- **多实例管理**：同时管理多个独立的 AgentSociety 实例
- **异步执行**：支持长时间运行的仿真任务，通过状态轮询获取进度
- **模块化架构**：通过注册表机制动态注册环境模块和智能体类型
- **HTTP 传输**：使用 Streamable HTTP 协议，便于跨网络访问

## 架构设计

### 核心类

#### `AgentSocietyMCPServer`

MCP 服务器的主类，负责：

- 管理多个 `SocietyInstance` 实例
- 注册和管理 MCP 工具
- 处理客户端请求
- 提供 HTTP 传输支持

#### `SocietyInstance`

封装单个 AgentSociety 实例的包装类，包含：

- `instance_id`: 实例唯一标识符
- `society`: AgentSociety 对象
- `status`: 实例状态（idle/running/error）
- `run_task`: 异步运行任务

### 工作流程

```
客户端请求 → MCP Server → SocietyInstance → AgentSociety
                ↓
          工具注册表
                ↓
          环境模块/智能体注册表
```

## 快速开始

### 启动服务器

```bash
# 基本启动（默认 localhost:8000）
python -m agentsociety2.mcp.server

# 指定主机和端口
python -m agentsociety2.mcp.server --host 0.0.0.0 --port 8000 --path /mcp
```

### 客户端连接

```python
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

server_url = "http://localhost:8000/mcp"

async with streamablehttp_client(server_url) as (read_stream, write_stream, _):
    async with ClientSession(read_stream, write_stream) as session:
        await session.initialize()
        # 使用工具...
```

## 核心组件

### 1. Server 实现 (`server.py`)

#### 主要功能

- **实例管理**：创建、查询、关闭 AgentSociety 实例
- **异步执行**：支持后台运行仿真步骤
- **状态跟踪**：实时跟踪实例运行状态
- **错误处理**：完善的异常处理和清理机制

#### 关键方法

- `create_mcp_server()`: 创建服务器实例
- `_create_env_module()`: 从配置创建环境模块
- `_create_agent()`: 从配置创建智能体
- `cleanup_all_instances()`: 清理所有实例

### 2. 数据模型 (`models.py`)

定义了请求和响应的数据结构：

#### `EnvModuleInitConfig`

环境模块初始化配置：

```python
{
    "module_type": str,  # 模块类型（如 "global_information"）
    "args": Dict[str, Any]  # 模块构造参数
}
```

#### `AgentInitConfig`

智能体初始化配置：

```python
{
    "agent_type": str,  # 智能体类型（如 "do_nothing"）
    "agent_id": int,  # 智能体唯一 ID
    "args": Dict[str, Any]  # 智能体构造参数（包含 profile, memory_config 等）
}
```

#### `CreateInstanceRequest`

创建实例的完整请求：

```python
{
    "instance_id": str,  # 实例唯一标识
    "llm_config": Config,  # LLM 配置
    "env_modules": List[EnvModuleInitConfig],  # 环境模块列表
    "agents": List[AgentInitConfig],  # 智能体列表
    "fallback_module_index": int,  # 回退模块索引
    "start_t": datetime,  # 仿真开始时间
    "tick": int  # 时间步长（秒）
}
```

### 3. 注册表机制 (`registry.py`)

通过常量列表注册可用的环境模块和智能体类型：

#### `REGISTERED_ENV_MODULES`

环境模块注册表，格式：`List[Tuple[str, Type[EnvBase]]]`

当前注册的模块：
- `global_information`: GlobalInformationEnv
- `economy_space`: EconomySpace
- `social_space`: SocialSpace
- `mobility_space`: MobilitySpace

#### `REGISTERED_AGENT_MODULES`

智能体模块注册表，格式：`List[Tuple[str, Type[AgentBase]]]`

当前注册的智能体：
- `do_nothing`: DoNothingAgent

#### 添加新模块

在 `registry.py` 中导入并添加到相应列表：

```python
from agentsociety2.contrib.env.my_module import MyEnvModule

REGISTERED_ENV_MODULES.append(("my_module", MyEnvModule))
```

## API 工具说明

### 1. `list_environment_modules`

列出所有已注册的环境模块。

**返回**：
```python
{
    "success": bool,
    "modules": {
        "module_type": {
            "class_name": str,
            "description": str
        }
    },
    "count": int
}
```

### 2. `list_available_agents`

列出所有已注册的智能体类型。

**返回**：
```python
{
    "success": bool,
    "agents": {
        "agent_type": {
            "class_name": str,
            "description": str
        }
    },
    "count": int
}
```

### 3. `create_society_instance`

创建新的 AgentSociety 实例。

**参数**：
- `request`: `CreateInstanceRequest` 字典

**返回**：
```python
{
    "success": bool,
    "instance_id": str,  # 成功时
    "error": str  # 失败时
}
```

### 4. `get_instance_status`

获取实例状态（用于轮询异步操作进度）。

**参数**：
- `instance_id`: 实例 ID

**返回**：
```python
{
    "success": bool,
    "status": {
        "instance_id": str,
        "status": str,  # "idle" | "running" | "error"
        "current_time": str,  # ISO 格式时间
        "num_agents": int,
        "num_env_modules": int
    }
}
```

### 5. `list_instances`

列出所有实例及其状态。

**返回**：
```python
{
    "success": bool,
    "instances": List[StatusDict],
    "count": int
}
```

### 6. `run_instance`

运行实例指定步数（异步操作）。

**参数**：
- `instance_id`: 实例 ID
- `num_steps`: 运行步数（默认：1）
- `tick`: 时间步长（秒，可选）

**返回**：
```python
{
    "success": bool,
    "message": str,
    "instance_id": str,
    "num_steps": int,
    "tick": int
}
```

**注意**：此操作是异步的，需要使用 `get_instance_status` 轮询完成状态。

### 7. `ask_instance`

向实例提问（只读查询），仅在实例 idle 状态可用。

**参数**：
- `instance_id`: 实例 ID
- `question`: 问题文本

**返回**：
```python
{
    "success": bool,
    "answer": str
}
```

### 8. `intervene_instance`

干预实例（可修改状态），仅在实例 idle 状态可用。

**参数**：
- `instance_id`: 实例 ID
- `instruction`: 干预指令

**返回**：
```python
{
    "success": bool,
    "result": Any
}
```

### 9. `close_instance`

关闭并清理实例。

**参数**：
- `instance_id`: 实例 ID

**返回**：
```python
{
    "success": bool,
    "message": str
}
```

## 数据模型

### 状态管理

实例状态流转：

```
idle → running → idle
  ↓                ↓
error ←────────────┘
```

- **idle**: 空闲状态，可以运行、询问、干预
- **running**: 运行中，不能执行其他操作
- **error**: 错误状态，需要清理

### 时间管理

- `start_t`: 仿真开始时间（datetime）
- `tick`: 每次步进的时间增量（秒）
- `current_time`: 当前仿真时间（自动更新）

## 注册表机制

### 模块发现

服务器通过 `mcp_description()` 类方法获取模块信息：

```python
# 环境模块需要实现
@classmethod
def mcp_description(cls) -> str:
    """返回模块的 MCP 描述信息"""
    return "模块描述和参数说明"
```

### 模块描述格式

描述应包含：
- 模块功能说明
- 构造函数参数说明
- JSON Schema 格式的参数定义

## 客户端示例

### 完整生命周期示例

参考 `test_agentsociety_mcp_http.py` 中的 `test_full_lifecycle()` 函数：

1. **创建实例**
   ```python
   create_request = {
       "instance_id": "test-instance-001",
       "llm_config": {...},
       "env_modules": [...],
       "agents": [...],
       "fallback_module_index": 0,
       "start_t": datetime.now().isoformat(),
       "tick": 1
   }
   await session.call_tool("create_society_instance", 
                           arguments={"request": create_request})
   ```

2. **运行实例**
   ```python
   await session.call_tool("run_instance", 
                           arguments={"instance_id": "test-instance-001", 
                                     "num_steps": 2})
   ```

3. **轮询状态**
   ```python
   while True:
       status = await session.call_tool("get_instance_status",
                                        arguments={"instance_id": "test-instance-001"})
       if status["status"]["status"] == "idle":
           break
       await asyncio.sleep(1)
   ```

4. **询问实例**
   ```python
   await session.call_tool("ask_instance",
                           arguments={"instance_id": "test-instance-001",
                                     "question": "当前状态如何？"})
   ```

5. **关闭实例**
   ```python
   await session.call_tool("close_instance",
                           arguments={"instance_id": "test-instance-001"})
   ```

### 运行测试客户端

```bash
# 启动服务器（在另一个终端）
python -m agentsociety2.mcp.server --host localhost --port 8000

# 运行测试客户端
python test_agentsociety_mcp_http.py

# 或指定服务器 URL
python test_agentsociety_mcp_http.py --url http://localhost:8000/mcp
```

## 使用说明

### 环境要求

- Python 3.11+
- 已安装 `agentsociety2` 包及其依赖
- MCP 客户端库（用于客户端测试）

### 配置要求

创建实例时需要提供：

1. **LLM 配置**：包含模型列表和配置
2. **环境模块**：至少一个环境模块
3. **智能体**：至少一个智能体
4. **时间配置**：开始时间和时间步长

### 最佳实践

1. **实例 ID 命名**：使用唯一且可识别的命名（如时间戳）
2. **状态轮询**：运行长时间任务时，合理设置轮询间隔
3. **错误处理**：检查 `success` 字段并处理错误
4. **资源清理**：及时关闭不再使用的实例
5. **并发控制**：避免对同一实例同时执行多个操作

### 限制和注意事项

- `ask_instance` 和 `intervene_instance` 仅在实例 idle 状态可用
- `run_instance` 是异步操作，需要通过状态轮询获取完成状态
- 实例状态为 `running` 时，不能执行其他操作
- 服务器关闭时会自动清理所有实例

### 故障排查

1. **连接失败**：检查服务器是否启动，URL 是否正确
2. **实例创建失败**：检查配置参数是否正确，模块类型是否已注册
3. **运行失败**：检查实例状态，查看错误信息
4. **状态不同步**：使用 `get_instance_status` 刷新状态

## 扩展开发

### 添加新的环境模块

1. 在 `registry.py` 中导入模块类
2. 添加到 `REGISTERED_ENV_MODULES` 列表
3. 确保模块类实现 `mcp_description()` 方法

### 添加新的智能体类型

1. 在 `registry.py` 中导入智能体类
2. 添加到 `REGISTERED_AGENT_MODULES` 列表
3. 确保智能体类实现 `mcp_description()` 方法

### 自定义工具

在 `AgentSocietyMCPServer._register_tools()` 中添加新的工具装饰器：

```python
@self.mcp.tool()
async def my_custom_tool(param: str) -> Dict[str, Any]:
    """工具描述"""
    # 实现逻辑
    return {"success": True, "result": ...}
```

---

## 相关文件

- `server.py`: MCP 服务器主实现
- `models.py`: 数据模型定义
- `registry.py`: 模块注册表
- `test_agentsociety_mcp_http.py`: 客户端测试示例

