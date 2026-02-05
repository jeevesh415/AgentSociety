"""预填充参数查询API路由（只读）"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, Any, Literal

from fastapi import APIRouter, Query, HTTPException
from fastapi import Path as PathParam

from agentsociety2.mcp.registry import (
    REGISTERED_ENV_MODULES,
    REGISTERED_AGENT_MODULES,
)
from agentsociety2.logger import get_logger

logger = get_logger()

router = APIRouter(prefix="/api/v1/prefill-params", tags=["prefill-params"])


def _load_prefill_params_file(workspace_path: str) -> Dict[str, Any]:
    """加载全局预填充参数文件"""
    prefill_file = Path(workspace_path) / ".agentsociety" / "prefill_params.json"
    
    if not prefill_file.exists():
        return {
            "version": "1.0",
            "env_modules": {},
            "agents": {}
        }
    
    try:
        content = prefill_file.read_text(encoding="utf-8")
        return json.loads(content)
    except Exception as e:
        logger.error(f"Failed to load prefill params file: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to load prefill params file: {str(e)}"
        )


@router.get("")
async def get_prefill_params(
    workspace_path: str = Query(..., description="工作区路径")
) -> Dict[str, Any]:
    """
    获取全局预填充参数（所有类的配置）- 只读
    
    Returns:
        包含所有预填充参数的字典
    """
    try:
        prefill_params = _load_prefill_params_file(workspace_path)
        return {
            "success": True,
            "data": prefill_params
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get prefill params: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get prefill params: {str(e)}"
        )


@router.get("/{class_kind}/{class_name}")
async def get_class_prefill_params(
    class_kind: Literal["env_module", "agent"] = PathParam(..., description="类类型：env_module 或 agent"),
    class_name: str = PathParam(..., description="类名，如 mobility_space, basic_agent"),
    workspace_path: str = Query(..., description="工作区路径")
) -> Dict[str, Any]:
    """
    获取特定类的预填充参数 - 只读
    
    Args:
        workspace_path: 工作区路径
        class_kind: 类类型（env_module 或 agent）
        class_name: 类名
    
    Returns:
        包含特定类预填充参数的字典
    """
    try:
        prefill_params = _load_prefill_params_file(workspace_path)
        
        # 根据class_kind选择对应的键
        params_key = "env_modules" if class_kind == "env_module" else "agents"
        class_params = prefill_params.get(params_key, {}).get(class_name, {})
        
        return {
            "success": True,
            "class_kind": class_kind,
            "class_name": class_name,
            "params": class_params
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get class prefill params: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get class prefill params: {str(e)}"
        )


@router.get("/classes")
async def list_available_classes(
    workspace_path: str = Query(..., description="工作区路径")
) -> Dict[str, Any]:
    """
    列出所有可用的Agent类和Env Module类
    
    Returns:
        包含可用类列表的字典
    """
    try:
        # 获取所有已注册的Agent类
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
        
        # 获取所有已注册的Env Module类
        env_modules = {}
        for module_type, env_class in REGISTERED_ENV_MODULES:
            try:
                description = env_class.mcp_description()
            except Exception:
                description = f"{env_class.__name__}: {env_class.__doc__ or 'No description available'}"
            
            env_modules[module_type] = {
                "type": module_type,
                "class_name": env_class.__name__,
                "description": description,
            }
        
        # 加载预填充参数，标记哪些类已配置
        prefill_params = _load_prefill_params_file(workspace_path)
        env_prefill = prefill_params.get("env_modules", {})
        agent_prefill = prefill_params.get("agents", {})
        
        # 为每个类添加是否已配置的标记
        for module_type in env_modules:
            env_modules[module_type]["has_prefill"] = module_type in env_prefill and bool(env_prefill[module_type])
        
        for agent_type in agents:
            agents[agent_type]["has_prefill"] = agent_type in agent_prefill and bool(agent_prefill[agent_type])
        
        return {
            "success": True,
            "env_modules": env_modules,
            "agents": agents,
            "env_module_count": len(env_modules),
            "agent_count": len(agents),
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to list available classes: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to list available classes: {str(e)}"
        )
