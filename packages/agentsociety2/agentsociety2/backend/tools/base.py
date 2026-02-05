"""工具基类"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, Callable, Awaitable
from pydantic import BaseModel

from openai.types.chat import ChatCompletionToolParam
from agentsociety2.backend.sse import ToolEvent
from agentsociety2.logger import get_logger

logger = get_logger()


class ToolResult(BaseModel):
    """工具执行结果"""

    success: bool
    content: str
    data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


# 进度回调函数类型：接受一个ToolEvent，返回None
ProgressCallback = Callable[[ToolEvent], Awaitable[None]]


class BaseTool(ABC):
    """工具基类"""

    def __init__(
        self,
        workspace_path: str,
        progress_callback: Optional[ProgressCallback],
        tool_id: str,
    ):
        self.name = self.get_name()
        self.description = self.get_description()
        self.parameters_schema = self.get_parameters_schema()
        self._workspace_path: str = workspace_path
        self._progress_callback: Optional[ProgressCallback] = progress_callback
        self._current_tool_id: str = tool_id

    async def _send_progress(self, tool_event: ToolEvent):
        """
        发送进度更新事件

        Args:
            tool_event: ToolEvent对象
        """
        try:
            if self._progress_callback:
                await self._progress_callback(tool_event)
        except Exception as e:
            logger.warning(f"发送进度更新失败: {e}")

    @abstractmethod
    def get_name(self) -> str:
        """返回工具名称"""
        pass

    @abstractmethod
    def get_description(self) -> str:
        """返回工具描述"""
        pass

    @abstractmethod
    def get_parameters_schema(self) -> Dict[str, Any]:
        """返回工具参数schema（JSON Schema格式）"""
        pass

    @abstractmethod
    async def execute(self, arguments: Dict[str, Any]) -> ToolResult:
        """
        执行工具

        Args:
            arguments: 工具参数

        Returns:
            工具执行结果
        """
        pass

    def to_openai_tool(self) -> ChatCompletionToolParam:
        """转换为OpenAI格式的工具定义"""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters_schema,
            },
        }
