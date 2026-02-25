"""
AgentSociety 2: A modern, LLM-native agent simulation platform.

This package provides tools for building and simulating LLM-driven agents
in various environments for social science research.
"""

__version__ = "2.0.0"

# Import main components for easy access
from .agent import AgentBase, PersonAgent
from .env import (
    EnvBase,
    RouterBase,
    ReActRouter,
    PlanExecuteRouter,
    CodeGenRouter,
    TwoTierReActRouter,
    TwoTierPlanExecuteRouter,
    SearchToolRouter,
    tool,
)
from .society import AgentSocietyHelper
from .storage import ReplayWriter

__all__ = [
    "AgentBase",
    "PersonAgent",
    "EnvBase",
    "RouterBase",
    "ReActRouter",
    "PlanExecuteRouter",
    "CodeGenRouter",
    "TwoTierReActRouter",
    "TwoTierPlanExecuteRouter",
    "SearchToolRouter",
    "tool",
    "AgentSocietyHelper",
    "ReplayWriter",
]
