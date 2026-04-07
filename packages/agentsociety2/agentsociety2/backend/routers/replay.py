"""
Replay data query API for simulation playback.

关联文件：
- @extension/src/replayWebviewProvider.ts - VSCode Replay Webview provider
- @extension/src/webview/replay/ - VSCode Replay Webview React app
"""

from __future__ import annotations

import asyncio
from datetime import datetime
import json
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlmodel import func, select

from ...backend.services.replay_catalog import (
    fetch_dataset_rows,
    get_dataset_by_id,
    load_dataset_catalog,
    query_dataset_rows,
    reflect_dataset_table,
)
from ...storage.replay_metadata import AGENT_PROFILE_DATASET_CAPABILITY

router = APIRouter(prefix="/replay", tags=["replay"])
_DB_CACHE_LOCK = asyncio.Lock()
_DB_SESSIONMAKER_CACHE: dict[str, tuple[int, AsyncEngine, sessionmaker]] = {}


class ExperimentInfo(BaseModel):
    hypothesis_id: str
    experiment_id: str
    total_steps: int
    start_time: Optional[datetime]
    end_time: Optional[datetime]
    agent_count: int


class TimelinePoint(BaseModel):
    step: int
    t: datetime


class AgentProfile(BaseModel):
    id: int
    name: str
    profile: Dict[str, Any] = Field(default_factory=dict)


class ReplayDatasetColumn(BaseModel):
    column_name: str
    sqlite_type: str
    logical_type: Optional[str] = None
    analysis_role: Optional[str] = None
    title: Optional[str] = None
    description: Optional[str] = None
    unit: Optional[str] = None
    nullable: bool
    enum_values: Optional[Any] = None
    example: Optional[Any] = None
    tags: List[str] = Field(default_factory=list)


class ReplayDatasetInfo(BaseModel):
    dataset_id: str
    table_name: str
    module_name: str
    kind: str
    title: str = ""
    description: str = ""
    entity_key: Optional[str] = None
    step_key: Optional[str] = None
    time_key: Optional[str] = None
    default_order: List[str] = Field(default_factory=list)
    capabilities: List[str] = Field(default_factory=list)
    version: int
    created_at: datetime
    columns: List[ReplayDatasetColumn] = Field(default_factory=list)


class ReplayDatasetList(BaseModel):
    datasets: List[ReplayDatasetInfo]


class ReplayDatasetRows(BaseModel):
    dataset_id: str
    columns: List[str]
    rows: List[Dict[str, Any]]
    total: int


class ReplayPanelSchema(BaseModel):
    agent_profile_dataset: Optional[ReplayDatasetInfo] = None
    agent_state_datasets: List[ReplayDatasetInfo] = Field(default_factory=list)
    env_state_datasets: List[ReplayDatasetInfo] = Field(default_factory=list)
    geo_dataset: Optional[ReplayDatasetInfo] = None
    primary_agent_state_dataset_id: Optional[str] = None
    layout_hint: Literal["map", "random"] = "random"
    supports_map: bool = False


class ReplayDatasetPanelRef(BaseModel):
    dataset_id: str
    module_name: str
    title: str = ""


class ReplayPosition(BaseModel):
    agent_id: int
    lng: Optional[float] = None
    lat: Optional[float] = None


class ReplayAgentStateAtStep(BaseModel):
    dataset: ReplayDatasetPanelRef
    rows_by_agent_id: Dict[str, Dict[str, Any]] = Field(default_factory=dict)


class ReplayEnvStateAtStep(BaseModel):
    dataset: ReplayDatasetPanelRef
    row: Optional[Dict[str, Any]] = None


class ReplayStepBundle(BaseModel):
    step: int
    t: Optional[datetime] = None
    layout_hint: Literal["map", "random"] = "random"
    positions: List[ReplayPosition] = Field(default_factory=list)
    agent_state_rows: Dict[str, ReplayAgentStateAtStep] = Field(default_factory=dict)
    env_state_rows: Dict[str, ReplayEnvStateAtStep] = Field(default_factory=dict)


def get_db_path(workspace_path: str, hypothesis_id: str, experiment_id: str) -> Path:
    return (
        Path(workspace_path)
        / f"hypothesis_{hypothesis_id}"
        / f"experiment_{experiment_id}"
        / "run"
        / "sqlite.db"
    )


async def _get_cached_sessionmaker(db_path: Path) -> tuple[sessionmaker, int]:
    resolved_path = db_path.resolve()
    if not resolved_path.exists():
        raise HTTPException(status_code=404, detail=f"Database not found: {db_path}")

    cache_key = str(resolved_path)
    mtime_ns = resolved_path.stat().st_mtime_ns

    async with _DB_CACHE_LOCK:
        cached = _DB_SESSIONMAKER_CACHE.get(cache_key)
        if cached is not None:
            cached_mtime_ns, engine, cached_sessionmaker = cached
            if cached_mtime_ns == mtime_ns:
                return cached_sessionmaker, mtime_ns
            await engine.dispose()

        engine = create_async_engine(
            f"sqlite+aiosqlite:///{resolved_path}",
            echo=False,
        )
        async_session = sessionmaker(
            engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )
        _DB_SESSIONMAKER_CACHE[cache_key] = (mtime_ns, engine, async_session)
        return async_session, mtime_ns


async def get_db_session(db_path: Path):
    async_session, mtime_ns = await _get_cached_sessionmaker(db_path)
    async with async_session() as session:
        session.info["replay_db_path"] = str(db_path.resolve())
        session.info["replay_db_mtime_ns"] = mtime_ns
        yield session


def _dataset_to_response(dataset: Dict[str, Any]) -> ReplayDatasetInfo:
    return ReplayDatasetInfo.model_validate(dataset)


def _dataset_ref(dataset: Dict[str, Any]) -> ReplayDatasetPanelRef:
    return ReplayDatasetPanelRef(
        dataset_id=dataset["dataset_id"],
        module_name=dataset.get("module_name") or "",
        title=dataset.get("title") or "",
    )


def _coerce_datetime(value: Any) -> Optional[datetime]:
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value)
        except ValueError:
            return None
    return None


def _dataset_has_columns(dataset: Dict[str, Any], *column_names: str) -> bool:
    available = {column["column_name"] for column in dataset.get("columns", [])}
    return all(column_name in available for column_name in column_names)


def _split_columns_param(raw_columns: Optional[str]) -> Optional[List[str]]:
    if raw_columns is None:
        return None
    columns = [column.strip() for column in raw_columns.split(",") if column.strip()]
    return columns or None


def _list_agent_state_datasets(datasets: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    items = [
        dataset
        for dataset in datasets
        if dataset.get("kind") == "entity_snapshot"
        and "agent_snapshot" in dataset.get("capabilities", [])
        and dataset.get("entity_key")
        and dataset.get("step_key")
    ]
    items.sort(key=lambda item: item["dataset_id"])
    return items


def _list_env_state_datasets(datasets: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    items = [
        dataset
        for dataset in datasets
        if dataset.get("kind") == "env_snapshot"
        and "env_snapshot" in dataset.get("capabilities", [])
        and dataset.get("step_key")
    ]
    items.sort(key=lambda item: item["dataset_id"])
    return items


def _select_geo_dataset(datasets: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    candidates = [
        dataset
        for dataset in _list_agent_state_datasets(datasets)
        if "geo_point" in dataset.get("capabilities", [])
        and _dataset_has_columns(dataset, "lng", "lat")
    ]
    candidates.sort(key=lambda item: item["dataset_id"])
    return candidates[0] if candidates else None


def _select_primary_agent_state_dataset(
    datasets: List[Dict[str, Any]],
) -> Optional[Dict[str, Any]]:
    agent_state_datasets = _list_agent_state_datasets(datasets)
    if not agent_state_datasets:
        return None

    non_geo_candidates = [
        dataset
        for dataset in agent_state_datasets
        if "geo_point" not in dataset.get("capabilities", [])
    ]
    candidates = non_geo_candidates or agent_state_datasets
    candidates.sort(key=lambda item: item["dataset_id"])
    return candidates[0]


def _select_timeline_dataset(
    datasets: List[Dict[str, Any]],
) -> Optional[Dict[str, Any]]:
    primary_agent_state = _select_primary_agent_state_dataset(datasets)
    if (
        primary_agent_state is not None
        and primary_agent_state.get("step_key")
        and primary_agent_state.get("time_key")
    ):
        return primary_agent_state

    agent_candidates = [
        dataset
        for dataset in _list_agent_state_datasets(datasets)
        if dataset.get("step_key") and dataset.get("time_key")
    ]
    agent_candidates.sort(
        key=lambda item: (
            0 if "geo_point" not in item.get("capabilities", []) else 1,
            item["dataset_id"],
        )
    )
    if agent_candidates:
        return agent_candidates[0]

    env_candidates = [
        dataset
        for dataset in _list_env_state_datasets(datasets)
        if dataset.get("step_key") and dataset.get("time_key")
    ]
    env_candidates.sort(key=lambda item: item["dataset_id"])
    return env_candidates[0] if env_candidates else None


def _find_time_value(
    rows: List[Dict[str, Any]],
    time_key: Optional[str],
) -> Optional[datetime]:
    if not time_key:
        return None
    for row in rows:
        timestamp = _coerce_datetime(row.get(time_key))
        if timestamp is not None:
            return timestamp
    return None


def _build_positions_from_step_rows(
    geo_dataset: Optional[Dict[str, Any]],
    agent_state_groups: Dict[str, ReplayAgentStateAtStep],
) -> List[ReplayPosition]:
    agent_ids: set[int] = set()
    for group in agent_state_groups.values():
        for raw_agent_id in group.rows_by_agent_id.keys():
            try:
                agent_ids.add(int(raw_agent_id))
            except (TypeError, ValueError):
                continue

    positions_by_agent_id: Dict[int, ReplayPosition] = {
        agent_id: ReplayPosition(agent_id=agent_id, lng=None, lat=None)
        for agent_id in sorted(agent_ids)
    }
    if geo_dataset is None:
        return list(positions_by_agent_id.values())

    geo_group = agent_state_groups.get(geo_dataset["dataset_id"])
    if geo_group is None:
        return list(positions_by_agent_id.values())

    for raw_agent_id, row in geo_group.rows_by_agent_id.items():
        try:
            agent_id = int(raw_agent_id)
        except (TypeError, ValueError):
            continue
        positions_by_agent_id[agent_id] = ReplayPosition(
            agent_id=agent_id,
            lng=row.get("lng"),
            lat=row.get("lat"),
        )
    return list(positions_by_agent_id.values())


async def _get_agent_profile_dataset(
    session: AsyncSession,
    datasets: Optional[List[Dict[str, Any]]] = None,
) -> Optional[Dict[str, Any]]:
    catalog = datasets or await load_dataset_catalog(session)
    candidates = [
        dataset
        for dataset in catalog
        if AGENT_PROFILE_DATASET_CAPABILITY in dataset.get("capabilities", [])
        and dataset.get("entity_key")
    ]
    candidates.sort(key=lambda item: item["dataset_id"])
    return candidates[0] if candidates else None


def _parse_profile_payload(raw_profile: Any) -> Dict[str, Any]:
    if isinstance(raw_profile, dict):
        return raw_profile
    if isinstance(raw_profile, str):
        try:
            decoded = json.loads(raw_profile)
        except json.JSONDecodeError:
            return {"raw": raw_profile}
        return decoded if isinstance(decoded, dict) else {}
    return {}


def _resolve_agent_name(agent_id: int, row: Dict[str, Any], profile: Dict[str, Any]) -> str:
    name = row.get("name")
    if isinstance(name, str) and name.strip():
        return name
    profile_name = profile.get("name")
    if isinstance(profile_name, str) and profile_name.strip():
        return profile_name
    return f"Agent_{agent_id}"


async def _load_agent_profiles(
    session: AsyncSession,
    datasets: Optional[List[Dict[str, Any]]] = None,
) -> Dict[int, AgentProfile]:
    catalog = datasets or await load_dataset_catalog(session)
    profile_dataset = await _get_agent_profile_dataset(session, catalog)
    if profile_dataset is not None:
        table = await reflect_dataset_table(session, profile_dataset)
        entity_key = profile_dataset["entity_key"]
        if entity_key in table.c:
            query = select(table).order_by(table.c[entity_key])
            result = await session.execute(query)
            profiles: Dict[int, AgentProfile] = {}
            for row in result.mappings().all():
                raw_id = row.get(entity_key)
                if raw_id is None:
                    continue
                agent_id = int(raw_id)
                profile_payload = _parse_profile_payload(row.get("profile"))
                profiles[agent_id] = AgentProfile(
                    id=agent_id,
                    name=_resolve_agent_name(agent_id, dict(row), profile_payload),
                    profile=profile_payload,
                )
            if profiles:
                return profiles

    identity_dataset = _select_primary_agent_state_dataset(catalog)
    if identity_dataset is None:
        return {}

    table = await reflect_dataset_table(session, identity_dataset)
    entity_key = identity_dataset["entity_key"]
    if entity_key not in table.c:
        return {}

    result = await session.execute(
        select(table.c[entity_key]).distinct().order_by(table.c[entity_key])
    )
    return {
        int(agent_id): AgentProfile(
            id=int(agent_id),
            name=f"Agent_{int(agent_id)}",
            profile={},
        )
        for (agent_id,) in result.all()
        if agent_id is not None
    }


async def _get_experiment_summary(
    session: AsyncSession,
    datasets: List[Dict[str, Any]],
) -> tuple[int, Optional[datetime], Optional[datetime], int]:
    timeline_dataset = _select_timeline_dataset(datasets)
    total_steps = 0
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None

    if timeline_dataset is not None:
        table = await reflect_dataset_table(session, timeline_dataset)
        step_key = timeline_dataset["step_key"]
        time_key = timeline_dataset["time_key"]
        if step_key in table.c and time_key in table.c:
            total_steps = (
                await session.execute(
                    select(func.count(func.distinct(table.c[step_key])))
                )
            ).scalar() or 0
            start_time = _coerce_datetime(
                (await session.execute(select(func.min(table.c[time_key])))).scalar()
            )
            end_time = _coerce_datetime(
                (await session.execute(select(func.max(table.c[time_key])))).scalar()
            )

    profiles = await _load_agent_profiles(session, datasets)
    return int(total_steps), start_time, end_time, len(profiles)


@router.get("/{hypothesis_id}/{experiment_id}/info", response_model=ExperimentInfo)
async def get_experiment_info(
    hypothesis_id: str,
    experiment_id: str,
    workspace_path: str = Query(..., description="Workspace root path"),
) -> ExperimentInfo:
    db_path = get_db_path(workspace_path, hypothesis_id, experiment_id)

    async for session in get_db_session(db_path):
        datasets = await load_dataset_catalog(session)
        total_steps, start_time, end_time, agent_count = await _get_experiment_summary(
            session, datasets
        )
        return ExperimentInfo(
            hypothesis_id=hypothesis_id,
            experiment_id=experiment_id,
            total_steps=total_steps,
            start_time=start_time,
            end_time=end_time,
            agent_count=agent_count,
        )


@router.get("/{hypothesis_id}/{experiment_id}/datasets", response_model=ReplayDatasetList)
async def get_replay_datasets(
    hypothesis_id: str,
    experiment_id: str,
    workspace_path: str = Query(..., description="Workspace root path"),
) -> ReplayDatasetList:
    db_path = get_db_path(workspace_path, hypothesis_id, experiment_id)

    async for session in get_db_session(db_path):
        datasets = await load_dataset_catalog(session)
        return ReplayDatasetList(
            datasets=[_dataset_to_response(dataset) for dataset in datasets]
        )


@router.get(
    "/{hypothesis_id}/{experiment_id}/datasets/{dataset_id}",
    response_model=ReplayDatasetInfo,
)
async def get_replay_dataset(
    hypothesis_id: str,
    experiment_id: str,
    dataset_id: str,
    workspace_path: str = Query(..., description="Workspace root path"),
) -> ReplayDatasetInfo:
    db_path = get_db_path(workspace_path, hypothesis_id, experiment_id)

    async for session in get_db_session(db_path):
        dataset = await get_dataset_by_id(session, dataset_id)
        return _dataset_to_response(dataset)


@router.get(
    "/{hypothesis_id}/{experiment_id}/datasets/{dataset_id}/rows",
    response_model=ReplayDatasetRows,
)
async def get_replay_dataset_rows(
    hypothesis_id: str,
    experiment_id: str,
    dataset_id: str,
    workspace_path: str = Query(..., description="Workspace root path"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    order_by: Optional[str] = Query(None),
    desc_order: bool = Query(False),
    step: Optional[int] = Query(None, description="Exact step filter"),
    entity_id: Optional[int] = Query(None, description="Exact entity filter"),
    start_step: Optional[int] = Query(None, description="Start step (inclusive)"),
    end_step: Optional[int] = Query(None, description="End step (inclusive)"),
    max_step: Optional[int] = Query(None, description="Maximum step (inclusive)"),
    columns: Optional[str] = Query(None, description="Comma-separated column whitelist"),
    latest_per_entity: bool = Query(
        False,
        description="Return only the latest row per entity",
    ),
) -> ReplayDatasetRows:
    db_path = get_db_path(workspace_path, hypothesis_id, experiment_id)

    async for session in get_db_session(db_path):
        dataset = await get_dataset_by_id(session, dataset_id)
        rows = await query_dataset_rows(
            session,
            dataset,
            page=page,
            page_size=page_size,
            order_by=order_by,
            desc=desc_order,
            step=step,
            entity_id=entity_id,
            start_step=start_step,
            end_step=end_step,
            max_step=max_step,
            columns=_split_columns_param(columns),
            latest_per_entity=latest_per_entity,
        )
        return ReplayDatasetRows(
            dataset_id=dataset_id,
            columns=rows["columns"],
            rows=rows["rows"],
            total=rows["total"],
        )


@router.get(
    "/{hypothesis_id}/{experiment_id}/panel-schema",
    response_model=ReplayPanelSchema,
)
async def get_replay_panel_schema(
    hypothesis_id: str,
    experiment_id: str,
    workspace_path: str = Query(..., description="Workspace root path"),
) -> ReplayPanelSchema:
    db_path = get_db_path(workspace_path, hypothesis_id, experiment_id)

    async for session in get_db_session(db_path):
        datasets = await load_dataset_catalog(session)
        agent_profile_dataset = await _get_agent_profile_dataset(session, datasets)
        agent_state_datasets = _list_agent_state_datasets(datasets)
        env_state_datasets = _list_env_state_datasets(datasets)
        geo_dataset = _select_geo_dataset(datasets)
        primary_agent_state_dataset = _select_primary_agent_state_dataset(datasets)
        return ReplayPanelSchema(
            agent_profile_dataset=(
                _dataset_to_response(agent_profile_dataset)
                if agent_profile_dataset is not None
                else None
            ),
            agent_state_datasets=[
                _dataset_to_response(dataset) for dataset in agent_state_datasets
            ],
            env_state_datasets=[
                _dataset_to_response(dataset) for dataset in env_state_datasets
            ],
            geo_dataset=(
                _dataset_to_response(geo_dataset) if geo_dataset is not None else None
            ),
            primary_agent_state_dataset_id=(
                primary_agent_state_dataset["dataset_id"]
                if primary_agent_state_dataset is not None
                else None
            ),
            layout_hint="map" if geo_dataset is not None else "random",
            supports_map=geo_dataset is not None,
        )


@router.get(
    "/{hypothesis_id}/{experiment_id}/steps/{step}/bundle",
    response_model=ReplayStepBundle,
)
async def get_replay_step_bundle(
    hypothesis_id: str,
    experiment_id: str,
    step: int,
    workspace_path: str = Query(..., description="Workspace root path"),
) -> ReplayStepBundle:
    db_path = get_db_path(workspace_path, hypothesis_id, experiment_id)

    async for session in get_db_session(db_path):
        datasets = await load_dataset_catalog(session)
        agent_state_datasets = _list_agent_state_datasets(datasets)
        env_state_datasets = _list_env_state_datasets(datasets)
        geo_dataset = _select_geo_dataset(datasets)
        layout_hint: Literal["map", "random"] = (
            "map" if geo_dataset is not None else "random"
        )

        step_timestamp: Optional[datetime] = None
        agent_state_rows: Dict[str, ReplayAgentStateAtStep] = {}
        for dataset in agent_state_datasets:
            rows_result = await fetch_dataset_rows(session, dataset, step=step)
            entity_key = dataset.get("entity_key")
            if not entity_key:
                continue
            rows_by_agent_id: Dict[str, Dict[str, Any]] = {}
            for row in rows_result["rows"]:
                raw_agent_id = row.get(entity_key)
                if raw_agent_id is None:
                    continue
                rows_by_agent_id[str(raw_agent_id)] = row
            agent_state_rows[dataset["dataset_id"]] = ReplayAgentStateAtStep(
                dataset=_dataset_ref(dataset),
                rows_by_agent_id=rows_by_agent_id,
            )
            if step_timestamp is None:
                step_timestamp = _find_time_value(
                    rows_result["rows"], dataset.get("time_key")
                )

        env_state_rows: Dict[str, ReplayEnvStateAtStep] = {}
        for dataset in env_state_datasets:
            rows_result = await fetch_dataset_rows(session, dataset, step=step, limit=1)
            row = rows_result["rows"][0] if rows_result["rows"] else None
            env_state_rows[dataset["dataset_id"]] = ReplayEnvStateAtStep(
                dataset=_dataset_ref(dataset),
                row=row,
            )
            if step_timestamp is None:
                step_timestamp = _find_time_value(
                    rows_result["rows"], dataset.get("time_key")
                )

        positions = _build_positions_from_step_rows(geo_dataset, agent_state_rows)
        return ReplayStepBundle(
            step=step,
            t=step_timestamp,
            layout_hint=layout_hint,
            positions=positions,
            agent_state_rows=agent_state_rows,
            env_state_rows=env_state_rows,
        )


@router.get("/{hypothesis_id}/{experiment_id}/timeline", response_model=List[TimelinePoint])
async def get_timeline(
    hypothesis_id: str,
    experiment_id: str,
    workspace_path: str = Query(..., description="Workspace root path"),
) -> List[TimelinePoint]:
    db_path = get_db_path(workspace_path, hypothesis_id, experiment_id)

    async for session in get_db_session(db_path):
        datasets = await load_dataset_catalog(session)
        timeline_dataset = _select_timeline_dataset(datasets)
        if timeline_dataset is None:
            return []

        table = await reflect_dataset_table(session, timeline_dataset)
        step_key = timeline_dataset["step_key"]
        time_key = timeline_dataset["time_key"]
        if step_key not in table.c or time_key not in table.c:
            return []

        result = await session.execute(
            select(table.c[step_key], func.min(table.c[time_key]))
            .group_by(table.c[step_key])
            .order_by(table.c[step_key])
        )
        timeline: List[TimelinePoint] = []
        for step_value, time_value in result.all():
            timestamp = _coerce_datetime(time_value)
            if timestamp is None:
                continue
            timeline.append(TimelinePoint(step=int(step_value), t=timestamp))
        return timeline


@router.get(
    "/{hypothesis_id}/{experiment_id}/agents/profiles",
    response_model=List[AgentProfile],
)
async def get_agent_profiles(
    hypothesis_id: str,
    experiment_id: str,
    workspace_path: str = Query(..., description="Workspace root path"),
) -> List[AgentProfile]:
    db_path = get_db_path(workspace_path, hypothesis_id, experiment_id)

    async for session in get_db_session(db_path):
        datasets = await load_dataset_catalog(session)
        profiles = await _load_agent_profiles(session, datasets)
        return sorted(profiles.values(), key=lambda profile: profile.id)
