# 🎭 AgentSociety Web UI

[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![Chainlit](https://img.shields.io/badge/framework-Chainlit-orange.svg)](https://chainlit.io)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

> 基于 Chainlit 的通用实验启动器 Web 界面，支持插件化扩展和丰富的交互式 UI 功能。

## ✨ 核心特性

### 🔌 插件化架构

- **声明式配置**：通过 `config.py` 零代码添加新实验
- **动态加载**：实验模块按需导入，节省内存
- **热重载支持**：开发模式下代码修改自动生效

### 🎨 丰富的 UI 交互

- **多种输入方式**：文本框、按钮选择、文件上传
- **多样化输出**：普通文本、代码块、图片、文件下载
- **实时流式输出**：支持长时间运行任务的进度展示
- **响应式设计**：完美适配桌面和移动设备

### 🛠️ 开发友好

- **适配器模式**：业务逻辑与 UI 框架完全解耦
- **类型提示**：完整的类型注解，IDE 友好
- **本地部署**：无需 pip install，复制即用
- **自动化构建**：启动脚本自动处理前端编译

---

## 🚀 快速开始

### 前置要求

- **Python 3.12+** （推荐 3.12）
- **Node.js 18+** + **pnpm**（仅首次构建需要）

### 一键启动

#### Windows

```powershell
.\start.ps1
```

#### Linux / macOS

```bash
chmod +x start.sh  # 首次需要添加执行权限
./start.sh
```

首次启动会自动：

1. 检查前端构建产物
2. 自动安装依赖（如需要）
3. 编译前端界面
4. 启动服务器

服务器将在 **`http://localhost:8000`** 启动并自动打开浏览器。

### 手动启动（可选）

#### Windows PowerShell

```powershell
# 设置 Python 路径
$env:PYTHONPATH = "chainlit_library\backend;$env:PYTHONPATH"

# 启动服务
python -m chainlit run app.py -w --host 0.0.0.0 --port 8000
```

#### Linux / macOS Bash

```bash
# 设置 Python 路径
export PYTHONPATH="chainlit_library/backend:$PYTHONPATH"

# 启动服务
python3 -m chainlit run app.py -w --host 0.0.0.0 --port 8000
```

---

## 🏗️ 架构设计

### 系统架构图

```text
┌─────────────────────────────────────────┐
│   Presentation Layer (前端)              │  React + WebSocket
│   ├─ 聊天消息流                          │
│   ├─ 交互式输入                          │
│   └─ 多媒体展示                          │
└──────────────┬──────────────────────────┘
               │ WebSocket (Socket.IO)
┌──────────────▼──────────────────────────┐
│   Application Layer (应用控制层)         │
│   app.py                                │
│   ├─ on_chat_start()   初始化会话       │
│   ├─ on_message()      路由命令          │
│   └─ run_experiment()  执行实验          │
└──────────────┬──────────────────────────┘
               │
┌──────────────▼──────────────────────────┐
│   Adapter Layer (I/O 适配层)             │
│   io_adapter.py                         │
│   ├─ print()           统一输出接口      │
│   ├─ input()           统一输入接口      │
│   ├─ ask_choices()     按钮选择          │
│   └─ send_file()       文件下载          │
└──────────────┬──────────────────────────┘
               │
┌──────────────▼──────────────────────────┐
│   Business Logic Layer (业务逻辑层)      │
│   demo_main.py, 其他实验模块...          │
│   └─ main(io)          实验入口函数      │
└──────────────┬──────────────────────────┘
               │
┌──────────────▼──────────────────────────┐
│   Configuration Layer (配置层)           │
│   config.py                             │
│   └─ EXPERIMENTS       实验注册表        │
└─────────────────────────────────────────┘
```

### 核心设计模式

#### 1. **适配器模式 (Adapter Pattern)**

- **目的**：解耦业务逻辑与 UI 框架
- **实现**：`io_adapter.py` 提供统一的 I/O 接口
- **优势**：业务代码可在不同环境（Web UI、命令行、测试）运行

#### 2. **插件化架构 (Plugin Architecture)**

- **目的**：零代码扩展功能
- **实现**：通过 `config.py` 声明式注册 + 动态导入
- **优势**：添加新实验无需修改核心代码

---

## 📚 API 文档

### ChainlitIOAdapter 类

#### 初始化参数

```python
ChainlitIOAdapter(
    message_author: str = "System",      # 消息发送者名称
    enable_streaming: bool = True,       # 是否启用流式输出
    buffer_size: int = 100,              # 输出缓冲区大小（行数）
    use_step: bool = True,               # 是否使用可折叠的 Step
    step_name: str = "Experiment Logs"   # Step 名称
)
```

#### 核心方法

##### 输出方法

| 方法                                                  | 参数                                             | 说明               | 示例                                     |
| ----------------------------------------------------- | ------------------------------------------------ | ------------------ | ---------------------------------------- |
| `print(*args, type="text", **kwargs)`                 | `type`: "text"\|"result"\|"code"\|"image"\|"log" | 通用输出方法       | `await io.print("Hello")`                |
| `print_text(*args, sep=" ", end="\n")`                | 标准 print 参数                                  | 输出普通文本       | `await io.print_text("Log", "Info")`     |
| `print_result(content: str)`                          | 结果文本                                         | 突出显示的结果消息 | `await io.print_result("✅ 完成")`        |
| `print_code(code: str, language="python")`            | 代码内容、语言                                   | 显示代码块         | `await io.print_code("x = 1", "python")` |
| `print_image(path: str, name="image", size="medium")` | 路径/URL、名称、尺寸                             | 显示图片           | `await io.print_image("https://...")`    |

##### 输入方法

| 方法                                                    | 参数                 | 返回值        | 说明         |
| ------------------------------------------------------- | -------------------- | ------------- | ------------ |
| `input(prompt: str, timeout=300)`                       | 提示文本、超时秒数   | `str`         | 获取文本输入 |
| `ask_choices(content: str, choices: list, timeout=300)` | 问题、选项列表、超时 | `str \| None` | 按钮选择     |

##### 文件方法

| 方法                                     | 参数               | 说明         |
| ---------------------------------------- | ------------------ | ------------ |
| `send_file(path: str, name: str = None)` | 文件路径、显示名称 | 提供文件下载 |

##### 生命周期方法

| 方法                 | 说明                   |
| -------------------- | ---------------------- |
| `async activate()`   | 激活适配器（自动调用） |
| `async deactivate()` | 清理资源（自动调用）   |

#### 使用示例

```python
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from io_adapter import ChainlitIOAdapter

async def my_experiment(io: "ChainlitIOAdapter"):
    """标准实验函数签名"""
    
    # 1. 输出欢迎消息
    await io.print("🚀 实验开始")
    
    # 2. 获取用户输入
    name = await io.input("请输入您的名字：")
    
    # 3. 按钮选择
    choice = await io.ask_choices(
        "选择一个选项：",
        ["选项 A", "选项 B", "选项 C"]
    )
    
    # 4. 显示代码
    await io.print_code("print('Hello World')", "python")
    
    # 5. 显示图片
    await io.print_image("https://example.com/image.png", name="示例图")
    
    # 6. 提供文件下载
    await io.send_file("report.txt", name="实验报告.txt")
    
    # 7. 显示结果
    await io.print_result(f"✅ 实验完成！{name} 选择了 {choice}")
```

---

## 📝 开发指南

### 添加新实验（3 步骤）

#### 步骤 1：编写实验代码

创建新文件 `my_experiment.py`：

```python
from typing import TYPE_CHECKING
import asyncio

if TYPE_CHECKING:
    from io_adapter import ChainlitIOAdapter

async def main(io: "ChainlitIOAdapter"):
    """实验主函数 - 必须命名为 main 并接收 io 参数"""
    
    await io.print("🎯 我的实验开始了！")
    
    # 获取用户输入
    param = await io.input("输入参数：")
    
    # 执行业务逻辑
    result = process_data(param)
    
    # 显示结果
    await io.print_result(f"结果：{result}")

def process_data(param: str) -> str:
    """业务逻辑函数"""
    return param.upper()
```

#### 步骤 2：注册实验

编辑 `config.py`：

```python
EXPERIMENTS = [
    # ... 现有实验 ...
    
    {
        "name": "我的实验",                    # 显示名称
        "commands": ["myexp", "me"],          # 触发命令（可多个）
        "module_path": "my_experiment",       # Python 模块名（不含.py）
        "function_name": "main",              # 入口函数名
        "description": "这是我的第一个实验"    # 描述信息
    }
]
```

#### 步骤 3：重启服务

```powershell
# 按 Ctrl+C 停止服务器
# 重新运行
.\start.ps1
```

✅ 完成！在 Web UI 中输入 `myexp` 即可运行。

---

### 自定义欢迎页面

编辑 `chainlit.md` 或 `zh-CN.md`：

```markdown
# 欢迎使用我的应用！

这里是应用说明...

## 功能特性
- 功能 1
- 功能 2
```

---

### 修改 UI 配置

编辑 `.chainlit/config.toml`：

```toml
[UI]
name = "我的应用名称"
default_theme = "dark"  # 或 "light"

[features]
latex = true            # 启用 LaTeX 数学公式
unsafe_allow_html = false  # 安全设置
```

---

## 📁 项目结构

```text
web_ui/
├── app.py                          # 主应用入口，路由控制器
├── config.py                       # 实验配置中心（插件注册表）
├── io_adapter.py                   # I/O 适配器核心实现
├── demo_main.py                    # UI 功能演示实验
├── start.ps1                       # Windows PowerShell 启动脚本
├── start.sh                        # Linux/macOS Bash 启动脚本
├── chainlit.md                     # 应用说明文档（默认语言）
├── zh-CN.md                        # 中文说明文档
│
├── .chainlit/                      # Chainlit 配置目录
│   ├── config.toml                 # UI 配置文件
│   └── translations/               # 多语言翻译文件
│
├── chainlit_library/               # 本地 Chainlit 库
│   ├── backend/                    # Python 后端
│   │   └── chainlit/               # Chainlit 源码
│   │       ├── __init__.py
│   │       ├── server.py           # FastAPI + Socket.IO 服务器
│   │       ├── message.py          # 消息类定义
│   │       └── ...
│   │
│   ├── frontend/                   # React 前端
│   │   ├── src/                    # TypeScript/React 源码
│   │   ├── dist/                   # 构建产物（启动时生成）
│   │   ├── package.json
│   │   └── vite.config.ts
│   │
│   └── libs/                       # 共享库
│       └── react-client/           # React 客户端库
│
└── public/                         # 静态资源
    ├── favicon.ico
    └── logo.svg
```
