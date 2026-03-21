"""economic-reasoning skill — EconomySpace 环境下的经济决策辅助"""

from __future__ import annotations
from typing import Any


async def run(agent: Any, ctx: dict[str, Any]) -> None:
    observation = agent._observation or ""
    obs_lower = observation.lower()

    has_economic_context = any(
        kw in obs_lower
        for kw in ("currency", "price", "income", "tax", "product", "job", "wage", "economy")
    )
    if not has_economic_context:
        return

    # 查询 agent 的经济状态
    _, financial_info = await agent.ask_env(
        {"id": agent._id},
        f"get_person(agent_id={agent._id})",
        readonly=True,
    )

    agent._add_cognition_memory(
        f"Economic context: {financial_info}",
        memory_type="economic_analysis",
    )
    ctx["step_log"].append("EconomicReasoning: analyzed financial state")
