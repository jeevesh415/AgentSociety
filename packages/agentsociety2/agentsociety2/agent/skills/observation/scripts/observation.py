"""observation skill — 感知环境"""

from __future__ import annotations
from typing import Any


async def run(agent: Any, ctx: dict[str, Any]) -> None:
    step_log: list[str] = ctx["step_log"]
    t = ctx["t"]

    agent._observation_ctx = None
    agent._observation = None

    observe_ctx, observation = await agent.ask_env(
        {"id": agent._id}, "<observe>", readonly=True
    )

    agent._logger.debug("observation result:\n%s", observation or "None")

    observe_status = (observe_ctx.get("status", "unknown") if observe_ctx else "unknown")

    if observe_status in ("in_progress",):
        step_log.append(f"Observe: InProgress (status={observe_status})")
        ctx["early_return"] = "Skipped (observe in progress)"
        ctx["stop"] = True
        return

    agent._observation_ctx = observe_ctx
    agent._observation = observation

    await agent._add_memory_with_timestamp(
        f"Observed environment: {observation}",
        metadata={"type": "observation"},
        t=t,
    )
    step_log.append(f"Observe: OK (status={observe_status})")
