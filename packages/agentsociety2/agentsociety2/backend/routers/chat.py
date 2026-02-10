"""LLM对话API路由"""

from __future__ import annotations

import json
import os
import asyncio
import time
from fastapi import APIRouter, HTTPException, Request
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

# 客户端断开检测间隔（秒），用于及时取消任务避免资源泄露
DISCONNECT_CHECK_INTERVAL = 0.5
# 无新事件时发送心跳的超时（秒）
HEARTBEAT_TIMEOUT = 5.0


async def _stream_completion(request: CompletionRequest, req: Request) -> AsyncGenerator[str, None]:
    """流式返回对话结果，使用timeout定时器策略：只有在completion事件持续HEARTBEAT_TIMEOUT秒没有新的之后，才触发一次心跳。
    当检测到客户端断开连接时，立即取消completion任务以避免资源泄露。"""
    # 创建事件队列
    event_queue: asyncio.Queue[SSEEvent | None] = asyncio.Queue()
    stream_finished = asyncio.Event()
    last_activity_time = time.monotonic()
    
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
        except asyncio.CancelledError:
            # 客户端断开时任务被取消，正常退出
            logger.info("[SSE API] Completion任务被取消（客户端已断开）")
            raise
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
        
        # 消费者循环：使用短超时以便定期检测客户端断开
        while True:
            try:
                # 等待事件，使用短超时以便检测客户端断开
                event = await asyncio.wait_for(
                    event_queue.get(),
                    timeout=DISCONNECT_CHECK_INTERVAL
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
                last_activity_time = time.monotonic()
                event_count += 1
                event_dict = event.model_dump()
                event_json = json.dumps(event_dict, ensure_ascii=False)
                logger.info(
                    f"[SSE API] 发送事件 #{event_count}: type={event_dict.get('type', 'unknown')}, 长度={len(event_json)}"
                )
                yield f"data: {event_json}\n\n"
                
            except asyncio.TimeoutError:
                # 短超时到期，检测客户端是否断开
                if await req.is_disconnected():
                    logger.info("[SSE API] 检测到客户端断开连接，取消completion任务")
                    if completion_task and not completion_task.done():
                        completion_task.cancel()
                    stream_finished.set()
                    break
                # 未断开：检查是否需要发送心跳
                if not stream_finished.is_set():
                    elapsed = time.monotonic() - last_activity_time
                    if elapsed >= HEARTBEAT_TIMEOUT:
                        heartbeat_event = HeartbeatEvent(content="heartbeat")
                        event_dict = heartbeat_event.model_dump()
                        event_json = json.dumps(event_dict, ensure_ascii=False)
                        logger.info(
                            f"[SSE API] 发送心跳事件: type={event_dict.get('type', 'unknown')}"
                        )
                        yield f"data: {event_json}\n\n"
                        last_activity_time = time.monotonic()
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
        # 确保completion任务完成或已取消，避免资源泄露
        stream_finished.set()
        if completion_task and not completion_task.done():
            completion_task.cancel()
            try:
                await completion_task
            except asyncio.CancelledError:
                pass  # 预期：客户端断开时任务被取消
            except Exception as e:
                logger.error(f"[SSE API] Completion任务错误: {e}", exc_info=True)


@router.post("/completion")
async def completion(request: CompletionRequest, req: Request):
    """
    LLM对话接口，支持function calling和SSE流式传输

    如果stream=True，则返回SSE流式响应。
    workspace_path是必需参数，用于文件操作工具。
    当客户端断开连接时，会立即取消对话任务以释放资源。
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
        _stream_completion(request, req),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
