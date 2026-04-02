"""
实验数据API

提供实验结果数据的查询接口，支持：
- 获取实验时间线
- 获取agent状态
- 获取实验指标
- 兼容V1前端API格式

关联文件：
- @extension/src/replayWebviewProvider.ts - 前端Replay Webview（调用此API）

API端点：
- GET /api/v1/experiments/{hypothesis_id}/{experiment_id}/info - 实验信息
- GET /api/v1/experiments/{hypothesis_id}/{experiment_id}/timeline - 时间线
- GET /api/v1/experiments/{hypothesis_id}/{experiment_id}/agents/* - Agent数据
- GET /api/v1/experiments/{hypothesis_id}/{experiment_id}/state - 最新状态
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from agentsociety2.logger import get_logger
from agentsociety2.storage.replay_metadata import DATASET_CATALOG_TABLE

logger = get_logger()

router = APIRouter(prefix="/experiments", tags=["experiments"])


# ============================================================================
# Pydantic 模型
# ============================================================================


class TimePoint(BaseModel):
    """时间点"""

    day: int
    t: int  # 当天秒数 (0-86400)
    timestamp: str


class AgentProfile(BaseModel):
    """Agent配置文件"""

    id: int
    name: Optional[str] = None
    profile: Optional[Dict[str, Any]] = None


class AgentStatus(BaseModel):
    """Agent状态"""

    id: int
    day: int
    t: int
    lng: Optional[float] = None
    lat: Optional[float] = None
    parent_id: Optional[int] = None
    action: Optional[str] = None
    status: Optional[Dict[str, Any]] = None


class ExperimentInfo(BaseModel):
    """实验信息"""

    experiment_id: str
    hypothesis_id: str
    status: str
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    agent_count: int
    step_count: int


# ============================================================================
# 辅助函数
# ============================================================================


def _get_experiment_path(
    workspace_path: Path,
    hypothesis_id: str,
    experiment_id: str,
) -> Path:
    """获取实验目录路径"""
    return (
        workspace_path / f"hypothesis_{hypothesis_id}" / f"experiment_{experiment_id}"
    )


def _get_db_connection(db_path: Path) -> sqlite3.Connection:
    """获取数据库连接"""
    if not db_path.exists():
        raise HTTPException(
            status_code=404,
            detail=f"Database not found: {db_path}. The experiment may not have been run yet.",
        )
    return sqlite3.connect(db_path)


def _parse_json_field(raw: Any, default: Any) -> Any:
    """解析 SQLite 中保存的 JSON 字段。"""
    if raw is None:
        return default
    if isinstance(raw, (dict, list)):
        return raw
    if isinstance(raw, (bytes, bytearray)):
        raw = raw.decode("utf-8", errors="ignore")
    if isinstance(raw, str):
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return default
    return default


def _datetime_to_day_t(dt: datetime, start_t: datetime) -> tuple[int, int]:
    """将datetime转换为(day, t)格式"""
    delta = dt - start_t
    day = delta.days
    t = int(delta.seconds)
    return day, t


def _table_exists(cursor: sqlite3.Cursor, table_name: str) -> bool:
    cursor.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name = ?",
        (table_name,),
    )
    return cursor.fetchone() is not None


def _quote_identifier(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


def _coerce_datetime(raw: Any) -> Optional[datetime]:
    if raw is None:
        return None
    if isinstance(raw, datetime):
        return raw
    if isinstance(raw, (bytes, bytearray)):
        raw = raw.decode("utf-8", errors="ignore")
    if isinstance(raw, str):
        try:
            return datetime.fromisoformat(raw)
        except ValueError:
            return None
    return None


def _load_dataset_catalog(cursor: sqlite3.Cursor) -> List[Dict[str, Any]]:
    if not _table_exists(cursor, DATASET_CATALOG_TABLE):
        return []

    cursor.execute(
        f"""
        SELECT dataset_id, table_name, module_name, kind,
               entity_key, step_key, time_key,
               default_order_json, capabilities_json
        FROM {DATASET_CATALOG_TABLE}
        ORDER BY dataset_id ASC
        """
    )
    datasets: List[Dict[str, Any]] = []
    for row in cursor.fetchall():
        (
            dataset_id,
            table_name,
            module_name,
            kind,
            entity_key,
            step_key,
            time_key,
            default_order_raw,
            capabilities_raw,
        ) = row
        default_order = _parse_json_field(default_order_raw, [])
        capabilities = _parse_json_field(capabilities_raw, [])
        datasets.append(
            {
                "dataset_id": dataset_id,
                "table_name": table_name,
                "module_name": module_name,
                "kind": kind,
                "entity_key": entity_key,
                "step_key": step_key,
                "time_key": time_key,
                "default_order": default_order if isinstance(default_order, list) else [],
                "capabilities": capabilities if isinstance(capabilities, list) else [],
            }
        )
    return datasets


def _get_table_columns(cursor: sqlite3.Cursor, table_name: str) -> set[str]:
    cursor.execute(f"PRAGMA table_info({_quote_identifier(table_name)})")
    return {str(row[1]) for row in cursor.fetchall()}


def _dataset_has_columns(
    cursor: sqlite3.Cursor,
    dataset: Dict[str, Any],
    *column_names: str,
) -> bool:
    available = _get_table_columns(cursor, dataset["table_name"])
    return all(column_name in available for column_name in column_names)


def _get_agent_status_dataset(cursor: sqlite3.Cursor) -> Optional[Dict[str, Any]]:
    candidates = [
        dataset
        for dataset in _load_dataset_catalog(cursor)
        if dataset.get("kind") == "entity_snapshot"
        and "agent_snapshot" in dataset.get("capabilities", [])
        and dataset.get("entity_key")
        and dataset.get("step_key")
        and dataset.get("time_key")
        and _table_exists(cursor, dataset["table_name"])
        and _dataset_has_columns(
            cursor,
            dataset,
            dataset["entity_key"],
            dataset["step_key"],
            dataset["time_key"],
        )
    ]
    candidates.sort(
        key=lambda item: (
            0 if "geo_point" in item.get("capabilities", []) else 1,
            item["dataset_id"],
        )
    )
    return candidates[0] if candidates else None


def _load_agent_profiles(cursor: sqlite3.Cursor) -> List[AgentProfile]:
    if not _table_exists(cursor, "agent_profile"):
        return []

    cursor.execute("SELECT id, name, profile FROM agent_profile ORDER BY id ASC")
    agents: List[AgentProfile] = []
    for agent_id, name, profile_raw in cursor.fetchall():
        profile = _parse_json_field(profile_raw, {})
        if not isinstance(profile, dict):
            profile = {}
        agents.append(
            AgentProfile(
                id=int(agent_id),
                name=name or profile.get("name"),
                profile=profile,
            )
        )
    return agents


def _build_profiles_from_status_rows(
    status_rows: List[Tuple[int, int, datetime, Optional[str], Dict[str, Any]]],
) -> List[AgentProfile]:
    agent_ids = sorted({agent_id for agent_id, _, _, _, _ in status_rows})
    return [
        AgentProfile(id=agent_id, name=f"Agent_{agent_id}", profile={})
        for agent_id in agent_ids
    ]


def _build_profiles_from_status_entries(
    status_entries: List[Dict[str, Any]],
) -> List[AgentProfile]:
    agent_ids = sorted({int(entry["id"]) for entry in status_entries})
    return [
        AgentProfile(id=agent_id, name=f"Agent_{agent_id}", profile={})
        for agent_id in agent_ids
    ]


def _load_agent_status_rows(
    cursor: sqlite3.Cursor,
    agent_id: Optional[int] = None,
) -> List[Tuple[int, int, datetime, Optional[str], Dict[str, Any]]]:
    if not _table_exists(cursor, "agent_status"):
        return []

    query = "SELECT id, step, t, action, status FROM agent_status"
    params: tuple[Any, ...] = ()
    if agent_id is not None:
        query += " WHERE id = ?"
        params = (agent_id,)
    query += " ORDER BY step ASC, id ASC"
    cursor.execute(query, params)

    rows: List[Tuple[int, int, datetime, Optional[str], Dict[str, Any]]] = []
    for raw_agent_id, step, t_raw, action, status_raw in cursor.fetchall():
        if not t_raw:
            continue
        try:
            timestamp = datetime.fromisoformat(str(t_raw))
        except ValueError:
            continue
        status = _parse_json_field(status_raw, {})
        if not isinstance(status, dict):
            status = {}
        rows.append((int(raw_agent_id), int(step), timestamp, action, status))
    return rows


def _load_agent_profiles_from_dataset(
    cursor: sqlite3.Cursor,
    dataset: Dict[str, Any],
) -> List[AgentProfile]:
    entity_key = dataset["entity_key"]
    table_name = dataset["table_name"]
    cursor.execute(
        f"""
        SELECT DISTINCT {_quote_identifier(entity_key)}
        FROM {_quote_identifier(table_name)}
        WHERE {_quote_identifier(entity_key)} IS NOT NULL
        ORDER BY {_quote_identifier(entity_key)} ASC
        """
    )
    return [
        AgentProfile(id=int(agent_id), name=f"Agent_{int(agent_id)}", profile={})
        for (agent_id,) in cursor.fetchall()
        if agent_id is not None
    ]


def _load_agent_status_entries_from_dataset(
    cursor: sqlite3.Cursor,
    dataset: Dict[str, Any],
    *,
    agent_id: Optional[int] = None,
) -> List[Dict[str, Any]]:
    entity_key = dataset["entity_key"]
    step_key = dataset["step_key"]
    time_key = dataset["time_key"]
    table_name = dataset["table_name"]

    query = f"SELECT * FROM {_quote_identifier(table_name)}"
    params: tuple[Any, ...] = ()
    if agent_id is not None:
        query += f" WHERE {_quote_identifier(entity_key)} = ?"
        params = (agent_id,)
    query += (
        f" ORDER BY {_quote_identifier(step_key)} ASC, "
        f"{_quote_identifier(entity_key)} ASC"
    )

    cursor.execute(query, params)
    column_names = [description[0] for description in cursor.description or []]

    entries: List[Dict[str, Any]] = []
    for row in cursor.fetchall():
        payload = dict(zip(column_names, row))
        timestamp = _coerce_datetime(payload.pop(time_key, None))
        raw_agent_id = payload.pop(entity_key, None)
        step = payload.pop(step_key, None)
        if timestamp is None or raw_agent_id is None or step is None:
            continue

        lng = payload.pop("lng", None)
        lat = payload.pop("lat", None)
        action = payload.pop("action", None)
        parent_id = payload.pop("parent_id", None)
        payload.pop("created_at", None)

        entries.append(
            {
                "id": int(raw_agent_id),
                "step": int(step),
                "timestamp": timestamp,
                "lng": float(lng) if lng is not None else None,
                "lat": float(lat) if lat is not None else None,
                "parent_id": int(parent_id) if parent_id is not None else None,
                "action": action,
                "status": payload,
            }
        )
    return entries


def _load_agent_profiles_compat(cursor: sqlite3.Cursor) -> List[AgentProfile]:
    if _table_exists(cursor, "agent_profile"):
        return _load_agent_profiles(cursor)

    dataset = _get_agent_status_dataset(cursor)
    if dataset is None:
        return []
    return _load_agent_profiles_from_dataset(cursor, dataset)


def _load_agent_status_entries(
    cursor: sqlite3.Cursor,
    *,
    agent_id: Optional[int] = None,
) -> List[Dict[str, Any]]:
    if _table_exists(cursor, "agent_status"):
        return [
            {
                "id": raw_agent_id,
                "step": step,
                "timestamp": timestamp,
                "lng": None,
                "lat": None,
                "parent_id": None,
                "action": action,
                "status": status,
            }
            for raw_agent_id, step, timestamp, action, status in _load_agent_status_rows(
                cursor, agent_id=agent_id
            )
        ]

    dataset = _get_agent_status_dataset(cursor)
    if dataset is None:
        return []
    return _load_agent_status_entries_from_dataset(cursor, dataset, agent_id=agent_id)


def _get_agent_dataset_summary(
    cursor: sqlite3.Cursor,
) -> Tuple[int, Optional[datetime], Optional[datetime], int]:
    dataset = _get_agent_status_dataset(cursor)
    if dataset is None:
        return 0, None, None, 0

    table_name = dataset["table_name"]
    entity_key = dataset["entity_key"]
    step_key = dataset["step_key"]
    time_key = dataset["time_key"]
    cursor.execute(
        f"""
        SELECT COUNT(DISTINCT {_quote_identifier(step_key)}),
               MIN({_quote_identifier(time_key)}),
               MAX({_quote_identifier(time_key)}),
               COUNT(DISTINCT {_quote_identifier(entity_key)})
        FROM {_quote_identifier(table_name)}
        """
    )
    row = cursor.fetchone()
    if row is None:
        return 0, None, None, 0

    total_steps, start_raw, end_raw, agent_count = row
    return (
        int(total_steps or 0),
        _coerce_datetime(start_raw),
        _coerce_datetime(end_raw),
        int(agent_count or 0),
    )


def _get_first_timestamp(
    status_rows: List[Dict[str, Any]],
) -> Optional[datetime]:
    if status_rows:
        return status_rows[0]["timestamp"]
    return None


# ============================================================================
# API 端点
# ============================================================================


@router.get("/{hypothesis_id}/{experiment_id}/info")
async def get_experiment_info(
    hypothesis_id: str,
    experiment_id: str,
    workspace_path: str = Query(..., description="Workspace directory path"),
) -> ExperimentInfo:
    """
    获取实验基本信息

    返回指定实验的基本信息，包括状态、时间、Agent数量等。

    Args:
        hypothesis_id: 假设ID，用于定位实验所属的假设目录
        experiment_id: 实验ID，用于定位具体的实验目录
        workspace_path: 工作区根目录路径

    Returns:
        ExperimentInfo: 实验基本信息对象，包含：
            - experiment_id: 实验ID
            - hypothesis_id: 假设ID
            - status: 实验状态 (not_started/running/completed/failed)
            - start_time: 开始时间
            - end_time: 结束时间
            - agent_count: Agent数量
            - step_count: 已执行步骤数

    Raises:
        HTTPException: 404 - 实验目录不存在
        HTTPException: 500 - 数据库查询失败
    """
    workspace = Path(workspace_path)
    exp_path = _get_experiment_path(workspace, hypothesis_id, experiment_id)

    if not exp_path.exists():
        raise HTTPException(status_code=404, detail="Experiment not found")

    run_dir = exp_path / "run"
    pid_file = run_dir / "pid.json"
    db_file = run_dir / "sqlite.db"

    # 读取状态
    status = "not_started"
    start_time = None
    end_time = None

    if pid_file.exists():
        try:
            pid_data = json.loads(pid_file.read_text(encoding="utf-8"))
            status = pid_data.get("status", "unknown")
            start_time = pid_data.get("start_time")
            end_time = pid_data.get("end_time")
        except Exception as e:
            logger.warning(f"Failed to read pid.json: {e}")

    # 获取agent和step数量
    agent_count = 0
    step_count = 0

    if db_file.exists():
        try:
            conn = _get_db_connection(db_file)
            cursor = conn.cursor()

            profiles = _load_agent_profiles_compat(cursor)
            if profiles:
                agent_count = len(profiles)
            elif _table_exists(cursor, "agent_status"):
                cursor.execute("SELECT COUNT(DISTINCT id) FROM agent_status")
                row = cursor.fetchone()
                agent_count = row[0] if row else 0
            else:
                _, _, _, agent_count = _get_agent_dataset_summary(cursor)

            # 获取step数量
            if _table_exists(cursor, "agent_status"):
                cursor.execute("SELECT COUNT(DISTINCT step) FROM agent_status")
                row = cursor.fetchone()
                step_count = row[0] if row else 0
            else:
                step_count, _, _, _ = _get_agent_dataset_summary(cursor)

            conn.close()
        except Exception as e:
            logger.warning(f"Failed to query database: {e}")

    return ExperimentInfo(
        experiment_id=experiment_id,
        hypothesis_id=hypothesis_id,
        status=status,
        start_time=start_time,
        end_time=end_time,
        agent_count=agent_count,
        step_count=step_count,
    )


@router.get("/{hypothesis_id}/{experiment_id}/timeline")
async def get_timeline(
    hypothesis_id: str,
    experiment_id: str,
    workspace_path: str = Query(..., description="Workspace directory path"),
) -> List[TimePoint]:
    """
    获取实验时间线

    返回实验所有记录的时间点，用于在时间轴上展示实验进度。

    Args:
        hypothesis_id: 假设ID
        experiment_id: 实验ID
        workspace_path: 工作区根目录路径

    Returns:
        List[TimePoint]: 时间点列表，每个时间点包含：
            - day: 模拟天数（从0开始）
            - t: 当天秒数 (0-86400)
            - timestamp: ISO格式的时间戳字符串

    Raises:
        HTTPException: 404 - 数据库不存在（实验未运行）
    """
    workspace = Path(workspace_path)
    exp_path = _get_experiment_path(workspace, hypothesis_id, experiment_id)
    db_file = exp_path / "run" / "sqlite.db"

    conn = _get_db_connection(db_file)
    cursor = conn.cursor()

    status_rows = _load_agent_status_entries(cursor)

    timeline: List[TimePoint] = []
    first_time = _get_first_timestamp(status_rows)

    if status_rows and first_time is not None:
        seen_steps: set[int] = set()
        for status_entry in status_rows:
            step = int(status_entry["step"])
            if step in seen_steps:
                continue
            seen_steps.add(step)
            timestamp = status_entry["timestamp"]
            day, t = _datetime_to_day_t(timestamp, first_time)
            timeline.append(
                TimePoint(day=day, t=t, timestamp=timestamp.isoformat())
            )
    conn.close()
    return timeline


@router.get("/{hypothesis_id}/{experiment_id}/agents")
async def get_agents(
    hypothesis_id: str,
    experiment_id: str,
    workspace_path: str = Query(..., description="Workspace directory path"),
) -> List[AgentProfile]:
    """
    获取所有Agent的配置信息

    返回实验中所有Agent的配置文件信息。

    Args:
        hypothesis_id: 假设ID
        experiment_id: 实验ID
        workspace_path: 工作区根目录路径

    Returns:
        List[AgentProfile]: Agent配置列表，每个配置包含：
            - id: Agent唯一标识符
            - name: Agent名称
            - profile: Agent详细配置字典

    Raises:
        HTTPException: 404 - 数据库不存在
    """
    workspace = Path(workspace_path)
    exp_path = _get_experiment_path(workspace, hypothesis_id, experiment_id)
    db_file = exp_path / "run" / "sqlite.db"

    conn = _get_db_connection(db_file)
    cursor = conn.cursor()

    agents = _load_agent_profiles_compat(cursor)
    if not agents:
        agents = _build_profiles_from_status_entries(_load_agent_status_entries(cursor))
    conn.close()
    return agents


@router.get("/{hypothesis_id}/{experiment_id}/agents/{agent_id}/status")
async def get_agent_status(
    hypothesis_id: str,
    experiment_id: str,
    agent_id: int,
    workspace_path: str = Query(..., description="Workspace directory path"),
    day: Optional[int] = Query(None, description="Day number (0-indexed)"),
    t: Optional[int] = Query(None, description="Time within day (seconds, 0-86400)"),
) -> List[AgentStatus]:
    """
    获取指定Agent的状态历史

    返回指定Agent在实验中的状态变化记录。

    Args:
        hypothesis_id: 假设ID
        experiment_id: 实验ID
        agent_id: Agent的唯一标识符
        workspace_path: 工作区根目录路径
        day: 可选，指定查询的模拟天数（0-indexed）
        t: 可选，指定查询的当天秒数（0-86400），与day配合使用

    Returns:
        List[AgentStatus]: Agent状态列表，每个状态包含：
            - id: Agent ID
            - day: 模拟天数
            - t: 当天秒数
            - lng: 经度坐标（如果有位置信息）
            - lat: 纬度坐标（如果有位置信息）
            - parent_id: 父Agent ID（如果有）
            - action: 当前动作
            - status: 状态详情字典

    Note:
        如果指定了day和t参数，返回该时刻附近的状态（允许1分钟误差）；
        否则返回所有历史状态记录。

    Raises:
        HTTPException: 404 - 数据库不存在
    """
    workspace = Path(workspace_path)
    exp_path = _get_experiment_path(workspace, hypothesis_id, experiment_id)
    db_file = exp_path / "run" / "sqlite.db"

    conn = _get_db_connection(db_file)
    cursor = conn.cursor()

    status_rows = _load_agent_status_entries(cursor, agent_id=agent_id)
    all_status_rows = _load_agent_status_entries(cursor)
    first_time = _get_first_timestamp(all_status_rows)

    statuses: List[AgentStatus] = []
    if first_time is not None:
        for status_entry in status_rows:
            timestamp = status_entry["timestamp"]
            current_day, current_t = _datetime_to_day_t(timestamp, first_time)
            if day is not None and t is not None:
                if current_day != day or abs(current_t - t) > 60:
                    continue
            statuses.append(
                AgentStatus(
                    id=agent_id,
                    day=current_day,
                    t=current_t,
                    lng=status_entry["lng"],
                    lat=status_entry["lat"],
                    parent_id=status_entry["parent_id"],
                    action=status_entry["action"],
                    status=status_entry["status"],
                )
            )

    conn.close()
    return statuses


@router.get("/{hypothesis_id}/{experiment_id}/state")
async def get_latest_state(
    hypothesis_id: str,
    experiment_id: str,
    workspace_path: str = Query(..., description="Workspace directory path"),
) -> Dict[str, Any]:
    """
    获取实验最新状态数据

    返回实验的最新完整状态，包括所有Agent的当前状态。

    Args:
        hypothesis_id: 假设ID
        experiment_id: 实验ID
        workspace_path: 工作区根目录路径

    Returns:
        Dict[str, Any]: 最新状态数据，包含：
            - timestamp: 记录时间戳
            - current_time: 当前模拟时间
            - step_count: 已执行步骤数
            - state: 完整状态数据（包含所有Agent信息）

    Raises:
        HTTPException: 404 - 数据库不存在或无状态数据
    """
    workspace = Path(workspace_path)
    exp_path = _get_experiment_path(workspace, hypothesis_id, experiment_id)
    db_file = exp_path / "run" / "sqlite.db"

    conn = _get_db_connection(db_file)
    cursor = conn.cursor()

    profiles = _load_agent_profiles_compat(cursor)
    status_rows = _load_agent_status_entries(cursor)
    conn.close()

    if not profiles and status_rows:
        profiles = _build_profiles_from_status_entries(status_rows)

    if not profiles and not status_rows:
        raise HTTPException(status_code=404, detail="No state data found")

    latest_timestamp: Optional[datetime] = None
    latest_step = 0
    if status_rows:
        latest_step = max(int(entry["step"]) for entry in status_rows)
        latest_timestamp = max(entry["timestamp"] for entry in status_rows)

    latest_status_by_agent: Dict[int, Dict[str, Any]] = {}
    for status_entry in status_rows:
        if int(status_entry["step"]) != latest_step:
            continue
        latest_status_by_agent[int(status_entry["id"])] = {
            "timestamp": status_entry["timestamp"],
            "action": status_entry["action"],
            "status": status_entry["status"],
        }

    agents_state = []
    for profile in profiles:
        state_entry = latest_status_by_agent.get(profile.id, {})
        agents_state.append(
            {
                "id": profile.id,
                "name": profile.name,
                "dump": {
                    "profile": profile.profile or {},
                    "current_action": state_entry.get("action"),
                    "status": state_entry.get("status", {}),
                },
            }
        )

    return {
        "timestamp": latest_timestamp.isoformat() if latest_timestamp else None,
        "current_time": latest_timestamp.isoformat() if latest_timestamp else None,
        "step_count": latest_step,
        "state": {"agents": agents_state},
    }


@router.get("/{hypothesis_id}/{experiment_id}/artifacts")
async def list_artifacts(
    hypothesis_id: str,
    experiment_id: str,
    workspace_path: str = Query(..., description="Workspace directory path"),
) -> List[Dict[str, str]]:
    """
    列出实验产出文件

    返回实验运行过程中生成的所有产出文件列表（如ask/intervene结果）。

    Args:
        hypothesis_id: 假设ID
        experiment_id: 实验ID
        workspace_path: 工作区根目录路径

    Returns:
        List[Dict[str, str]]: 产出文件列表，每个文件包含：
            - name: 文件名
            - path: 文件绝对路径
            - type: 文件类型 (ask/intervene)
    """
    workspace = Path(workspace_path)
    exp_path = _get_experiment_path(workspace, hypothesis_id, experiment_id)
    artifacts_dir = exp_path / "run" / "artifacts"

    if not artifacts_dir.exists():
        return []

    artifacts = []
    for file_path in sorted(artifacts_dir.glob("*.md")):
        artifacts.append(
            {
                "name": file_path.name,
                "path": str(file_path),
                "type": "ask" if file_path.name.startswith("ask_") else "intervene",
            }
        )

    return artifacts


@router.get("/{hypothesis_id}/{experiment_id}/artifacts/{artifact_name}")
async def get_artifact(
    hypothesis_id: str,
    experiment_id: str,
    artifact_name: str,
    workspace_path: str = Query(..., description="Workspace directory path"),
) -> Dict[str, str]:
    """
    获取指定产出文件内容

    返回指定产出文件的完整内容。

    Args:
        hypothesis_id: 假设ID
        experiment_id: 实验ID
        artifact_name: 产出文件名（如 ask_0.md, intervene_1.md）
        workspace_path: 工作区根目录路径

    Returns:
        Dict[str, str]: 文件内容，包含：
            - name: 文件名
            - content: 文件完整内容（Markdown格式）

    Raises:
        HTTPException: 404 - 文件不存在
    """
    workspace = Path(workspace_path)
    exp_path = _get_experiment_path(workspace, hypothesis_id, experiment_id)
    artifact_path = exp_path / "run" / "artifacts" / artifact_name

    if not artifact_path.exists():
        raise HTTPException(status_code=404, detail="Artifact not found")

    content = artifact_path.read_text(encoding="utf-8")

    return {
        "name": artifact_name,
        "content": content,
    }
