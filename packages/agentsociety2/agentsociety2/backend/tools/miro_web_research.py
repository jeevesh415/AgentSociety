"""外部 MCP 工具：`miro_web_research`。

通过 HTTP MCP 调用远程的 `run_task` 工具完成联网检索/阅读任务。
未配置 `WEB_SEARCH_API_URL` 时该工具不会被注册。
"""

from __future__ import annotations

import uuid
from typing import Any, Dict

from mcp.client.session import ClientSession
from mcp.client.streamable_http import streamablehttp_client

from agentsociety2.backend.sse import ToolEvent
from agentsociety2.backend.tools.base import BaseTool, ToolResult
from agentsociety2.config.config import Config
from agentsociety2.logger import get_logger

logger = get_logger()

MCP_URL = Config.WEB_SEARCH_API_URL
MCP_TOKEN = Config.WEB_SEARCH_API_TOKEN
DEFAULT_LLM = Config.MIROFLOW_DEFAULT_LLM
DEFAULT_AGENT = Config.MIROFLOW_DEFAULT_AGENT


class MiroWebResearchTool(BaseTool):
    """Miro Web Research（通过外部 MCP server）。"""

    def __init__(
        self,
        workspace_path: str,
        progress_callback,
        tool_id: str,
    ):
        super().__init__(
            workspace_path=workspace_path,
            progress_callback=progress_callback,
            tool_id=tool_id,
        )

        if not MCP_URL:
            raise ValueError(
                "WEB_SEARCH_API_URL 未设置，无法使用 miro_web_research 外部 MCP 工具。"
            )
        if not MCP_TOKEN:
            raise ValueError(
                "WEB_SEARCH_API_TOKEN 未设置，无法使用 miro_web_research 外部 MCP 工具。"
            )

    def get_name(self) -> str:
        return "miro_web_research"

    def get_description(self) -> str:
        return (
            "Miro Web Research：通过外部 MCP Server 执行联网搜索/阅读任务。\n\n"
            "需要配置 WEB_SEARCH_API_URL 和 WEB_SEARCH_API_TOKEN。"
        )

    def get_parameters_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "任务描述或查询。",
                },
                "llm": {
                    "type": "string",
                    "description": f"LLM 模型名称（默认 {DEFAULT_LLM}）。",
                },
                "agent": {
                    "type": "string",
                    "description": f"Agent 配置名称（默认 {DEFAULT_AGENT}）。",
                },
            },
            "required": ["query"],
        }

    async def execute(self, arguments: Dict[str, Any]) -> ToolResult:
        query = (arguments.get("query") or "").strip()
        if not query:
            return ToolResult(
                success=False, content="查询内容不能为空", error="query is required"
            )

        llm = (arguments.get("llm") or DEFAULT_LLM).strip()
        agent = (arguments.get("agent") or DEFAULT_AGENT).strip()
        task_id = f"miro_web_research_{uuid.uuid4().hex[:8]}"

        await self._send_progress(
            ToolEvent(
                tool_name=self.name,
                tool_id=self._current_tool_id,
                status="start",
                content=f"连接 MCP 服务并启动任务：{query[:60]}...",
            )
        )

        headers = {"Authorization": f"Bearer {MCP_TOKEN}"}
        logger.info(f"Miro MCP: url={MCP_URL}, task_id={task_id}")

        try:
            async with streamablehttp_client(MCP_URL, headers=headers) as (
                read,
                write,
                _,
            ):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    tools = await session.list_tools()
                    if "run_task" not in [t.name for t in tools.tools]:
                        return ToolResult(
                            success=False,
                            content="远端 MCP 未提供 run_task 工具",
                            error="run_task tool not found on MCP server",
                        )

                    await self._send_progress(
                        ToolEvent(
                            tool_name=self.name,
                            tool_id=self._current_tool_id,
                            status="progress",
                            content="已连接 MCP，开始执行 run_task...",
                        )
                    )

                    result = await session.call_tool(
                        "run_task",
                        {
                            "task_description": query,
                            "llm": llm,
                            "agent": agent,
                        },
                    )

            if result.isError:
                error_blocks = [
                    block.text
                    for block in result.content
                    if hasattr(block, "text") and block.text
                ]
                error_msg = (
                    "\n".join(error_blocks).strip() if error_blocks else "未知错误"
                )
                logger.error(f"Miro MCP run_task 返回错误: {error_msg}")
                return ToolResult(
                    success=False,
                    content=f"Miro Web Research 执行失败: {error_msg}",
                    error=error_msg,
                )

            blocks = [
                block.text
                for block in result.content
                if hasattr(block, "text") and block.text
            ]
            content = "\n\n".join(blocks).strip() if blocks else "远端 MCP 返回为空"

        except Exception as e:
            logger.error(f"Miro MCP 连接或执行失败: {e}", exc_info=True)
            return ToolResult(
                success=False,
                content=f"Miro Web Research 执行失败: {str(e)}",
                error=str(e),
            )

        await self._send_progress(
            ToolEvent(
                tool_name=self.name,
                tool_id=self._current_tool_id,
                status="success",
                content="任务执行完成",
            )
        )

        return ToolResult(
            success=True,
            content=f"## Miro Web Research（MCP）结果\n\n{content}",
            data={
                "query": query,
                "task_id": task_id,
                "mcp_url": MCP_URL,
                "llm": llm,
                "agent": agent,
            },
        )
