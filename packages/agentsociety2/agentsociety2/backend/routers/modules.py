"""Agent和Environment模块查询API路由"""

from __future__ import annotations

from fastapi import APIRouter
from typing import Dict, Any

from agentsociety2.mcp.registry import (
    REGISTERED_ENV_MODULES,
    REGISTERED_AGENT_MODULES,
)

router = APIRouter(prefix="/api/v1/modules", tags=["modules"])


@router.get("/agent_classes")
async def list_agent_classes() -> Dict[str, Any]:
    """
    获取所有已注册的Agent类列表

    Returns:
        包含agent类信息的字典
    """
    agents = {}

    for agent_type, agent_class in REGISTERED_AGENT_MODULES:
        try:
            description = agent_class.mcp_description()
        except Exception:
            description = f"{agent_class.__name__}: {agent_class.__doc__ or 'No description available'}"

        agents[agent_type] = {
            "type": agent_type,
            "class_name": agent_class.__name__,
            "description": description,
        }

    return {
        "success": True,
        "agents": agents,
        "count": len(agents),
    }


@router.get("/env_module_classes")
async def list_env_modules() -> Dict[str, Any]:
    """
    获取所有已注册的Environment模块类列表

    Returns:
        包含environment模块类信息的字典
    """
    modules = {}

    for module_type, env_class in REGISTERED_ENV_MODULES:
        try:
            description = env_class.mcp_description()
        except Exception:
            description = f"{env_class.__name__}: {env_class.__doc__ or 'No description available'}"

        modules[module_type] = {
            "type": module_type,
            "class_name": env_class.__name__,
            "description": description,
        }

    return {
        "success": True,
        "modules": modules,
        "count": len(modules),
    }
