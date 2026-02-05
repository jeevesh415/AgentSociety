"""LLM对话API路由"""

from __future__ import annotations

import json
import os
import asyncio
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from typing import AsyncGenerator

from agentsociety2.backend.models import (
    CompletionRequest,
)
from agentsociety2.backend.services.completion_service import CompletionService
from agentsociety2.backend.sse import MessageEvent, HeartbeatEvent, SSEEvent
from agentsociety2.logger import get_logger

logger = get_logger()

router = APIRouter(prefix="/api/v1/chat", tags=["chat"])

# 创建服务实例
_completion_service = CompletionService()


async def _stream_completion(request: CompletionRequest) -> AsyncGenerator[str, None]:
    """流式返回对话结果，使用timeout定时器策略：只有在completion事件持续5秒没有新的之后，才触发一次心跳"""
    # 创建事件队列
    event_queue: asyncio.Queue[SSEEvent | None] = asyncio.Queue()
    stream_finished = asyncio.Event()
    HEARTBEAT_TIMEOUT = 5.0  # 5秒超时后发送心跳
    
    async def completion_producer():
        """生产者：CompletionService产生的事件"""
        try:
            async for event in _completion_service.chat_stream(
                messages=request.messages,
                max_turns=request.max_turns,
                workspace_path=request.workspace_path,
            ):
                await event_queue.put(event)
            # 流式对话完成，发送None标记结束
            await event_queue.put(None)
        except Exception as e:
            logger.error(f"[SSE API] CompletionService错误: {e}", exc_info=True)
            error_event = MessageEvent(
                content=f"对话失败: {str(e)}",
                is_error=True,
            )
            await event_queue.put(error_event)
            await event_queue.put(None)
    
    event_count = 0
    completion_task = None
    
    try:
        logger.info(f"[SSE API] 开始流式对话，消息数: {len(request.messages)}")
        
        # 启动completion生产者任务
        completion_task = asyncio.create_task(completion_producer())
        
        # 消费者循环：使用timeout策略
        while True:
            try:
                # 等待事件，最多等待HEARTBEAT_TIMEOUT秒
                event = await asyncio.wait_for(
                    event_queue.get(),
                    timeout=HEARTBEAT_TIMEOUT
                )
                
                # 收到事件，立即处理
                # None表示流式对话完成
                if event is None:
                    logger.info(
                        f"[SSE API] 流式对话完成，共发送{event_count}个事件，发送[DONE]标记"
                    )
                    yield "data: [DONE]\n\n"
                    stream_finished.set()
                    break
                
                # 发送completion事件
                event_count += 1
                event_dict = event.model_dump()
                event_json = json.dumps(event_dict, ensure_ascii=False)
                logger.info(
                    f"[SSE API] 发送事件 #{event_count}: type={event_dict.get('type', 'unknown')}, 长度={len(event_json)}"
                )
                yield f"data: {event_json}\n\n"
                
            except asyncio.TimeoutError:
                # 5秒内没有新的completion事件，发送心跳
                if not stream_finished.is_set():
                    heartbeat_event = HeartbeatEvent(content="heartbeat")
                    event_dict = heartbeat_event.model_dump()
                    event_json = json.dumps(event_dict, ensure_ascii=False)
                    logger.info(
                        f"[SSE API] 发送心跳事件: type={event_dict.get('type', 'unknown')}"
                    )
                    yield f"data: {event_json}\n\n"
                    # 继续循环，等待下一个事件或下一次超时
                else:
                    # 流已结束，退出循环
                    break
                    
    except Exception as e:
        logger.error(f"[SSE API] 流式对话API错误: {e}", exc_info=True)
        stream_finished.set()
        error_event = MessageEvent(
            content=f"对话失败: {str(e)}",
            is_error=True,
        )
        logger.info(f"[SSE API] 发送error事件: {error_event.model_dump()}")
        yield f"data: {json.dumps(error_event.model_dump(), ensure_ascii=False)}\n\n"
    finally:
        # 确保completion任务完成
        stream_finished.set()
        if completion_task and not completion_task.done():
            try:
                await completion_task
            except Exception as e:
                logger.error(f"[SSE API] Completion任务错误: {e}", exc_info=True)


@router.post("/completion")
async def completion(request: CompletionRequest):
    """
    LLM对话接口，支持function calling和SSE流式传输

    如果stream=True，则返回SSE流式响应。
    workspace_path是必需参数，用于文件操作工具。
    """
    # 验证工作区路径
    if not os.path.exists(request.workspace_path):
        raise HTTPException(
            status_code=400, detail=f"工作区路径不存在: {request.workspace_path}"
        )
    if not os.path.isdir(request.workspace_path):
        raise HTTPException(
            status_code=400, detail=f"工作区路径不是目录: {request.workspace_path}"
        )

    if not request.stream:
        raise HTTPException(status_code=400, detail="只允许流式返回")

    return StreamingResponse(
        _stream_completion(request),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
