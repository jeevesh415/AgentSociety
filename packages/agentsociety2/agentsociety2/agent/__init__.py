"""智能体模块 - 提供 Agent 的核心类。

本模块包含：

**AgentBase** — 智能体抽象基类：
- 定义智能体的基本接口（ask、step、dump、load）
- 提供 LLM 交互、环境交互、回放写入等基础功能
- 支持 skill 状态管理和 token 使用统计

**PersonAgent** — skills-first agent：
- 每个 agent 拥有独立工作区和会话线程
- 通过 skill catalog + 工具调用自主完成任务
- 适用于通用社会模拟场景

使用示例::

    from agentsociety2.agent import AgentBase, PersonAgent
    from datetime import datetime

    # 使用 PersonAgent
    agent = PersonAgent(id=1, profile={"name": "Alice"})

    # 自定义 Agent
    class MyAgent(AgentBase):
        async def ask(self, message: str, readonly: bool = True) -> str:
            return f"Received: {message}"
        async def step(self, tick: int, t: datetime) -> str:
            return "Step completed"
        async def dump(self) -> dict:
            return {}
        async def load(self, dump_data: dict):
            pass
"""

from .base import AgentBase
from .person import PersonAgent

__all__ = ["AgentBase", "PersonAgent"]
