# AgentSociety2 自定义模块支持实现计划

## 概述

为 AgentSociety2 添加**自定义 Agent 和环境模块支持**功能，允许用户：
1. 在 `custom/` 目录编写自定义 Agent 和 EnvModule（只放用户代码）
2. **通过交互命令触发扫描和注册**（非自动）
3. 扫描后自动在 `.agentsociety` 目录生成对应的 JSON 配置
4. **一键测试功能** - 自动生成最简单的 `main.py` 来运行测试

## 目录结构设计

### 核心原则：分离用户代码和系统代码

```
packages/agentsociety2/agentsociety2/
├── custom/                          # 用户自定义代码目录（仅用户代码）
│   ├── README.md                    # 用户指南
│   ├── agents/                      # 用户自定义 Agent
│   │   ├── __init__.py
│   │   └── examples/                # 官方示例（供用户参考）
│   │       ├── simple_agent.py
│   │       └── advanced_agent.py
│   └── envs/                        # 用户自定义环境模块
│       ├── __init__.py
│       └── examples/                # 官方示例（供用户参考）
│           ├── simple_env.py
│           └── advanced_env.py
│
└── backend/                         # 后端服务（系统代码）
    └── services/
        └── custom/                  # 自定义模块服务（系统工具，不对用户暴露）
            ├── __init__.py
            ├── scanner.py           # 扫描服务
            ├── validator.py         # 代码验证
            ├── generator.py         # JSON 生成器
            └── test_builder.py      # 测试脚本生成器
```

### 用户实际使用时的目录

```
my_workspace/
├── custom/                          # 用户创建此目录
│   ├── agents/
│   │   └── my_agent.py             # 用户自己的 Agent
│   └── envs/
│       └── my_env.py               # 用户自己的环境模块
│
├── .agentsociety/                   # 自动生成
│   ├── agent_classes/
│   │   └── my_agent.json           # 扫描后自动生成
│   └── env_modules/
│       └── my_env.json             # 扫描后自动生成
│
└── test_custom_module.py            # 测试命令生成（自动生成）
```

## 一、用户交互机制

### API 端点

| 端点 | 方法 | 功能 |
|------|------|------|
| `/api/v1/custom/scan` | POST | 扫描自定义模块并生成 JSON 配置 |
| `/api/v1/custom/clean` | POST | 清理自定义模块的 JSON 配置 |
| `/api/v1/custom/test` | POST | **生成并运行测试脚本** |
| `/api/v1/custom/list` | GET | 列出当前已注册的自定义模块 |

### VSCode 命令

| 命令 ID | 功能 |
|---------|------|
| `agentsociety.scanCustomModules` | 扫描自定义模块 |
| `agentsociety.cleanCustomModules` | 清理自定义模块配置 |
| `agentsociety.testCustomModules` | **测试自定义模块** |

### 交互流程

```
┌─────────────────────────────────────────────────┐
│  1. 用户在 custom/ 目录创建代码                  │
│     custom/agents/my_agent.py                   │
└────────────────┬────────────────────────────────┘
                 │
                 ↓
┌─────────────────────────────────────────────────┐
│  2. 用户运行命令 "扫描自定义模块"               │
│     POST /api/v1/custom/scan                    │
└────────────────┬────────────────────────────────┘
                 │
                 ↓
┌─────────────────────────────────────────────────┐
│  3. 扫描结果                                    │
│     ✓ 发现 1 个 Agent                          │
│     ✓ 发现 1 个环境模块                        │
│     ✓ 生成 JSON 配置文件                       │
└────────────────┬────────────────────────────────┘
                 │
                 ↓
┌─────────────────────────────────────────────────┐
│  4. 用户运行命令 "测试自定义模块"               │
│     POST /api/v1/custom/test                    │
└────────────────┬────────────────────────────────┘
                 │
                 ↓
┌─────────────────────────────────────────────────┐
│  5. 系统自动生成 test_custom_module.py          │
│     并执行测试                                  │
└────────────────┬────────────────────────────────┘
                 │
                 ↓
┌─────────────────────────────────────────────────┐
│  6. 显示测试结果                                │
│     ✓ Agent 测试通过                           │
│     ✓ 环境模块测试通过                         │
│                                                │
│     [查看日志] [关闭]                           │
└─────────────────────────────────────────────────┘
```

## 二、核心实现

### 1. 扫描服务 (`backend/services/custom/scanner.py`)

```python
from pathlib import Path
from typing import List, Dict, Any
import importlib.util
import sys

class CustomModuleScanner:
    """自定义模块扫描服务"""

    def __init__(self, workspace_path: str):
        self.workspace_path = Path(workspace_path)
        self.custom_dir = self.workspace_path / "custom"

    def scan_all(self) -> Dict[str, Any]:
        """扫描所有自定义模块"""
        result = {
            "agents": [],
            "envs": [],
            "errors": []
        }

        # 扫描 Agent（跳过 examples 子目录）
        agents_dir = self.custom_dir / "agents"
        if agents_dir.exists():
            result["agents"] = self._scan_agents(agents_dir, skip_examples=True)

        # 扫描环境模块（跳过 examples 子目录）
        envs_dir = self.custom_dir / "envs"
        if envs_dir.exists():
            result["envs"] = self._scan_envs(envs_dir, skip_examples=True)

        return result

    def _scan_agents(self, agents_dir: Path, skip_examples: bool = True) -> List[Dict[str, Any]]:
        """扫描 Agent 目录"""
        agents = []

        for py_file in agents_dir.rglob("*.py"):
            # 跳过 __init__.py 和 examples 目录
            if py_file.name.startswith("__"):
                continue
            if skip_examples and "examples" in py_file.parts:
                continue

            try:
                agent_classes = self._extract_agent_classes(py_file)
                for cls in agent_classes:
                    agents.append({
                        "type": cls.__name__,
                        "class_name": cls.__name__,
                        "module_path": str(py_file.relative_to(self.workspace_path)),
                        "file_path": str(py_file),
                        "description": cls.mcp_description(),
                    })
            except Exception as e:
                # 记录错误但继续扫描
                pass

        return agents

    def _scan_envs(self, envs_dir: Path, skip_examples: bool = True) -> List[Dict[str, Any]]:
        """扫描环境模块目录"""
        envs = []

        for py_file in envs_dir.rglob("*.py"):
            # 跳过 __init__.py 和 examples 目录
            if py_file.name.startswith("__"):
                continue
            if skip_examples and "examples" in py_file.parts:
                continue

            try:
                env_classes = self._extract_env_classes(py_file)
                for cls in env_classes:
                    envs.append({
                        "type": cls.__name__,
                        "class_name": cls.__name__,
                        "module_path": str(py_file.relative_to(self.workspace_path)),
                        "file_path": str(py_file),
                        "description": cls.mcp_description(),
                    })
            except Exception as e:
                pass

        return envs

    def _extract_agent_classes(self, file_path: Path) -> List:
        """从文件中提取 Agent 类"""
        import inspect

        spec = importlib.util.spec_from_file_location("custom_module", file_path)
        if spec is None or spec.loader is None:
            return []

        module = importlib.util.module_from_spec(spec)
        sys.modules["custom_module"] = module
        spec.loader.exec_module(module)

        from agentsociety2.agent.base import AgentBase

        agents = []
        for name, obj in inspect.getmembers(module, inspect.isclass):
            if issubclass(obj, AgentBase) and obj is not AgentBase:
                if self._validate_agent_class(obj):
                    agents.append(obj)

        return agents

    def _extract_env_classes(self, file_path: Path) -> List:
        """从文件中提取环境模块类"""
        import inspect

        spec = importlib.util.spec_from_file_location("custom_module", file_path)
        if spec is None or spec.loader is None:
            return []

        module = importlib.util.module_from_spec(spec)
        sys.modules["custom_module"] = module
        spec.loader.exec_module(module)

        from agentsociety2.env.base import EnvBase

        envs = []
        for name, obj in inspect.getmembers(module, inspect.isclass):
            if issubclass(obj, EnvBase) and obj is not EnvBase:
                if self._validate_env_class(obj):
                    envs.append(obj)

        return envs

    def _validate_agent_class(self, cls) -> bool:
        """验证 Agent 类是否实现必需方法"""
        required_methods = ["ask", "step", "dump", "load", "mcp_description"]
        for method in required_methods:
            if not hasattr(cls, method):
                return False
        return True

    def _validate_env_class(self, cls) -> bool:
        """验证环境模块类是否有效"""
        required_methods = ["step", "mcp_description"]
        for method in required_methods:
            if not hasattr(cls, method):
                return False
        if not hasattr(cls, "_registered_tools"):
            return False
        return len(cls._registered_tools) > 0
```

### 2. JSON 配置生成器 (`backend/services/custom/generator.py`)

```python
import json
from pathlib import Path
from typing import Dict, Any

class CustomModuleJsonGenerator:
    """为自定义模块生成 .agentsociety JSON 配置文件"""

    def __init__(self, workspace_path: str):
        self.workspace_path = Path(workspace_path)
        self.agent_classes_dir = self.workspace_path / ".agentsociety/agent_classes"
        self.env_modules_dir = self.workspace_path / ".agentsociety/env_modules"

    def generate_all(self, scan_result: Dict[str, Any]) -> Dict[str, int]:
        """生成所有发现的模块的 JSON 文件"""
        counts = {
            "agents_generated": 0,
            "envs_generated": 0,
            "errors": 0
        }

        self.agent_classes_dir.mkdir(parents=True, exist_ok=True)
        self.env_modules_dir.mkdir(parents=True, exist_ok=True)

        for agent in scan_result.get("agents", []):
            if self._generate_agent_json(agent):
                counts["agents_generated"] += 1

        for env in scan_result.get("envs", []):
            if self._generate_env_json(env):
                counts["envs_generated"] += 1

        return counts

    def _generate_agent_json(self, agent_info: Dict[str, Any]) -> bool:
        """生成单个 Agent 的 JSON 文件"""
        try:
            file_path = self.agent_classes_dir / f"{agent_info['type'].lower()}.json"
            data = {
                "type": agent_info['type'],
                "class_name": agent_info['class_name'],
                "description": agent_info['description'],
                "is_custom": True,
                "module_path": agent_info.get('module_path', ''),
                "file_path": agent_info.get('file_path', ''),
            }

            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)

            return True
        except Exception as e:
            return False

    def _generate_env_json(self, env_info: Dict[str, Any]) -> bool:
        """生成单个环境模块的 JSON 文件"""
        try:
            file_path = self.env_modules_dir / f"{env_info['type'].lower()}.json"
            data = {
                "type": env_info['type'],
                "class_name": env_info['class_name'],
                "description": env_info['description'],
                "is_custom": True,
                "module_path": env_info.get('module_path', ''),
                "file_path": env_info.get('file_path', ''),
            }

            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)

            return True
        except Exception as e:
            return False

    def remove_custom_modules(self) -> int:
        """删除所有标记为自定义的 JSON 文件"""
        count = 0
        for json_file in self.agent_classes_dir.glob("*.json"):
            try:
                with open(json_file, 'r') as f:
                    data = json.load(f)
                    if data.get("is_custom"):
                        json_file.unlink()
                        count += 1
            except Exception:
                pass

        for json_file in self.env_modules_dir.glob("*.json"):
            try:
                with open(json_file, 'r') as f:
                    data = json.load(f)
                    if data.get("is_custom"):
                        json_file.unlink()
                        count += 1
            except Exception:
                pass

        return count
```

### 3. 测试脚本生成器 (`backend/services/custom/test_builder.py`)

```python
from pathlib import Path
from typing import List, Dict, Any
from datetime import datetime

class TestScriptBuilder:
    """自动生成测试脚本"""

    def __init__(self, workspace_path: str):
        self.workspace_path = Path(workspace_path)

    def build_test_script(self, scan_result: Dict[str, Any]) -> str:
        """生成测试脚本内容"""

        agents = scan_result.get("agents", [])
        envs = scan_result.get("envs", [])

        # 构建导入语句
        imports = []
        for agent in agents:
            module_path = agent['module_path'].replace('/', '.').replace('.py', '')
            imports.append(f"from {module_path} import {agent['class_name']}")

        for env in envs:
            module_path = env['module_path'].replace('/', '.').replace('.py', '')
            imports.append(f"from {module_path} import {env['class_name']}")

        # 构建测试代码
        script = f'''"""
自动生成的测试脚本
生成时间: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}

此脚本用于快速测试自定义模块的基本功能。
"""
import asyncio
import sys
from pathlib import Path

# 添加工作区到 Python 路径
workspace_path = Path("{self.workspace_path}")
sys.path.insert(0, str(workspace_path))
sys.path.insert(0, str(workspace_path / "packages/agentsociety2"))

{chr(10).join(imports)}

from agentsociety2.env.router_react import ReActRouter


async def test_agents():
    """测试自定义 Agent"""
    print("=" * 50)
    print("测试自定义 Agent")
    print("=" * 50)

'''

        # 添加 Agent 测试代码
        for i, agent in enumerate(agents):
            script += f'''
    # 测试 {agent['class_name']}
    print(f"\\n--- 测试 {agent['class_name']} ---")
    try:
        agent = {agent['class_name']}(
            id={i},
            profile={{"name": "测试用户", "personality": "友好"}}
        )
        print(f"✓ {agent['class_name']} 创建成功")

        # 测试基本方法
        if hasattr(agent, "mcp_description"):
            desc = agent.mcp_description()
            print(f"✓ mcp_description() 返回: {{len(desc)}} 字符")

        print(f"✓ {agent['class_name']} 基本测试通过\\n")
    except Exception as e:
        print(f"✗ {agent['class_name']} 测试失败: {{e}}\\n")
'''

        # 添加环境模块测试代码
        script += '''
async def test_envs():
    """测试自定义环境模块"""
    print("=" * 50)
    print("测试自定义环境模块")
    print("=" * 50)

'''

        for env in envs:
            script += f'''
    # 测试 {env['class_name']}
    print(f"\\n--- 测试 {env['class_name']} ---")
    try:
        env_module = {env['class_name']}()
        print(f"✓ {env['class_name']} 创建成功")

        # 测试工具注册
        if hasattr(env_module, "_registered_tools"):
            tools = env_module._registered_tools
            print(f"✓ 已注册 {{len(tools)}} 个工具:")
            for tool_name in tools.keys():
                print(f"  - {{tool_name}}")

        print(f"✓ {env['class_name']} 基本测试通过\\n")
    except Exception as e:
        print(f"✗ {env['class_name']} 测试失败: {{e}}\\n")
'''

        # 添加集成测试
        if agents and envs:
            script += '''
async def test_integration():
    """测试 Agent 与环境模块的集成"""
    print("=" * 50)
    print("测试集成（Agent + 环境模块）")
    print("=" * 50)

    try:
'''
            # 使用第一个 Agent 和第一个环境
            first_agent = agents[0]
            first_env = envs[0]

            script += f'''
        # 创建环境
        env = {first_env['class_name']}()
        router = ReActRouter([env])
        await router.init(datetime.now())
        print(f"✓ 环境初始化成功")

        # 创建 Agent
        agent = {first_agent['class_name']}(
            id=0,
            profile={{"name": "测试用户"}}
        )
        await agent.init(router)
        print(f"✓ Agent 初始化成功")

        # 运行一个仿真步骤
        print(f"\\n运行仿真步骤...")
        result = await agent.step(tick=60, t=datetime.now())
        print(f"✓ 仿真步骤执行成功")
        print(f"  结果: {{result[:100] if len(result) > 100 else result}}...")

        print(f"\\n✓ 集成测试通过\\n")

    except Exception as e:
        print(f"✗ 集成测试失败: {{e}}\\n")
        import traceback
        traceback.print_exc()
'''

        # 添加主函数
        script += '''
async def main():
    """主测试函数"""
    print("\\n" + "=" * 50)
    print("开始测试自定义模块")
    print("=" * 50 + "\\n")

    await test_agents()
    await test_envs()
'''

        if agents and envs:
            script += '    await test_integration()\n'

        script += '''
    print("=" * 50)
    print("测试完成！")
    print("=" * 50)


if __name__ == "__main__":
    asyncio.run(main())
'''

        return script

    def save_test_script(self, scan_result: Dict[str, Any]) -> str:
        """保存测试脚本到工作区"""
        script_content = self.build_test_script(scan_result)
        test_file = self.workspace_path / "test_custom_module.py"

        with open(test_file, 'w', encoding='utf-8') as f:
            f.write(script_content)

        return str(test_file)

    async def run_test(self, scan_result: Dict[str, Any]) -> Dict[str, Any]:
        """运行测试并返回结果"""
        import subprocess

        # 保存测试脚本
        test_file = self.save_test_script(scan_result)

        # 运行测试
        try:
            result = subprocess.run(
                [sys.executable, str(test_file)],
                capture_output=True,
                text=True,
                timeout=30,
                cwd=str(self.workspace_path)
            )

            return {
                "success": result.returncode == 0,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "test_file": str(test_file)
            }
        except subprocess.TimeoutExpired:
            return {
                "success": False,
                "error": "测试超时（30秒）",
                "test_file": str(test_file)
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "test_file": str(test_file)
            }
```

### 4. API 端点 (`backend/routers/custom.py`)

```python
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
import os
import sys

router = APIRouter(prefix="/api/v1/custom", tags=["custom"])

class ScanRequest(BaseModel):
    workspace_path: Optional[str] = None

class ScanResponse(BaseModel):
    success: bool
    agents_found: int
    envs_found: int
    agents_generated: int
    envs_generated: int
    errors: list[str]

class TestResponse(BaseModel):
    success: bool
    test_output: str
    test_file: Optional[str] = None
    error: Optional[str] = None

@router.post("/scan", response_model=ScanResponse)
async def scan_custom_modules(request: ScanRequest):
    """扫描自定义模块并生成 JSON 配置"""
    from agentsociety2.backend.services.custom.scanner import CustomModuleScanner
    from agentsociety2.backend.services.custom.generator import CustomModuleJsonGenerator

    workspace_path = request.workspace_path or os.getenv("WORKSPACE_PATH")
    if not workspace_path:
        raise HTTPException(status_code=400, detail="Workspace path not provided")

    try:
        scanner = CustomModuleScanner(workspace_path)
        scan_result = scanner.scan_all()

        generator = CustomModuleJsonGenerator(workspace_path)
        counts = generator.generate_all(scan_result)

        return ScanResponse(
            success=True,
            agents_found=len(scan_result["agents"]),
            envs_found=len(scan_result["envs"]),
            agents_generated=counts["agents_generated"],
            envs_generated=counts["envs_generated"],
            errors=scan_result.get("errors", []),
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/clean")
async def clean_custom_modules(request: ScanRequest):
    """清理自定义模块的 JSON 配置"""
    from agentsociety2.backend.services.custom.generator import CustomModuleJsonGenerator

    workspace_path = request.workspace_path or os.getenv("WORKSPACE_PATH")
    if not workspace_path:
        raise HTTPException(status_code=400, detail="Workspace path not provided")

    try:
        generator = CustomModuleJsonGenerator(workspace_path)
        count = generator.remove_custom_modules()

        return {
            "success": True,
            "removed_count": count,
            "message": f"已清理 {count} 个自定义模块配置"
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/test", response_model=TestResponse)
async def test_custom_modules(request: ScanRequest):
    """生成并运行测试脚本"""
    from agentsociety2.backend.services.custom.scanner import CustomModuleScanner
    from agentsociety2.backend.services.custom.test_builder import TestScriptBuilder

    workspace_path = request.workspace_path or os.getenv("WORKSPACE_PATH")
    if not workspace_path:
        raise HTTPException(status_code=400, detail="Workspace path not provided")

    try:
        # 先扫描模块
        scanner = CustomModuleScanner(workspace_path)
        scan_result = scanner.scan_all()

        if not scan_result["agents"] and not scan_result["envs"]:
            return TestResponse(
                success=False,
                test_output="",
                error="未发现任何自定义模块"
            )

        # 生成并运行测试
        builder = TestScriptBuilder(workspace_path)
        result = await builder.run_test(scan_result)

        return TestResponse(
            success=result["success"],
            test_output=result.get("stdout", ""),
            test_file=result.get("test_file"),
            error=result.get("stderr") or result.get("error")
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/list")
async def list_custom_modules():
    """列出当前已注册的自定义模块"""
    workspace_path = os.getenv("WORKSPACE_PATH")
    if not workspace_path:
        raise HTTPException(status_code=400, detail="Workspace path not set")

    from pathlib import Path
    import json

    result = {
        "agents": [],
        "envs": []
    }

    agent_dir = Path(workspace_path) / ".agentsociety/agent_classes"
    env_dir = Path(workspace_path) / ".agentsociety/env_modules"

    if agent_dir.exists():
        for json_file in agent_dir.glob("*.json"):
            try:
                with open(json_file, 'r') as f:
                    data = json.load(f)
                    if data.get("is_custom"):
                        result["agents"].append(data)
            except Exception:
                pass

    if env_dir.exists():
        for json_file in env_dir.glob("*.json"):
            try:
                with open(json_file, 'r') as f:
                    data = json.load(f)
                    if data.get("is_custom"):
                        result["envs"].append(data)
            except Exception:
                pass

    return result
```

## 三、用户使用流程

### 完整流程

```
1. 创建代码
   custom/agents/my_agent.py
   custom/envs/my_env.py

   ↓

2. 扫描注册
   VSCode 命令: "扫描自定义模块"
   或 API: POST /api/v1/custom/scan

   结果: 生成 .agentsociety/*.json

   ↓

3. 测试验证
   VSCode 命令: "测试自定义模块"
   或 API: POST /api/v1/custom/test

   结果: 生成 test_custom_module.py 并自动运行

   ↓

4. 查看结果
   - 测试通过 → 可以在 AI Social Scientist 中使用
   - 测试失败 → 查看日志修复代码

   ↓

5. 清理（可选）
   VSCode 命令: "清理自定义模块"
   或 API: POST /api/v1/custom/clean
```

### 生成的测试脚本示例

当用户运行"测试自定义模块"命令后，系统会生成 `test_custom_module.py`：

```python
"""
自动生成的测试脚本
生成时间: 2026-02-26 10:30:00

此脚本用于快速测试自定义模块的基本功能。
"""
import asyncio
import sys
from pathlib import Path
from datetime import datetime

workspace_path = Path("/root/my_workspace")
sys.path.insert(0, str(workspace_path))
sys.path.insert(0, str(workspace_path / "packages/agentsociety2"))

from custom.agents.my_agent import MyAgent
from custom.envs.my_env import MyEnv

from agentsociety2.env.router_react import ReActRouter


async def test_agents():
    """测试自定义 Agent"""
    print("=" * 50)
    print("测试自定义 Agent")
    print("=" * 50)

    # 测试 MyAgent
    print("\n--- 测试 MyAgent ---")
    try:
        agent = MyAgent(
            id=0,
            profile={"name": "测试用户", "personality": "友好"}
        )
        print("✓ MyAgent 创建成功")

        if hasattr(agent, "mcp_description"):
            desc = agent.mcp_description()
            print(f"✓ mcp_description() 返回: {len(desc)} 字符")

        print("✓ MyAgent 基本测试通过\n")
    except Exception as e:
        print(f"✗ MyAgent 测试失败: {e}\n")


async def test_envs():
    """测试自定义环境模块"""
    print("=" * 50)
    print("测试自定义环境模块")
    print("=" * 50)

    # 测试 MyEnv
    print("\n--- 测试 MyEnv ---")
    try:
        env_module = MyEnv()
        print("✓ MyEnv 创建成功")

        if hasattr(env_module, "_registered_tools"):
            tools = env_module._registered_tools
            print(f"✓ 已注册 {len(tools)} 个工具:")
            for tool_name in tools.keys():
                print(f"  - {tool_name}")

        print("✓ MyEnv 基本测试通过\n")
    except Exception as e:
        print(f"✗ MyEnv 测试失败: {e}\n")


async def test_integration():
    """测试 Agent 与环境模块的集成"""
    print("=" * 50)
    print("测试集成（Agent + 环境模块）")
    print("=" * 50)

    try:
        # 创建环境
        env = MyEnv()
        router = ReActRouter([env])
        await router.init(datetime.now())
        print("✓ 环境初始化成功")

        # 创建 Agent
        agent = MyAgent(
            id=0,
            profile={"name": "测试用户"}
        )
        await agent.init(router)
        print("✓ Agent 初始化成功")

        # 运行一个仿真步骤
        print("\n运行仿真步骤...")
        result = await agent.step(tick=60, t=datetime.now())
        print("✓ 仿真步骤执行成功")
        print(f"  结果: {result[:100] if len(result) > 100 else result}...")

        print("\n✓ 集成测试通过\n")

    except Exception as e:
        print(f"✗ 集成测试失败: {e}\n")
        import traceback
        traceback.print_exc()


async def main():
    """主测试函数"""
    print("\n" + "=" * 50)
    print("开始测试自定义模块")
    print("=" * 50 + "\n")

    await test_agents()
    await test_envs()
    await test_integration()

    print("=" * 50)
    print("测试完成！")
    print("=" * 50)


if __name__ == "__main__":
    asyncio.run(main())
```

## 四、文件清单

### 新建文件（12 个）

| 文件路径 | 优先级 | 说明 |
|---------|--------|------|
| `custom/__init__.py` | P0 | 用户自定义代码包 |
| `custom/agents/__init__.py` | P0 | Agent 包 |
| `custom/agents/examples/simple_agent.py` | P1 | 简单 Agent 示例 |
| `custom/agents/examples/advanced_agent.py` | P1 | 高级 Agent 示例 |
| `custom/envs/__init__.py` | P0 | 环境模块包 |
| `custom/envs/examples/simple_env.py` | P1 | 简单环境示例 |
| `custom/envs/examples/advanced_env.py` | P1 | 高级环境示例 |
| `custom/README.md` | P1 | 用户指南 |
| `backend/services/custom/__init__.py` | P0 | 服务包 |
| `backend/services/custom/scanner.py` | P0 | 扫描服务 |
| `backend/services/custom/generator.py` | P0 | JSON 生成器 |
| `backend/services/custom/test_builder.py` | P1 | 测试脚本生成器 |

### 修改文件（3 个）

| 文件路径 | 修改内容 |
|---------|---------|
| `backend/routers/custom.py` | 新增自定义模块 API 路由 |
| `backend/app.py` | 注册 custom 路由 |
| `.env.example` | 添加 WORKSPACE_PATH 配置 |

## 五、关键设计说明

### 1. 目录分离原则

- **`custom/` 目录** - 只放用户代码和官方示例
- **`backend/services/custom/` 目录** - 系统工具代码，用户不可见

这样用户打开 `custom/` 目录时，只会看到：
- 官方示例（`examples/`）
- 自己创建的代码

不会被系统实现细节干扰。

### 2. 测试脚本设计

- **自动生成** - 根据扫描到的模块自动生成
- **独立可运行** - 生成的 `test_custom_module.py` 可以独立运行
- **完整测试** - 包含单元测试和集成测试
- **30秒超时** - 防止测试卡死

### 3. 跳过示例目录

扫描时自动跳过 `examples/` 子目录：
- 避免将官方示例注册为用户模块
- 保持 `.agentsociety` 目录整洁

### 4. 工作区路径配置

支持两种方式：
1. 环境变量 `WORKSPACE_PATH`
2. API 请求参数 `workspace_path`

## 六、VSCode 插件集成

### 新增命令

```typescript
"commands": [
  {
    "command": "agentsociety.scanCustomModules",
    "title": "扫描自定义模块",
    "category": "AgentSociety"
  },
  {
    "command": "agentsociety.cleanCustomModules",
    "title": "清理自定义模块",
    "category": "AgentSociety"
  },
  {
    "command": "agentsociety.testCustomModules",
    "title": "测试自定义模块",
    "category": "AgentSociety"
  }
]
```

### 侧边栏按钮组

```typescript
{
  "type": "button-group",
  "buttons": [
    {
      "text": "$(refresh) 扫描",
      "command": "agentsociety.scanCustomModules",
      "tooltip": "扫描 custom/ 目录中的自定义模块"
    },
    {
      "text": "$(play) 测试",
      "command": "agentsociety.testCustomModules",
      "tooltip": "生成并运行测试脚本"
    },
    {
      "text": "$(trash) 清理",
      "command": "agentsociety.cleanCustomModules",
      "tooltip": "清理自定义模块的注册配置"
    }
  ]
}
```

### 测试结果显示

```typescript
async function testCustomModules() {
  const result = await axios.post('/api/v1/custom/test');

  if (result.success) {
    // 显示测试输出
    const panel = vscode.window.createWebviewPanel(
      'testResults',
      '测试结果',
      vscode.ViewColumn.One
    );
    panel.webview.html = `
      <html>
      <body>
        <h1>测试结果</h1>
        <pre>${result.test_output}</pre>
        <p>测试脚本: ${result.test_file}</p>
      </body>
      </html>
    `;
  } else {
    vscode.window.showErrorMessage(`测试失败: ${result.error}`);
  }
}
```

## 七、用户文档示例 (`custom/README.md`)

```markdown
# 自定义模块开发指南

## 目录结构

```
custom/
├── agents/          # 放置你的自定义 Agent
│   └── my_agent.py
└── envs/            # 放置你的自定义环境模块
    └── my_env.py
```

## 创建自定义 Agent

1. 在 `custom/agents/` 创建新的 `.py` 文件
2. 继承 `AgentBase` 类
3. 实现必需方法：
   - `ask()` - 回答问题
   - `step()` - 执行仿真步骤
   - `dump()` - 序列化状态
   - `load()` - 反序列化状态
   - `mcp_description()` - 模块描述

## 创建自定义环境模块

1. 在 `custom/envs/` 创建新的 `.py` 文件
2. 继承 `EnvBase` 类
3. 使用 `@tool()` 装饰器注册工具方法
4. 实现 `step()` 方法

## 工作流程

1. **创建代码** - 在 `custom/` 目录编写代码
2. **扫描注册** - 运行 VSCode 命令 "扫描自定义模块"
3. **测试验证** - 运行 VSCode 命令 "测试自定义模块"
4. **开始使用** - 在 AI Social Scientist 中选择使用

## 示例

查看 `custom/agents/examples/` 和 `custom/envs/examples/` 获取示例代码。
```

## 八、实施步骤

### Phase 1: 基础设施
1. 创建目录结构
2. 实现扫描服务
3. 实现 JSON 生成器
4. 实现 API 端点（扫描、清理）

### Phase 2: 测试功能
5. 实现测试脚本生成器
6. 实现测试 API 端点
7. 创建示例代码

### Phase 3: VSCode 集成
8. 添加 VSCode 命令
9. 添加侧边栏按钮
10. 实现测试结果显示

### Phase 4: 文档和测试
11. 编写用户文档
12. 编写系统测试
