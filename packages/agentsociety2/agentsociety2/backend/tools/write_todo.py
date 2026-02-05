"""Todo工具 - 用于创建和管理任务列表"""

from __future__ import annotations

from typing import Dict, Any, List, Literal
from pydantic import BaseModel, Field, ValidationError

from agentsociety2.backend.tools.base import BaseTool, ToolResult
from agentsociety2.backend.sse import ToolEvent
from agentsociety2.logger import get_logger

logger = get_logger()


class TodoItem(BaseModel):
    """Todo项模型"""

    description: str = Field(
        ...,
        description="The task description",
    )
    status: Literal["pending", "in_progress", "completed", "cancelled"] = Field(
        ...,
        description="The current status of the task",
    )


class WriteTodoTool(BaseTool):
    """Todo工具 - 允许AI代理创建和管理任务列表"""

    def get_name(self) -> str:
        """返回工具名称"""
        return "write_todos"

    def get_description(self) -> str:
        """返回工具描述"""
        return (
            "Create and manage a list of subtasks for complex user requests. "
            "This provides visibility into the agent's plan and current progress. "
            "Only one task should be marked as 'in_progress' at a time. "
            "The todos list replaces the existing list entirely."
        )

    def get_parameters_schema(self) -> Dict[str, Any]:
        """返回工具参数schema（JSON Schema格式）"""
        return {
            "type": "object",
            "properties": {
                "todos": {
                    "type": "array",
                    "description": "The complete list of todo items. This replaces the existing list.",
                    "items": {
                        "type": "object",
                        "properties": {
                            "description": {
                                "type": "string",
                                "description": "The task description",
                            },
                            "status": {
                                "type": "string",
                                "description": "The current status of the task",
                                "enum": ["pending", "in_progress", "completed", "cancelled"],
                            },
                        },
                        "required": ["description", "status"],
                    },
                    "minItems": 0,
                },
            },
            "required": ["todos"],
        }

    async def execute(self, arguments: Dict[str, Any]) -> ToolResult:
        """
        执行工具

        Args:
            arguments: 工具参数，包含 todos 数组

        Returns:
            工具执行结果
        """
        try:
            # 验证参数
            todos_data = arguments.get("todos", [])
            if not isinstance(todos_data, list):
                return ToolResult(
                    success=False,
                    content="Invalid argument: 'todos' must be an array",
                    error="InvalidArgument",
                )

            # 验证每个todo项
            todos: List[TodoItem] = []
            in_progress_count = 0

            for idx, todo_data in enumerate(todos_data):
                try:
                    todo = TodoItem(**todo_data)
                    todos.append(todo)

                    # 统计 in_progress 数量
                    if todo.status == "in_progress":
                        in_progress_count += 1

                except ValidationError as e:
                    return ToolResult(
                        success=False,
                        content=f"Invalid todo item {idx + 1}: {str(e)}",
                        error="ValidationError",
                    )

            # 验证：最多只能有一个 in_progress 任务
            if in_progress_count > 1:
                return ToolResult(
                    success=False,
                    content=f"Only one task can be marked as 'in_progress' at a time. "
                    f"Found {in_progress_count} tasks with 'in_progress' status.",
                    error="MultipleInProgress",
                )

            # 发送进度更新
            progress_event = ToolEvent(
                tool_name=self.name,
                tool_id=self._current_tool_id,
                status="progress",
                content=f"Updated todo list with {len(todos)} items",
            )
            await self._send_progress(progress_event)

            # 构建响应内容
            if not todos:
                content = "Todo list cleared (no items remaining)."
            else:
                status_summary = {}
                for todo in todos:
                    status_summary[todo.status] = status_summary.get(todo.status, 0) + 1

                status_parts = [
                    f"{count} {status}" for status, count in sorted(status_summary.items())
                ]
                content = (
                    f"Todo list updated with {len(todos)} items: {', '.join(status_parts)}.\n\n"
                )

                # 列出所有任务
                for idx, todo in enumerate(todos, 1):
                    status_icon = {
                        "pending": "⏳",
                        "in_progress": "🔄",
                        "completed": "✅",
                        "cancelled": "❌",
                    }.get(todo.status, "•")
                    content += f"{status_icon} {todo.description} ({todo.status})\n"

            logger.info(f"Todo list updated: {len(todos)} items")

            return ToolResult(
                success=True,
                content=content,
                data={
                    "todos": [
                        {
                            "description": todo.description,
                            "status": todo.status,
                        }
                        for todo in todos
                    ],
                    "count": len(todos),
                    "in_progress_count": in_progress_count,
                },
            )

        except Exception as e:
            logger.error(f"执行write_todos工具时出错: {e}", exc_info=True)
            return ToolResult(
                success=False,
                content=f"Failed to update todo list: {str(e)}",
                error=str(e),
            )
