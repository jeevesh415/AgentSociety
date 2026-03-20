"""
Example custom agent skill.

每个 skill 的入口脚本需要导出一个 async def run(agent, ctx) 函数。
agent 是 PersonAgent 实例，ctx 是 step 上下文 dict。
"""

from __future__ import annotations
from typing import Any


async def run(agent: Any, ctx: dict[str, Any]) -> None:
    step_log: list[str] = ctx["step_log"]

    # 示例：读取当前 observation
    observation = getattr(agent, "_observation", None)
    if observation:
        step_log.append("MyCustomSkill: processed observation")
    else:
        step_log.append("MyCustomSkill: no observation available")
