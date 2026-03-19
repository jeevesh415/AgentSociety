"""
Modules API router

Provides endpoints for listing available agent classes and environment modules.
Supports both built-in modules and custom modules from the workspace.

关联文件：
- @extension/src/apiClient.ts - API客户端（调用getAgentClasses, getEnvModules）
- @extension/src/prefillParamsViewProvider.ts - 预填充参数查看器
- @extension/src/simSettingsEditorProvider.ts - SIM_SETTINGS编辑器
- @packages/agentsociety2/agentsociety2/registry/ - 模块注册表

API端点：
- GET /api/v1/modules/agent_classes - 获取所有可用的Agent类
- GET /api/v1/modules/env_module_classes - 获取所有可用的Environment模块类
- GET /api/v1/modules/refresh - 刷新模块列表（重新扫描）
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Dict, Any, List

from fastapi import APIRouter, Query, HTTPException

from agentsociety2.logger import get_logger
from agentsociety2.registry import (
    get_registry,
    get_registered_env_modules,
    get_registered_agent_modules,
    scan_and_register_custom_modules,
)

logger = get_logger()

router = APIRouter(prefix="/api/v1/modules", tags=["modules"])


def _get_workspace_path() -> str:
    """Get workspace path from environment variable"""
    workspace_path = os.getenv("WORKSPACE_PATH")
    if not workspace_path:
        raise HTTPException(
            status_code=400,
            detail="WORKSPACE_PATH environment variable not set",
        )
    return workspace_path


def _load_custom_modules_if_needed() -> None:
    """Load custom modules if workspace is configured"""
    try:
        workspace_path = os.getenv("WORKSPACE_PATH")
        if workspace_path:
            registry = get_registry()
            # Only scan if not already loaded
            if not registry._custom_loaded:
                scan_and_register_custom_modules(Path(workspace_path), registry)
    except Exception as e:
        logger.warning(f"Failed to load custom modules: {e}")


@router.get("/agent_classes")
async def get_agent_classes(
    include_custom: bool = Query(True, description="是否包含自定义模块")
) -> Dict[str, Any]:
    """
    获取所有可用的 Agent 类列表

    Returns:
        包含 Agent 类信息的字典
    """
    try:
        registry = get_registry()

        # 加载自定义模块（如果需要）
        if include_custom:
            _load_custom_modules_if_needed()

        # 获取所有已注册的 Agent 类
        agents = {}
        for agent_type, agent_class in get_registered_agent_modules():
            try:
                description = agent_class.mcp_description()
            except Exception:
                description = f"{agent_class.__name__}: {agent_class.__doc__ or 'No description available'}"

            agents[agent_type] = {
                "type": agent_type,
                "class_name": agent_class.__name__,
                "description": description,
                "is_custom": getattr(agent_class, "_is_custom", False),
            }

        return {
            "success": True,
            "agents": agents,
            "count": len(agents),
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get agent classes: {e}", exc_info=True)
        raise HTTPException(
            status_code=500, detail=f"Failed to get agent classes: {str(e)}"
        )


@router.get("/env_module_classes")
async def get_env_module_classes(
    include_custom: bool = Query(True, description="是否包含自定义模块")
) -> Dict[str, Any]:
    """
    获取所有可用的 Environment 模块类列表

    Returns:
        包含 Environment 模块类信息的字典
    """
    try:
        registry = get_registry()

        # 加载自定义模块（如果需要）
        if include_custom:
            _load_custom_modules_if_needed()

        # 获取所有已注册的 Environment 模块类
        env_modules = {}
        for module_type, env_class in get_registered_env_modules():
            try:
                description = env_class.mcp_description()
            except Exception:
                description = f"{env_class.__name__}: {env_class.__doc__ or 'No description available'}"

            env_modules[module_type] = {
                "type": module_type,
                "class_name": env_class.__name__,
                "description": description,
                "is_custom": getattr(env_class, "_is_custom", False),
            }

        return {
            "success": True,
            "modules": env_modules,
            "count": len(env_modules),
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get env module classes: {e}", exc_info=True)
        raise HTTPException(
            status_code=500, detail=f"Failed to get env module classes: {str(e)}"
        )


@router.get("/all")
async def get_all_modules(
    include_custom: bool = Query(True, description="是否包含自定义模块")
) -> Dict[str, Any]:
    """
    获取所有可用的 Agent 类和 Environment 模块类

    Returns:
        包含所有模块信息的字典
    """
    try:
        registry = get_registry()

        # 加载自定义模块（如果需要）
        if include_custom:
            _load_custom_modules_if_needed()

        # 获取 Agent 类
        agents = {}
        for agent_type, agent_class in get_registered_agent_modules():
            try:
                description = agent_class.mcp_description()
            except Exception:
                description = f"{agent_class.__name__}: {agent_class.__doc__ or 'No description available'}"

            agents[agent_type] = {
                "type": agent_type,
                "class_name": agent_class.__name__,
                "description": description,
                "is_custom": getattr(agent_class, "_is_custom", False),
            }

        # 获取 Environment 模块类
        env_modules = {}
        for module_type, env_class in get_registered_env_modules():
            try:
                description = env_class.mcp_description()
            except Exception:
                description = f"{env_class.__name__}: {env_class.__doc__ or 'No description available'}"

            env_modules[module_type] = {
                "type": module_type,
                "class_name": env_class.__name__,
                "description": description,
                "is_custom": getattr(env_class, "_is_custom", False),
            }

        return {
            "success": True,
            "agents": agents,
            "agent_count": len(agents),
            "env_modules": env_modules,
            "env_module_count": len(env_modules),
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get all modules: {e}", exc_info=True)
        raise HTTPException(
            status_code=500, detail=f"Failed to get all modules: {str(e)}"
        )
