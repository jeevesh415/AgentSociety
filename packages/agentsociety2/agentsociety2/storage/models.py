"""回放数据存储的框架表（SQLModel）。

该模块定义三张框架表：

- :class:`~agentsociety2.storage.models.AgentProfile`：agent 基本信息与 profile
- :class:`~agentsociety2.storage.models.AgentStatus`：每步状态快照
- :class:`~agentsociety2.storage.models.AgentDialog`：对话/反思记录

它们由 :class:`~agentsociety2.storage.ReplayWriter` 在初始化时创建并写入。
"""

from datetime import datetime
from typing import Any, Dict, Optional

from sqlalchemy import JSON, Column
from sqlmodel import Field, SQLModel


class AgentProfile(SQLModel, table=True):
    """agent 档案信息（框架表）。"""

    __tablename__ = "agent_profile"

    id: int = Field(primary_key=True)
    name: str
    profile: Dict[str, Any] = Field(default={}, sa_column=Column(JSON))
    created_at: datetime = Field(default_factory=datetime.now)


class AgentStatus(SQLModel, table=True):
    """agent 在某一步的状态快照（框架表）。"""

    __tablename__ = "agent_status"

    id: int = Field(primary_key=True)
    step: int = Field(primary_key=True, index=True)
    t: datetime = Field(index=True)
    action: Optional[str] = None
    status: Optional[Dict[str, Any]] = Field(default=None, sa_column=Column(JSON))
    created_at: datetime = Field(default_factory=datetime.now)


class AgentDialog(SQLModel, table=True):
    """agent 对话记录（框架表）。"""

    __tablename__ = "agent_dialog"

    id: Optional[int] = Field(default=None, primary_key=True)
    agent_id: int = Field(index=True)
    step: int = Field(index=True)
    t: datetime
    type: int = Field(index=True)  # 0=反思 (thought/reflection); V2 only uses 0
    speaker: str
    content: str
    created_at: datetime = Field(default_factory=datetime.now)
