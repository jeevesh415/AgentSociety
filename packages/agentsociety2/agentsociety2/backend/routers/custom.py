"""
自定义模块 API 路由

提供扫描、清理、测试自定义模块的 API 端点。
"""

from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
import os
import sys

# 添加工作区路径以确保可以导入自定义模块
workspace_path = os.getenv("WORKSPACE_PATH", "")
if workspace_path:
    workspace_abs_path = os.path.abspath(workspace_path)
    if workspace_abs_path not in sys.path:
        sys.path.insert(0, workspace_abs_path)

    agentsociety_path = os.path.join(workspace_abs_path, "packages/agentsociety2")
    if os.path.exists(agentsociety_path) and agentsociety_path not in sys.path:
        sys.path.insert(0, agentsociety_path)

from agentsociety2.backend.services.custom.scanner import CustomModuleScanner
from agentsociety2.backend.services.custom.generator import CustomModuleJsonGenerator
from agentsociety2.backend.services.custom.script_generator import ScriptGenerator


router = APIRouter(prefix="/api/v1/custom", tags=["custom"])


# ========== 请求/响应模型 ==========

class ScanRequest(BaseModel):
    """扫描请求"""
    workspace_path: Optional[str] = Field(None, description="工作区路径，不提供则使用环境变量")


class ScanResponse(BaseModel):
    """扫描响应"""
    success: bool
    agents_found: int
    envs_found: int
    agents_generated: int
    envs_generated: int
    errors: List[str]
    message: Optional[str] = None


class CleanResponse(BaseModel):
    """清理响应"""
    success: bool
    removed_count: int
    message: str


class TestRequest(BaseModel):
    """测试请求"""
    workspace_path: Optional[str] = Field(None, description="工作区路径，不提供则使用环境变量")


class TestResponse(BaseModel):
    """测试响应"""
    success: bool
    test_output: str
    test_file: Optional[str] = None
    error: Optional[str] = None
    returncode: Optional[int] = None


class ListResponse(BaseModel):
    """列表响应"""
    success: bool
    agents: List[Dict[str, Any]]
    envs: List[Dict[str, Any]]
    total_agents: int
    total_envs: int


# ========== API 端点 ==========

@router.post("/scan", response_model=ScanResponse)
async def scan_custom_modules(request: ScanRequest):
    """
    扫描自定义模块并生成 JSON 配置

    此接口会：
    1. 扫描 custom/agents/ 和 custom/envs/ 目录（跳过 examples/）
    2. 验证发现的模块
    3. 在 .agentsociety/ 目录生成对应的 JSON 文件
    4. 返回扫描结果
    """
    workspace_path = request.workspace_path or os.getenv("WORKSPACE_PATH")
    if not workspace_path:
        raise HTTPException(
            status_code=400,
            detail="Workspace path not provided. Set WORKSPACE_PATH env var or pass in request."
        )

    try:
        # 扫描自定义模块
        scanner = CustomModuleScanner(workspace_path)
        scan_result = scanner.scan_all()

        # 生成 JSON 配置文件
        generator = CustomModuleJsonGenerator(workspace_path)
        counts = generator.generate_all(scan_result)

        message_parts = []
        if counts["agents_generated"] > 0:
            message_parts.append(f"发现 {counts['agents_generated']} 个 Agent")
        if counts["envs_generated"] > 0:
            message_parts.append(f"发现 {counts['envs_generated']} 个环境模块")

        if not message_parts:
            message = "未发现任何自定义模块"
        else:
            message = "、".join(message_parts) + "，已生成 JSON 配置文件"

        return ScanResponse(
            success=True,
            agents_found=len(scan_result["agents"]),
            envs_found=len(scan_result["envs"]),
            agents_generated=counts["agents_generated"],
            envs_generated=counts["envs_generated"],
            errors=scan_result.get("errors", []),
            message=message
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"扫描失败: {str(e)}")


@router.post("/clean", response_model=CleanResponse)
async def clean_custom_modules(request: ScanRequest):
    """
    清理自定义模块的 JSON 配置

    删除所有标记为 is_custom=true 的 JSON 配置文件。
    """
    workspace_path = request.workspace_path or os.getenv("WORKSPACE_PATH")
    if not workspace_path:
        raise HTTPException(
            status_code=400,
            detail="Workspace path not provided. Set WORKSPACE_PATH env var or pass in request."
        )

    try:
        generator = CustomModuleJsonGenerator(workspace_path)
        count = generator.remove_custom_modules()

        return CleanResponse(
            success=True,
            removed_count=count,
            message=f"已清理 {count} 个自定义模块配置"
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"清理失败: {str(e)}")


@router.post("/test", response_model=TestResponse)
async def test_custom_modules(request: TestRequest):
    """
    生成并运行测试脚本

    此接口会：
    1. 扫描 custom/ 目录
    2. 生成 test_custom_module.py 测试脚本
    3. 自动运行测试
    4. 返回测试结果
    """
    workspace_path = request.workspace_path or os.getenv("WORKSPACE_PATH")
    if not workspace_path:
        raise HTTPException(
            status_code=400,
            detail="Workspace path not provided. Set WORKSPACE_PATH env var or pass in request."
        )

    try:
        # 先扫描模块
        scanner = CustomModuleScanner(workspace_path)
        scan_result = scanner.scan_all()

        if not scan_result["agents"] and not scan_result["envs"]:
            return TestResponse(
                success=False,
                test_output="",
                error="未发现任何自定义模块，请先在 custom/ 目录下创建模块"
            )

        # 生成并运行测试
        builder = ScriptGenerator(workspace_path)
        result = await builder.run_test(scan_result)

        output = result.get("stdout", "")
        stderr = result.get("stderr", "")
        if stderr:
            output = output + "\n--- 错误输出 ---\n" + stderr if output else stderr

        return TestResponse(
            success=result["success"],
            test_output=output,
            test_file=result.get("test_file"),
            error=result.get("error"),
            returncode=result.get("returncode")
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"测试失败: {str(e)}")


@router.get("/list", response_model=ListResponse)
async def list_custom_modules():
    """
    列出当前已注册的自定义模块

    返回所有 is_custom=true 的模块信息。
    """
    workspace_path = os.getenv("WORKSPACE_PATH")
    if not workspace_path:
        raise HTTPException(
            status_code=400,
            detail="Workspace path not set. Set WORKSPACE_PATH env var."
        )

    from pathlib import Path
    import json

    result = {
        "agents": [],
        "envs": []
    }

    agent_dir = Path(workspace_path) / ".agentsociety/agent_classes"
    env_dir = Path(workspace_path) / ".agentsociety/env_modules"

    # 读取自定义 Agent
    if agent_dir.exists():
        for json_file in agent_dir.glob("*.json"):
            try:
                with open(json_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    if data.get("is_custom"):
                        result["agents"].append(data)
            except Exception:
                pass

    # 读取自定义环境模块
    if env_dir.exists():
        for json_file in env_dir.glob("*.json"):
            try:
                with open(json_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    if data.get("is_custom"):
                        result["envs"].append(data)
            except Exception:
                pass

    return ListResponse(
        success=True,
        agents=result["agents"],
        envs=result["envs"],
        total_agents=len(result["agents"]),
        total_envs=len(result["envs"])
    )


@router.get("/status")
async def get_custom_modules_status():
    """
    获取自定义模块状态概览
    """
    workspace_path = os.getenv("WORKSPACE_PATH")
    if not workspace_path:
        raise HTTPException(
            status_code=400,
            detail="Workspace path not set"
        )

    from pathlib import Path

    custom_dir = Path(workspace_path) / "custom"
    agent_classes_dir = Path(workspace_path) / ".agentsociety/agent_classes"
    env_modules_dir = Path(workspace_path) / ".agentsociety/env_modules"

    status = {
        "custom_dir_exists": custom_dir.exists(),
        "agents_dir_exists": (custom_dir / "agents").exists(),
        "envs_dir_exists": (custom_dir / "envs").exists(),
        "agent_files_count": 0,
        "env_files_count": 0,
        "registered_agents": 0,
        "registered_envs": 0,
    }

    # 统计自定义代码文件
    if status["agents_dir_exists"]:
        status["agent_files_count"] = len([
            f for f in (custom_dir / "agents").rglob("*.py")
            if not f.name.startswith("__") and "examples" not in f.parts
        ])

    if status["envs_dir_exists"]:
        status["env_files_count"] = len([
            f for f in (custom_dir / "envs").rglob("*.py")
            if not f.name.startswith("__") and "examples" not in f.parts
        ])

    # 统计已注册的模块
    if agent_classes_dir.exists():
        for json_file in agent_classes_dir.glob("*.json"):
            try:
                import json
                with open(json_file, 'r') as f:
                    if json.load(f).get("is_custom"):
                        status["registered_agents"] += 1
            except Exception:
                pass

    if env_modules_dir.exists():
        for json_file in env_modules_dir.glob("*.json"):
            try:
                import json
                with open(json_file, 'r') as f:
                    if json.load(f).get("is_custom"):
                        status["registered_envs"] += 1
            except Exception:
                pass

    return status
