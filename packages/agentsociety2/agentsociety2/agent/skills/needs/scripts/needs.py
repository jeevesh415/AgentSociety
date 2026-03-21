"""needs skill — 需求调整（fallback：仅在 cognition skill 未加载时独立运行）"""

from __future__ import annotations
from typing import Any


async def run(agent: Any, ctx: dict[str, Any]) -> None:
    selected_skills = ctx.get("selected_skills", set())
    if "cognition" in selected_skills or ctx.get("cognition_ran"):
        return

    result = await agent._adjust_needs_from_memory()
    ctx["step_log"].append(f"NeedAdjust: {len(result.adjustments)} adjustments")
    await agent._determine_current_need()
    ctx["step_log"].append(f"Need: {agent._need}")
