"""cognition skill — 需求调整 + 情感/思考更新 + 意图形成（合并 LLM 调用）"""

from __future__ import annotations
from typing import Any


async def run(agent: Any, ctx: dict[str, Any]) -> None:
    step_log: list[str] = ctx["step_log"]

    cognition_result = await agent._update_cognition_and_intention()
    need_adj = cognition_result.need_adjustment

    step_log.append(f"NeedAdjust: {len(need_adj.adjustments)} adjustments")
    step_log.append(f"Need: {agent._need}")
    step_log.append(f"Emotion: {agent._emotion_types.value}")
    step_log.append(
        f"Intention: {agent._intention.intention if agent._intention else 'None'}"
    )

    # 标记 cognition 已运行，needs skill 不必重复执行
    ctx["cognition_ran"] = True
