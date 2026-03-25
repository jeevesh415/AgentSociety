"""存储模块 - 提供实验数据的存储与回放功能。

本模块包含：

**ReplayWriter** — 回放数据写入器：
- 写入 SQLite 数据库
- 支持框架表（agent_profile、agent_status、agent_dialog）
- 支持动态表注册

**数据模型**：
- ``AgentProfile``: 智能体档案表
- ``AgentStatus``: 智能体状态表
- ``AgentDialog``: 智能体对话表

**动态表**：
- ``ColumnDef``: 列定义
- ``TableSchema``: 表结构定义

使用示例::

    from agentsociety2.storage import ReplayWriter, ColumnDef, TableSchema

    # 创建写入器
    writer = ReplayWriter("replay.db")

    # 注册动态表
    writer.register_table(TableSchema(
        name="custom_data",
        columns=[ColumnDef(name="key", dtype="TEXT")]
    ))

    # 写入数据
    await writer.write_agent_status(agent_id=1, step=0, t=datetime.now())
"""

from .replay_writer import ReplayWriter
from .models import (
    AgentProfile,
    AgentStatus,
    AgentDialog,
)
from .table_schema import ColumnDef, TableSchema

__all__ = [
    "ReplayWriter",
    "AgentProfile",
    "AgentStatus",
    "AgentDialog",
    "ColumnDef",
    "TableSchema",
]
