"""memory skill — step 收尾：cognition memory flush + 可选 intention 查询"""

from __future__ import annotations
from typing import Any


async def run(agent: Any, ctx: dict[str, Any]) -> None:
    # flush 当前 step 积累的 cognition_memory 到长期记忆（纯内存操作，无 LLM）
    await agent._flush_cognition_memory_to_memory()

    # intention 查询需要 1 次 LLM 调用，仅在 cognition skill 已加载时才有意义
    if ctx.get("cognition_ran") and agent.ask_intention_enabled and agent._step_count % 2 == 0:
        await agent._query_current_intention()
