"""SSE事件数据模型，使用Pydantic规范化所有可能的事件格式"""

from __future__ import annotations

from typing import Literal, Union
from pydantic import BaseModel, Field
from enum import Enum


class SSEEventType(str, Enum):
    """SSE事件类型枚举"""

    MESSAGE = "message"  # 消息事件（思考/助手消息），前端应该显示相应的文字
    TOOL = "tool"  # 工具事件（调用/执行中），前端应该显示工具调用信息
    COMPLETE = "complete"  # 对话完成，前端应该终止SSE
    HEARTBEAT = "heartbeat"  # 心跳事件，用于保持连接活跃，前端应该直接丢弃


class BaseSSEEvent(BaseModel):
    """SSE事件基类"""

    type: str = Field(..., description="事件类型")
    content: str = Field(..., description="消息内容")

    class Config:
        use_enum_values = True


class MessageEvent(BaseSSEEvent):
    """消息事件（合并了思考事件和助手消息事件）"""

    type: str = Field(default=SSEEventType.MESSAGE.value, description="事件类型")
    is_thinking: bool = Field(default=False, description="是否为思考状态")
    is_error: bool = Field(default=False, description="是否为错误状态")


class ToolEvent(BaseSSEEvent):
    """工具事件（合并了工具调用和工具执行中事件）"""

    type: str = Field(default=SSEEventType.TOOL.value, description="事件类型")
    tool_name: str = Field(..., description="工具名称")
    tool_id: str = Field(..., description="工具调用ID")
    status: Literal["start", "progress", "success", "error"] = Field(
        ..., description="工具状态"
    )


class CompleteEvent(BaseSSEEvent):
    """完成事件（对话完成，携带最终文本内容）"""

    type: str = Field(default=SSEEventType.COMPLETE.value, description="事件类型")


class HeartbeatEvent(BaseSSEEvent):
    """心跳事件（用于保持连接活跃，前端应该直接丢弃）"""

    type: str = Field(default=SSEEventType.HEARTBEAT.value, description="事件类型")


# 所有SSE事件的联合类型
SSEEvent = Union[
    MessageEvent,
    ToolEvent,
    CompleteEvent,
    HeartbeatEvent,
]
