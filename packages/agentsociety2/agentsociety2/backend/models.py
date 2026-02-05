"""Pydantic models for API requests and responses"""

from __future__ import annotations

from typing import List, Dict, Any, Optional, Literal
from pydantic import BaseModel, Field


# ==================== Chat/Completion Models ====================

class ChatMessage(BaseModel):
    """聊天消息"""
    role: Literal["system", "user", "assistant", "tool"] = Field(..., description="消息角色")
    content: Optional[str] = Field(None, description="消息内容")
    tool_calls: Optional[List[Dict[str, Any]]] = Field(None, description="工具调用（assistant角色）")
    tool_call_id: Optional[str] = Field(None, description="工具调用ID（tool角色）")
    name: Optional[str] = Field(None, description="工具名称（tool角色）")
    data: Optional[Dict[str, Any]] = Field(None, description="工具结果数据（tool角色，用于传递结构化数据如文献搜索结果）")


class CompletionRequest(BaseModel):
    """LLM对话请求"""
    messages: List[ChatMessage] = Field(..., description="对话消息列表")
    max_turns: int = Field(50, ge=1, le=50, description="最大对话轮数")
    stream: bool = Field(True, description="是否流式返回")
    workspace_path: str = Field(..., description="工作区路径，用于文件操作工具（必需）")


class ToolCall(BaseModel):
    """工具调用"""
    id: str = Field(..., description="工具调用ID")
    name: str = Field(..., description="工具名称")
    arguments: Dict[str, Any] = Field(..., description="工具参数")


class CompletionResponse(BaseModel):
    """LLM对话响应"""
    success: bool = Field(..., description="是否成功")
    messages: List[ChatMessage] = Field(..., description="完整的对话消息列表（包括工具调用结果）")
    final_answer: Optional[str] = Field(None, description="最终答案（如果对话完成）")
    tool_calls: Optional[List[ToolCall]] = Field(None, description="本轮的工具调用")
    is_complete: bool = Field(..., description="对话是否完成")
    turn_count: int = Field(..., description="当前轮数")
    message: Optional[str] = Field(None, description="状态消息")


# ==================== Tool Definitions ====================

class ToolDefinition(BaseModel):
    """工具定义"""
    name: str = Field(..., description="工具名称")
    description: str = Field(..., description="工具描述")
    parameters: Dict[str, Any] = Field(..., description="工具参数schema（JSON Schema格式）")


class ToolsListResponse(BaseModel):
    """工具列表响应"""
    success: bool = Field(..., description="是否成功")
    tools: List[ToolDefinition] = Field(..., description="可用工具列表")


# ==================== Error Response Model ====================

class ErrorResponse(BaseModel):
    """错误响应"""
    success: bool = False
    error: str
    detail: Optional[str] = None
