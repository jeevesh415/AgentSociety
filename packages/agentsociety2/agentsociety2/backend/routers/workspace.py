from __future__ import annotations

import json
from pathlib import Path
import shutil
from typing import Dict, Any
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import aiohttp

from agentsociety2.mcp.registry import (
    REGISTERED_ENV_MODULES,
    REGISTERED_AGENT_MODULES,
)
from agentsociety2.logger import get_logger

logger = get_logger()

router = APIRouter(prefix="/api/v1/workspace", tags=["workspace"])


class InitWorkspaceRequest(BaseModel):
    workspace_path: str
    topic: str


WORKSPACE_PATH_MARKDOWN_CONTENT = """# Workspace Path Memory

This file records descriptions of high-value file paths and their meanings to help the Agent run with long-term memory.

## High-Value Files

- `TOPIC.md`: The core research topic and goals for the current simulation experiment. Always read this file first to understand your mission.
- `.agentsociety/agent_classes/*.json`: JSON files containing detailed information about all supported agent classes, including their types and capabilities.
- `.agentsociety/env_modules/*.json`: JSON files containing detailed information about all supported environment modules that can be used to build simulation worlds.

## Ignore Files

- `papers/`: The directory for storing literature search results or user-uploaded literature files. You SHOULD NOT read this directory directly, but use the `load_literature` tool to load the literature files.

## Progressive Context Loading

Instead of using specialized discovery tools, you should:
1. Read `.agentsociety/path.md` to understand the workspace structure.
2. List these directories to see available components.
3. Read specific JSON files as needed to gather detailed information about agent classes or environment modules.
"""


@router.post("/init")
async def init_workspace(request: InitWorkspaceRequest) -> Dict[str, Any]:
    """
    初始化工作区，创建必要的目录和文件以支持渐进式上下文加载
    """
    workspace_path = request.workspace_path
    if not workspace_path:
        raise HTTPException(status_code=400, detail="workspace_path is required")

    workspace_dir = Path(workspace_path).resolve()

    try:
        # 0. 创建 TOPIC.md, papers/, user_data/
        topic_file = workspace_dir / "TOPIC.md"
        topic_content = f"# Research Topic\n\n{request.topic}\n\n## Description\n\n[Describe your research topic here]\n\n## Hypotheses\n\n[Generated hypotheses will appear here]\n"
        with open(topic_file, "w", encoding="utf-8") as f:
            f.write(topic_content)

        (workspace_dir / "papers").mkdir(parents=True, exist_ok=True)
        (workspace_dir / "user_data").mkdir(parents=True, exist_ok=True)

        # 0.1 创建 custom/ 目录用于自定义 Agent 和环境模块
        custom_agents_dir = workspace_dir / "custom" / "agents"
        custom_envs_dir = workspace_dir / "custom" / "envs"
        custom_agents_dir.mkdir(parents=True, exist_ok=True)
        custom_envs_dir.mkdir(parents=True, exist_ok=True)

        # 复制自定义模块示例文件
        import agentsociety2 as pkg_module
        pkg_path = Path(pkg_module.__file__).parent
        custom_src_agents = pkg_path / "custom" / "agents"
        custom_src_envs = pkg_path / "custom" / "envs"

        # 复制 agents 示例
        if custom_src_agents.exists():
            examples_agents = custom_src_agents / "examples"
            if examples_agents.exists():
                for example_file in examples_agents.glob("*.py"):
                    shutil.copy2(example_file, custom_agents_dir / example_file.name)
                    logger.info(f"Copied agent example: {example_file.name}")

        # 复制 envs 示例
        if custom_src_envs.exists():
            examples_envs = custom_src_envs / "examples"
            if examples_envs.exists():
                for example_file in examples_envs.glob("*.py"):
                    shutil.copy2(example_file, custom_envs_dir / example_file.name)
                    logger.info(f"Copied env example: {example_file.name}")

        # 创建 custom/README.md
        custom_readme = workspace_dir / "custom" / "README.md"
        if not custom_readme.exists():
            custom_readme_content = """# Custom Modules

本目录用于存放自定义的 Agent 和环境模块。

## 目录结构

- `agents/` - 自定义 Agent 类
- `envs/` - 自定义环境模块

## 开发指南

1. 在 `agents/` 目录下创建自定义 Agent 类，继承自 `AgentBase`
2. 在 `envs/` 目录下创建自定义环境模块，继承自 `EnvBase`
3. 运行"扫描"命令注册模块
4. 运行"测试"命令验证模块功能

详细文档请参考项目文档。
"""
            with open(custom_readme, "w", encoding="utf-8") as f:
                f.write(custom_readme_content)

        # 1. 创建目录结构
        dot_agentsociety_dir = workspace_dir / ".agentsociety"
        if dot_agentsociety_dir.exists():
            # 如果存在，则删除
            shutil.rmtree(dot_agentsociety_dir)

        agents_dir = dot_agentsociety_dir / "agent_classes"
        env_dir = dot_agentsociety_dir / "env_modules"
        data_dir = dot_agentsociety_dir / "data"

        agents_dir.mkdir(parents=True, exist_ok=True)
        env_dir.mkdir(parents=True, exist_ok=True)
        data_dir.mkdir(parents=True, exist_ok=True)

        # 2. 创建 agent_classes/*.json
        for agent_type, agent_class in REGISTERED_AGENT_MODULES:
            try:
                # 尝试调用 mcp_description 获取描述
                if hasattr(agent_class, "mcp_description"):
                    description = agent_class.mcp_description()
                else:
                    description = agent_class.__doc__ or "No description available"
            except Exception as e:
                logger.warning(f"Error getting description for agent {agent_type}: {e}")
                description = agent_class.__doc__ or "No description available"

            agent_info = {
                "type": agent_type,
                "class_name": agent_class.__name__,
                "description": description,
            }

            with open(agents_dir / f"{agent_type}.json", "w", encoding="utf-8") as f:
                json.dump(agent_info, f, ensure_ascii=False, indent=2)

        # 3. 创建 env_modules/*.json
        for module_type, env_class in REGISTERED_ENV_MODULES:
            try:
                # 尝试调用 mcp_description 获取描述
                if hasattr(env_class, "mcp_description"):
                    description = env_class.mcp_description()
                else:
                    description = env_class.__doc__ or "No description available"
            except Exception as e:
                logger.warning(
                    f"Error getting description for env module {module_type}: {e}"
                )
                description = env_class.__doc__ or "No description available"

            module_info = {
                "type": module_type,
                "class_name": env_class.__name__,
                "description": description,
            }

            with open(env_dir / f"{module_type}.json", "w", encoding="utf-8") as f:
                json.dump(module_info, f, ensure_ascii=False, indent=2)

        # 4. 创建 .agentsociety/path.md
        with open(dot_agentsociety_dir / "path.md", "w", encoding="utf-8") as f:
            f.write(WORKSPACE_PATH_MARKDOWN_CONTENT)

        # 5. 下载地图文件到 .agentsociety/data
        map_url = "https://agentsociety.obs.cn-north-4.myhuaweicloud.com/data/map/beijing_map.pb"
        map_file_path = data_dir / "beijing_map.pb"

        try:
            logger.info(f"Downloading map file from {map_url}...")
            timeout = aiohttp.ClientTimeout(total=300)  # 5分钟超时
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(map_url) as response:
                    response.raise_for_status()

                    with open(map_file_path, "wb") as f:
                        async for chunk in response.content.iter_chunked(8192):
                            f.write(chunk)

            logger.info(f"Map file downloaded successfully to {map_file_path}")
        except Exception as e:
            logger.error(f"Failed to download map file: {e}", exc_info=True)
            # 不抛出异常，允许工作区初始化继续，但记录错误
            # 即使下载失败，也创建预填充参数文件，使用预期的路径

        # 6. 创建预填充参数文件
        prefill_file = dot_agentsociety_dir / "prefill_params.json"

        prefill_data = {
            "version": "1.0",
            "env_modules": {
                "mobility_space": {
                    "file_path": str(map_file_path.resolve()),
                    "home_dir": str(data_dir.resolve()),
                },
            },
            "agents": {},
        }

        with open(prefill_file, "w", encoding="utf-8") as f:
            json.dump(prefill_data, f, ensure_ascii=False, indent=2)
        logger.info(f"Prefill params file created at {prefill_file}")

        return {
            "success": True,
            "message": "Workspace initialized successfully",
            "data": {
                "workspace_path": str(workspace_dir),
                "files_created": [
                    "TOPIC.md",
                    "papers/",
                    "user_data/",
                    "custom/",
                    "custom/agents/",
                    "custom/envs/",
                    ".agentsociety/path.md",
                    ".agentsociety/agent_classes/*.json",
                    ".agentsociety/env_modules/*.json",
                    ".agentsociety/data/beijing_map.pb",
                    ".agentsociety/prefill_params.json",
                ],
            },
        }

    except Exception as e:
        logger.error(f"Failed to initialize workspace: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
