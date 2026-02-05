"""
Registry for environment modules and agent modules in MCP server.

This module provides simple constant lists for registered environment modules and agent modules
that should be available through the MCP server's discovery interfaces.
These lists should be manually maintained by developers.
"""

from typing import List, Tuple, Type

from agentsociety2.agent.base import AgentBase
from agentsociety2.contrib.agent.llm_donor_agent import LLMDonorAgent
from agentsociety2.contrib.env.reputation_game import ReputationGameEnv
from agentsociety2.contrib.env.economy_space import EconomySpace
from agentsociety2.contrib.env.global_information import GlobalInformationEnv
from agentsociety2.contrib.env.mobility_space.environment import MobilitySpace
from agentsociety2.contrib.env.simple_social_space import SimpleSocialSpace
from agentsociety2.contrib.env.commons_tragedy import CommonsTragedyEnv
from agentsociety2.contrib.env.public_goods import PublicGoodsEnv
from agentsociety2.contrib.env.prisoners_dilemma import PrisonersDilemmaEnv
from agentsociety2.contrib.env.trust_game import TrustGameEnv
from agentsociety2.contrib.env.volunteer_dilemma import VolunteerDilemmaEnv
from agentsociety2.contrib.env.social_media import SocialMediaSpace
from agentsociety2.contrib.agent.commons_tragedy_agent import CommonsTragedyAgent
from agentsociety2.contrib.agent.public_goods_agent import PublicGoodsAgent
from agentsociety2.contrib.agent.prisoners_dilemma_agent import PrisonersDilemmaAgent
from agentsociety2.contrib.agent.trust_game_agent import TrustGameAgent
from agentsociety2.contrib.agent.volunteer_dilemma_agent import VolunteerDilemmaAgent
from agentsociety2.agent.person import PersonAgent
from agentsociety2.env.base import EnvBase

__all__ = [
    "REGISTERED_ENV_MODULES",
    "REGISTERED_AGENT_MODULES",
]


# Register environment modules here
# Format: (module_type: str, env_class: Type[EnvBase])
# Example:
#   from agentsociety2.contrib.env.mobility_space.environment import MobilitySpace
#   REGISTERED_ENV_MODULES = [
#       ("mobility_space", MobilitySpace),
#   ]
REGISTERED_ENV_MODULES: List[Tuple[str, Type[EnvBase]]] = [
    ("global_information", GlobalInformationEnv),
    ("economy_space", EconomySpace),
    ("simple_social_space", SimpleSocialSpace),
    ("mobility_space", MobilitySpace),
    ("reputation_game", ReputationGameEnv),
    ("commons_tragedy", CommonsTragedyEnv),
    ("public_goods", PublicGoodsEnv),
    ("prisoners_dilemma", PrisonersDilemmaEnv),
    ("trust_game", TrustGameEnv),
    ("volunteer_dilemma", VolunteerDilemmaEnv),
    ("social_media", SocialMediaSpace),
]


# Register agent modules here
# Format: (agent_type: str, agent_class: Type[AgentBase])
# Example:
#   from agentsociety2.contrib.agent.donothing import DoNothingAgent
#   REGISTERED_AGENT_MODULES = [
#       ("do_nothing", DoNothingAgent),
#   ]
REGISTERED_AGENT_MODULES: List[Tuple[str, Type[AgentBase]]] = [
    ("llm_donor_agent", LLMDonorAgent),
    ("commons_tragedy_agent", CommonsTragedyAgent),
    ("public_goods_agent", PublicGoodsAgent),
    ("prisoners_dilemma_agent", PrisonersDilemmaAgent),
    ("trust_game_agent", TrustGameAgent),
    ("volunteer_dilemma_agent", VolunteerDilemmaAgent),
    ("person_agent", PersonAgent),
]
