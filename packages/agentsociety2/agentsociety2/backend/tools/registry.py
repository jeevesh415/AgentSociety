"""工具注册表"""

from __future__ import annotations

import os
from typing import Dict, List, Optional
from openai.types.chat import ChatCompletionToolParam
from agentsociety2.backend.tools.base import BaseTool
from agentsociety2.backend.tools.literature_search import LiteratureSearchTool
from agentsociety2.backend.tools.load_literature import LoadLiteratureTool
from agentsociety2.backend.tools.experiment_config import (
    ExperimentConfigTool,
)
from agentsociety2.backend.tools.run_experiment import RunExperimentTool
from agentsociety2.backend.tools.run_shell_command import RunShellCommandTool
from agentsociety2.backend.tools.file_system import (
    ListDirectoryTool,
    ReadFileTool,
    WriteFileTool,
    GlobTool,
    SearchFileContentTool,
    ReplaceTool,
)
from agentsociety2.backend.tools.write_todo import WriteTodoTool
from agentsociety2.backend.tools.hypothesis import HypothesisTool
from agentsociety2.backend.tools.data_analysis import DataAnalysisTool
from agentsociety2.backend.tools.analysis_workspace import SynthesizeExperimentsTool
from agentsociety2.backend.tools.generate_paper import GeneratePaperTool
from agentsociety2.logger import get_logger

logger = get_logger()


# 如果设置了 WEB_SEARCH_API_URL 和 WEB_SEARCH_API_TOKEN 环境变量，则尝试导入和注册
def _should_enable_mirothinker() -> bool:
    """检查是否应该启用 Miro Web Research（外部 MCP）"""
    mcp_url = os.environ.get("WEB_SEARCH_API_URL")
    mcp_token = os.environ.get("WEB_SEARCH_API_TOKEN")
    return (
        mcp_url is not None
        and mcp_url.strip() != ""
        and mcp_token is not None
        and mcp_token.strip() != ""
    )


def _try_import_mirothinker():
    """尝试导入 Miro Web Research 工具"""
    try:
        from agentsociety2.backend.tools.miro_web_research import MiroWebResearchTool

        return MiroWebResearchTool
    except ImportError as e:
        logger.warning(
            "Miro Web Research（外部 MCP）不可用（可选功能）。"
            "如需使用，请配置 WEB_SEARCH_API_URL 并确保依赖已安装。"
            f"错误: {e}"
        )
        return None


class ToolRegistry:
    """工具注册表"""

    def __init__(self):
        self._tool_classes: Dict[str, type] = {}
        self._default_tools: Dict[str, BaseTool] = {}  # 用于获取schema
        self._register_default_tools()

    def _register_default_tools(self):
        """注册默认工具"""

        async def empty_progress_callback(tool_event):
            """空的进度回调函数，用于默认实例"""
            pass

        tool_classes = [
            LiteratureSearchTool,
            LoadLiteratureTool,
            ExperimentConfigTool,
            RunExperimentTool,
            RunShellCommandTool,
            # 文件系统工具
            ListDirectoryTool,
            ReadFileTool,
            WriteFileTool,
            GlobTool,
            SearchFileContentTool,
            ReplaceTool,
            # Todo工具
            WriteTodoTool,
            # 假设管理工具
            HypothesisTool,
            # 分析模块对主 Agent 仅暴露两个入口：分析单实验、综合分析（具体分析策略与内容由分析模块内部决定）
            DataAnalysisTool,
            SynthesizeExperimentsTool,
            # 分析报告排版成 PDF（EasyPaper，可选 LLM 合成 meta）
            GeneratePaperTool,
        ]

        # 只有在环境变量配置了 WEB_SEARCH_API_URL 时才启用
        if _should_enable_mirothinker():
            MiroWebResearchTool = _try_import_mirothinker()
            if MiroWebResearchTool is not None:
                tool_classes.append(MiroWebResearchTool)
                logger.info("Miro Web Research（外部 MCP）已启用")
            else:
                logger.warning(
                    "检测到 WEB_SEARCH_API_URL 和 WEB_SEARCH_API_TOKEN，但 Miro Web Research（外部 MCP）不可用。"
                )
        for tool_class in tool_classes:
            # 创建默认实例用于获取schema
            default_instance = tool_class(
                workspace_path="",
                progress_callback=empty_progress_callback,
                tool_id="",
            )
            tool_name = default_instance.name
            self._tool_classes[tool_name] = tool_class
            self._default_tools[tool_name] = default_instance
            logger.info(f"注册工具: {tool_name}")

    def get_tool(
        self,
        name: str,
        workspace_path: str,
        progress_callback,
        tool_id: str,
    ) -> Optional[BaseTool]:
        """获取工具实例"""
        tool_class = self._tool_classes.get(name)
        if tool_class:
            return tool_class(
                workspace_path=workspace_path,
                progress_callback=progress_callback,
                tool_id=tool_id,
            )
        return None

    def get_all_tools(self) -> Dict[str, BaseTool]:
        """获取所有工具的默认实例（用于获取schema）"""
        return self._default_tools.copy()

    def get_openai_tools(self) -> List[ChatCompletionToolParam]:
        """
        获取OpenAI格式的工具列表（使用默认实例获取schema）

        Returns:
            OpenAI格式的工具列表
        """
        tools = list(self._default_tools.values())
        return [tool.to_openai_tool() for tool in tools]


# 全局工具注册表实例
_registry = ToolRegistry()


def get_registry() -> ToolRegistry:
    """获取全局工具注册表"""
    return _registry
