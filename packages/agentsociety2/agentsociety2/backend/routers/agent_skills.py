"""
Agent Skills API 路由

提供 agent skill 的列表、启用/禁用、扫描自定义 skill、导入 skill 的 API 端点。

关联文件：
- @packages/agentsociety2/agentsociety2/agent/skills/__init__.py - Skill 注册表
- @extension/src/apiClient.ts - 前端 API 客户端

API 端点：
- GET  /api/v1/agent-skills/list    — 列出所有 agent skill（builtin + custom）
- POST /api/v1/agent-skills/enable  — 启用指定 skill
- POST /api/v1/agent-skills/disable — 禁用指定 skill
- POST /api/v1/agent-skills/scan    — 扫描 workspace/custom/skills/ 下的自定义 skill
- POST /api/v1/agent-skills/import  — 从路径导入 skill 目录
- POST /api/v1/agent-skills/reload  — 热重载指定 skill
- GET  /api/v1/agent-skills/{name}/info — 获取 SKILL.md 内容
"""

from __future__ import annotations

import os
import shutil
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from agentsociety2.agent.skills import get_skill_registry
from agentsociety2.logger import get_logger

logger = get_logger()

router = APIRouter(prefix="/api/v1/agent-skills", tags=["agent-skills"])


# ── 请求/响应模型 ──


class SkillItem(BaseModel):
    name: str
    priority: int
    source: str
    enabled: bool
    path: str
    has_skill_md: bool


class ListResponse(BaseModel):
    success: bool
    skills: list[SkillItem]
    total: int


class NameRequest(BaseModel):
    name: str = Field(..., description="skill 名称")


class ScanRequest(BaseModel):
    workspace_path: str | None = Field(None, description="工作区路径")


class ScanResponse(BaseModel):
    success: bool
    new_skills: list[str]
    total: int
    message: str


class ImportRequest(BaseModel):
    source_path: str = Field(..., description="skill 目录的绝对路径")
    workspace_path: str | None = Field(None, description="工作区路径")


class ImportResponse(BaseModel):
    success: bool
    name: str
    message: str


class SimpleResponse(BaseModel):
    success: bool
    message: str


# ── API 端点 ──


@router.get("/list", response_model=ListResponse)
async def list_skills():
    """
    列出所有已发现的Agent Skill

    返回系统中所有已注册的Agent Skill，包括内置和自定义技能。

    Returns:
        ListResponse: Skill列表，包含：
            - success: 是否成功
            - skills: Skill列表，每个Skill包含：
                - name: Skill名称
                - priority: 优先级
                - source: 来源 (builtin/custom)
                - enabled: 是否启用
                - path: Skill路径
                - has_skill_md: 是否有SKILL.md文档
            - total: Skill总数
    """
    from pathlib import Path as PathLib

    reg = get_skill_registry()
    _ensure_custom_scanned(reg)

    items = [
        SkillItem(
            name=s.name,
            priority=s.priority,
            source=s.source,
            enabled=s.enabled,
            path=s.path,
            has_skill_md=(
                PathLib(s.path) / "SKILL.md"
            ).exists(),
        )
        for s in reg.list_all()
    ]
    return ListResponse(success=True, skills=items, total=len(items))


@router.post("/enable", response_model=SimpleResponse)
async def enable_skill(req: NameRequest):
    """
    启用指定的Agent Skill

    Args:
        req: 请求体，包含：
            - name: Skill名称

    Returns:
        SimpleResponse: 操作结果，包含：
            - success: 是否成功
            - message: 结果消息

    Raises:
        HTTPException: 404 - Skill不存在
    """
    reg = get_skill_registry()
    if reg.enable(req.name):
        logger.info(f"[Skills] Enabled: {req.name}")
        return SimpleResponse(success=True, message=f"Skill '{req.name}' enabled")
    raise HTTPException(404, f"Skill '{req.name}' not found")


@router.post("/disable", response_model=SimpleResponse)
async def disable_skill(req: NameRequest):
    """
    禁用指定的Agent Skill

    Args:
        req: 请求体，包含：
            - name: Skill名称

    Returns:
        SimpleResponse: 操作结果，包含：
            - success: 是否成功
            - message: 结果消息

    Raises:
        HTTPException: 404 - Skill不存在
    """
    reg = get_skill_registry()
    if reg.disable(req.name):
        logger.info(f"[Skills] Disabled: {req.name}")
        return SimpleResponse(success=True, message=f"Skill '{req.name}' disabled")
    raise HTTPException(404, f"Skill '{req.name}' not found")


@router.post("/scan", response_model=ScanResponse)
async def scan_custom_skills(req: ScanRequest):
    """
    扫描工作区的自定义Agent Skill

    扫描 {workspace}/custom/skills/ 目录下尚未注册的Skill。

    Args:
        req: 扫描请求，包含：
            - workspace_path: 工作区路径（可选，不提供则使用环境变量）

    Returns:
        ScanResponse: 扫描结果，包含：
            - success: 是否成功
            - new_skills: 新发现的Skill名称列表
            - total: Skill总数
            - message: 结果消息

    Raises:
        HTTPException: 400 - 未提供工作区路径
    """
    workspace = req.workspace_path or os.getenv("WORKSPACE_PATH")
    if not workspace:
        raise HTTPException(
            400, "workspace_path not provided and WORKSPACE_PATH not set"
        )

    reg = get_skill_registry()
    new_names = reg.scan_custom(workspace)

    return ScanResponse(
        success=True,
        new_skills=new_names,
        total=len(reg.list_all()),
        message=f"发现 {len(new_names)} 个新 skill" if new_names else "未发现新 skill",
    )


@router.post("/import", response_model=ImportResponse)
async def import_skill(req: ImportRequest):
    """
    从外部路径导入Agent Skill

    将指定目录复制到工作区的 custom/skills/ 目录下。

    Args:
        req: 导入请求，包含：
            - source_path: Skill目录的绝对路径
            - workspace_path: 工作区路径（可选）

    Returns:
        ImportResponse: 导入结果，包含：
            - success: 是否成功
            - name: Skill名称（目录名）
            - message: 结果消息

    Raises:
        HTTPException: 400 - 源路径不是目录或不是有效的Skill目录
        HTTPException: 400 - 未提供工作区路径

    Note:
        Skill目录需要包含 SKILL.md 文件或 scripts/ 目录。
        如果目标目录已存在，将被覆盖。
    """
    source = Path(req.source_path)
    if not source.is_dir():
        raise HTTPException(400, f"Source path is not a directory: {source}")

    if not (source / "SKILL.md").exists() and not (source / "scripts").is_dir():
        raise HTTPException(
            400, "Directory does not look like a skill (missing SKILL.md and scripts/)"
        )

    workspace = req.workspace_path or os.getenv("WORKSPACE_PATH")
    if not workspace:
        raise HTTPException(
            400, "workspace_path not provided and WORKSPACE_PATH not set"
        )

    dest = Path(workspace) / "custom" / "skills" / source.name
    if dest.exists():
        shutil.rmtree(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(str(source), str(dest))

    # 重新扫描
    reg = get_skill_registry()
    reg.scan_custom(workspace)

    logger.info(f"[Skills] Imported skill '{source.name}' from {source} → {dest}")
    return ImportResponse(
        success=True,
        name=source.name,
        message=f"Skill '{source.name}' imported to {dest}",
    )


@router.post("/reload", response_model=SimpleResponse)
async def reload_skill(req: NameRequest):
    """
    热重载指定的Agent Skill

    重新导入Skill的Python模块，用于开发时快速迭代。

    Args:
        req: 重载请求，包含：
            - name: Skill名称

    Returns:
        SimpleResponse: 重载结果，包含：
            - success: 是否成功
            - message: 结果消息

    Raises:
        HTTPException: 404 - Skill不存在或重载失败
    """
    reg = get_skill_registry()
    if reg.reload_skill(req.name):
        logger.info(f"[Skills] Reloaded: {req.name}")
        return SimpleResponse(success=True, message=f"Skill '{req.name}' reloaded")
    raise HTTPException(404, f"Skill '{req.name}' not found or reload failed")


@router.get("/{name}/info")
async def get_skill_info(name: str) -> dict[str, Any]:
    """
    获取Agent Skill的详细信息

    返回Skill的SKILL.md内容和元数据。这是一个按需加载的API，
    只有调用此API时才会加载完整的skill_md内容。

    Args:
        name: Skill名称

    Returns:
        dict[str, Any]: Skill详细信息，包含：
            - success: 是否成功
            - name: Skill名称
            - priority: 优先级
            - source: 来源 (builtin/custom)
            - enabled: 是否启用
            - path: Skill路径
            - skill_md: SKILL.md文档内容

    Raises:
        HTTPException: 404 - Skill不存在
    """
    reg = get_skill_registry()
    info = reg.get_skill_info(name)

    if not info:
        raise HTTPException(404, f"Skill '{name}' not found")

    return {
        "success": True,
        "name": info.name,
        "priority": info.priority,
        "source": info.source,
        "enabled": info.enabled,
        "path": info.path,
        "skill_md": info.skill_md,
    }


@router.post("/remove", response_model=SimpleResponse)
async def remove_custom_skill(req: NameRequest):
    """
        移除自定义Agent Skill

        删除自定义Skill的目录并从注册表中移除。仅限source为custom的Skill。

        Args:
            req: 移除请求，包含：
                - name: Skill名称

        Returns:
            SimpleResponse: 移除结果，包含：
                - success: 是否成功
                - message: 结果消息

        Raises:
            HTTPException: 404 - Skill不存在
            HTTPException: 400 - 不能删除内置Skill

    Note:
            此操作不可逆，会删除Skill目录下的所有文件。
    """
    reg = get_skill_registry()
    info_dict = {s.name: s for s in reg.list_all()}
    info = info_dict.get(req.name)

    if not info:
        raise HTTPException(404, f"Skill '{req.name}' not found")
    if info.source != "custom":
        raise HTTPException(400, f"Cannot remove builtin skill '{req.name}'")

    # 删除文件
    skill_path = Path(info.path)
    if skill_path.exists():
        shutil.rmtree(skill_path)

    reg.remove_custom(req.name)
    logger.info(f"[Skills] Removed custom skill: {req.name}")
    return SimpleResponse(success=True, message=f"Custom skill '{req.name}' removed")


# ── 辅助函数 ──


def _ensure_custom_scanned(reg) -> None:
    """确保 custom skills 已扫描"""
    workspace = os.getenv("WORKSPACE_PATH")
    if workspace:
        reg.scan_custom(workspace)
