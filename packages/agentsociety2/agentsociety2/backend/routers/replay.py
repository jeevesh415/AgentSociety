"""
Replay data query API for simulation playback.

关联文件：
- @extension/src/replayWebviewProvider.ts - 前端 Replay Webview（调用此 API）
- @extension/src/webview/replay/ - 前端 React 组件
"""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import Table, inspect as sa_inspect
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlmodel import desc, func, select

from ...backend.services.replay_catalog import (
    find_dataset_by_capability,
    get_dataset_by_id,
    load_dataset_catalog,
    query_dataset_rows,
    reflect_dataset_table,
)
from ...storage.models import AgentDialog, AgentProfile, AgentStatus

router = APIRouter(prefix="/replay", tags=["replay"])


class ExperimentInfo(BaseModel):
    hypothesis_id: str
    experiment_id: str
    total_steps: int
    start_time: Optional[datetime]
    end_time: Optional[datetime]
    agent_count: int
    has_social: bool = False


class TimelinePoint(BaseModel):
    step: int
    t: datetime


class AgentStatusResponse(BaseModel):
    id: int
    step: int
    t: datetime
    lng: Optional[float]
    lat: Optional[float]
    action: Optional[str]
    status: Dict[str, Any]


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


class SocialNetworkNode(BaseModel):
    user_id: int
    username: str


class SocialNetworkEdge(BaseModel):
    source: int
    target: int


class SocialNetwork(BaseModel):
    nodes: List[SocialNetworkNode]
    edges: List[SocialNetworkEdge]


class SocialUser(BaseModel):
    user_id: int
    username: str
    bio: Optional[str] = None
    created_at: Optional[datetime] = None
    followers_count: Optional[int] = None
    following_count: Optional[int] = None
    posts_count: Optional[int] = None
    profile: Optional[Any] = None


class SocialPost(BaseModel):
    post_id: int
    step: int
    author_id: int
    content: str
    post_type: str
    parent_id: Optional[int] = None
    created_at: Optional[datetime] = None
    likes_count: Optional[int] = 0
    reposts_count: Optional[int] = 0
    comments_count: Optional[int] = 0
    view_count: Optional[int] = 0
    tags: Optional[Any] = None
    topic_category: Optional[str] = None


class SocialComment(BaseModel):
    comment_id: int
    step: int
    post_id: int
    author_id: int
    content: str
    created_at: Optional[datetime] = None
    likes_count: Optional[int] = 0


class SocialEvent(BaseModel):
    event_id: int
    step: int
    t: Optional[datetime] = None
    sender_id: int
    sender_name: str
    action: str
    content: Optional[str] = None
    receiver_id: Optional[int] = None
    receiver_name: Optional[str] = None
    target_id: Optional[int] = None
    target_author_id: Optional[int] = None
    target_author_name: Optional[str] = None
    summary: str


class SocialActivityResponse(BaseModel):
    step: int
    highlighted_agent_ids: List[int]


SOCIAL_POST_ACTIONS = {"post", "repost"}
SOCIAL_TARGETED_ACTIONS = {"follow", "unfollow", "like", "unlike", "comment", "repost"}


def get_db_path(workspace_path: str, hypothesis_id: str, experiment_id: str) -> Path:
    return (
        Path(workspace_path)
        / f"hypothesis_{hypothesis_id}"
        / f"experiment_{experiment_id}"
        / "run"
        / "sqlite.db"
    )


async def get_db_session(db_path: Path):
    if not db_path.exists():
        raise HTTPException(status_code=404, detail=f"Database not found: {db_path}")

    engine = create_async_engine(f"sqlite+aiosqlite:///{db_path}", echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as session:
        yield session

    await engine.dispose()


async def _table_exists(session: AsyncSession, table_name: str) -> bool:
    def _do(sync_session):
        return table_name in sa_inspect(sync_session.connection()).get_table_names()

    return bool(await session.run_sync(_do))


def _dataset_to_response(dataset: Dict[str, Any]) -> ReplayDatasetInfo:
    return ReplayDatasetInfo.model_validate(dataset)


def _build_agent_status_response(
    status: AgentStatus,
    *,
    lng: Optional[float] = None,
    lat: Optional[float] = None,
) -> AgentStatusResponse:
    return AgentStatusResponse(
        id=status.id,
        step=status.step,
        t=status.t,
        lng=lng,
        lat=lat,
        action=status.action,
        status=status.status or {},
    )


def _dataset_has_columns(dataset: Dict[str, Any], *column_names: str) -> bool:
    available = {column["column_name"] for column in dataset.get("columns", [])}
    return all(column_name in available for column_name in column_names)


async def _find_optional_dataset_by_capability(
    session: AsyncSession,
    capability: str,
    *,
    kind: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    try:
        return await find_dataset_by_capability(session, capability, kind=kind)
    except HTTPException as exc:
        if exc.status_code == 404:
            return None
        raise


async def _get_geo_dataset(session: AsyncSession) -> Optional[Dict[str, Any]]:
    datasets = await load_dataset_catalog(session)
    candidates = [
        dataset
        for dataset in datasets
        if "geo_point" in dataset.get("capabilities", [])
        and dataset.get("kind") == "entity_snapshot"
        and dataset.get("entity_key")
        and dataset.get("step_key")
        and _dataset_has_columns(dataset, "lng", "lat")
    ]
    candidates.sort(key=lambda item: item["dataset_id"])
    return candidates[0] if candidates else None


async def _get_trajectory_dataset(session: AsyncSession) -> Optional[Dict[str, Any]]:
    datasets = await load_dataset_catalog(session)
    candidates = [
        dataset
        for dataset in datasets
        if "trajectory" in dataset.get("capabilities", [])
        and dataset.get("kind") == "entity_snapshot"
        and dataset.get("entity_key")
        and dataset.get("step_key")
        and dataset.get("time_key")
        and _dataset_has_columns(dataset, "lng", "lat")
    ]
    candidates.sort(key=lambda item: item["dataset_id"])
    return candidates[0] if candidates else None


async def _get_social_datasets(
    session: AsyncSession,
) -> tuple[Optional[Dict[str, Any]], Optional[Dict[str, Any]]]:
    event_dataset = await _find_optional_dataset_by_capability(
        session,
        "social_event",
        kind="event_stream",
    )
    if event_dataset is None:
        return None, None

    datasets = await load_dataset_catalog(session)
    state_candidates = [
        dataset
        for dataset in datasets
        if dataset.get("module_name") == event_dataset.get("module_name")
        and dataset.get("kind") == "entity_snapshot"
        and "agent_snapshot" in dataset.get("capabilities", [])
        and dataset.get("entity_key")
    ]
    state_candidates.sort(key=lambda item: item["dataset_id"])
    return event_dataset, (state_candidates[0] if state_candidates else None)


async def _load_dataset_mappings(
    session: AsyncSession,
    dataset: Dict[str, Any],
    *,
    max_step: Optional[int] = None,
) -> List[Dict[str, Any]]:
    table = await reflect_dataset_table(session, dataset)
    query = select(table)
    step_key = dataset.get("step_key")
    if max_step is not None and step_key and step_key in table.c:
        query = query.where(table.c[step_key] <= max_step)

    order_columns = [
        table.c[column_name]
        for column_name in dataset.get("default_order", [])
        if column_name in table.c
    ]
    if not order_columns and step_key and step_key in table.c:
        order_columns = [table.c[step_key]]
    if order_columns:
        query = query.order_by(*order_columns)

    result = await session.execute(query)
    return [dict(row) for row in result.mappings().all()]


async def _load_social_events(
    session: AsyncSession,
    *,
    max_step: Optional[int] = None,
) -> List[Dict[str, Any]]:
    event_dataset, _ = await _get_social_datasets(session)
    if event_dataset is None:
        return []
    return await _load_dataset_mappings(session, event_dataset, max_step=max_step)


async def _load_agent_profiles(session: AsyncSession) -> Dict[int, AgentProfile]:
    result = await session.execute(select(AgentProfile))
    return {profile.id: profile for profile in result.scalars().all()}


def _display_name(profile: Optional[AgentProfile], user_id: int) -> str:
    if profile is not None and profile.name:
        return profile.name
    return f"User {user_id}"


def _extract_bio(profile: Optional[AgentProfile]) -> Optional[str]:
    if profile is None or not isinstance(profile.profile, dict):
        return None
    for key in ("bio", "background_story", "description"):
        value = profile.profile.get(key)
        if isinstance(value, str) and value.strip():
            return value
    return None


def _build_post_author_map(events: List[Dict[str, Any]]) -> Dict[int, int]:
    post_author_map: Dict[int, int] = {}
    for event in events:
        action = str(event.get("action") or "")
        target_id = event.get("target_id")
        if action == "post" and target_id is not None:
            post_author_map[int(target_id)] = int(event["sender_id"])
        elif action == "repost":
            post_author_map[int(event["id"])] = int(event["sender_id"])
    return post_author_map


@router.get("/{hypothesis_id}/{experiment_id}/info", response_model=ExperimentInfo)
async def get_experiment_info(
    hypothesis_id: str,
    experiment_id: str,
    workspace_path: str = Query(..., description="Workspace root path"),
) -> ExperimentInfo:
    db_path = get_db_path(workspace_path, hypothesis_id, experiment_id)

    async for session in get_db_session(db_path):
        total_steps = (
            await session.execute(select(func.count(func.distinct(AgentStatus.step))))
        ).scalar() or 0
        start_time = (await session.execute(select(func.min(AgentStatus.t)))).scalar()
        end_time = (await session.execute(select(func.max(AgentStatus.t)))).scalar()
        agent_count = (await session.execute(select(func.count(AgentProfile.id)))).scalar() or 0

        datasets = await load_dataset_catalog(session)
        has_social = any(
            "social_event" in dataset.get("capabilities", [])
            for dataset in datasets
        )
        return ExperimentInfo(
            hypothesis_id=hypothesis_id,
            experiment_id=experiment_id,
            total_steps=total_steps,
            start_time=start_time,
            end_time=end_time,
            agent_count=agent_count,
            has_social=has_social,
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
        )
        return ReplayDatasetRows(
            dataset_id=dataset_id,
            columns=rows["columns"],
            rows=rows["rows"],
            total=rows["total"],
        )


@router.get("/{hypothesis_id}/{experiment_id}/timeline", response_model=List[TimelinePoint])
async def get_timeline(
    hypothesis_id: str,
    experiment_id: str,
    workspace_path: str = Query(..., description="Workspace root path"),
) -> List[TimelinePoint]:
    db_path = get_db_path(workspace_path, hypothesis_id, experiment_id)

    async for session in get_db_session(db_path):
        result = await session.execute(
            select(AgentStatus.step, AgentStatus.t).distinct().order_by(AgentStatus.step)
        )
        return [TimelinePoint(step=row[0], t=row[1]) for row in result.all()]


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
        result = await session.execute(select(AgentProfile))
        return result.scalars().all()


@router.get(
    "/{hypothesis_id}/{experiment_id}/agents/status",
    response_model=List[AgentStatusResponse],
)
async def get_agents_status_at_step(
    hypothesis_id: str,
    experiment_id: str,
    workspace_path: str = Query(..., description="Workspace root path"),
    step: Optional[int] = Query(None, description="Specific step to query. If omitted, use latest step."),
) -> List[AgentStatusResponse]:
    db_path = get_db_path(workspace_path, hypothesis_id, experiment_id)

    async for session in get_db_session(db_path):
        if step is None:
            step = (await session.execute(select(func.max(AgentStatus.step)))).scalar()
            if step is None:
                return []

        geo_dataset = await _get_geo_dataset(session)
        if geo_dataset is None:
            result = await session.execute(
                select(AgentStatus)
                .where(AgentStatus.step == step)
                .order_by(AgentStatus.id)
            )
            return [_build_agent_status_response(status) for status in result.scalars().all()]

        geo_table = await reflect_dataset_table(session, geo_dataset)
        entity_key = geo_dataset["entity_key"]
        step_key = geo_dataset["step_key"]
        if entity_key not in geo_table.c or step_key not in geo_table.c:
            result = await session.execute(
                select(AgentStatus)
                .where(AgentStatus.step == step)
                .order_by(AgentStatus.id)
            )
            return [_build_agent_status_response(status) for status in result.scalars().all()]

        result = await session.execute(
            select(AgentStatus, geo_table.c.lng, geo_table.c.lat)
            .select_from(AgentStatus)
            .outerjoin(
                geo_table,
                (AgentStatus.id == geo_table.c[entity_key])
                & (AgentStatus.step == geo_table.c[step_key]),
            )
            .where(AgentStatus.step == step)
            .order_by(AgentStatus.id)
        )
        return [
            _build_agent_status_response(status, lng=lng, lat=lat)
            for status, lng, lat in result.all()
        ]


@router.get(
    "/{hypothesis_id}/{experiment_id}/agents/{agent_id}/status",
    response_model=List[AgentStatusResponse],
)
async def get_agent_status_history(
    hypothesis_id: str,
    experiment_id: str,
    agent_id: int,
    workspace_path: str = Query(..., description="Workspace root path"),
) -> List[AgentStatusResponse]:
    db_path = get_db_path(workspace_path, hypothesis_id, experiment_id)

    async for session in get_db_session(db_path):
        geo_dataset = await _get_geo_dataset(session)
        if geo_dataset is None:
            result = await session.execute(
                select(AgentStatus)
                .where(AgentStatus.id == agent_id)
                .order_by(AgentStatus.step)
            )
            return [_build_agent_status_response(status) for status in result.scalars().all()]

        geo_table = await reflect_dataset_table(session, geo_dataset)
        entity_key = geo_dataset["entity_key"]
        step_key = geo_dataset["step_key"]
        if entity_key not in geo_table.c or step_key not in geo_table.c:
            result = await session.execute(
                select(AgentStatus)
                .where(AgentStatus.id == agent_id)
                .order_by(AgentStatus.step)
            )
            return [_build_agent_status_response(status) for status in result.scalars().all()]

        result = await session.execute(
            select(AgentStatus, geo_table.c.lng, geo_table.c.lat)
            .select_from(AgentStatus)
            .outerjoin(
                geo_table,
                (AgentStatus.id == geo_table.c[entity_key])
                & (AgentStatus.step == geo_table.c[step_key]),
            )
            .where(AgentStatus.id == agent_id)
            .order_by(AgentStatus.step)
        )
        return [
            _build_agent_status_response(status, lng=lng, lat=lat)
            for status, lng, lat in result.all()
        ]


@router.get(
    "/{hypothesis_id}/{experiment_id}/agents/{agent_id}/trajectory",
    response_model=List[Dict[str, Any]],
)
async def get_agent_trajectory(
    hypothesis_id: str,
    experiment_id: str,
    agent_id: int,
    workspace_path: str = Query(..., description="Workspace root path"),
    start_step: Optional[int] = Query(None, description="Start step (inclusive)"),
    end_step: Optional[int] = Query(None, description="End step (inclusive)"),
) -> List[Dict[str, Any]]:
    db_path = get_db_path(workspace_path, hypothesis_id, experiment_id)

    async for session in get_db_session(db_path):
        dataset = await _get_trajectory_dataset(session)
        if dataset is None:
            return []

        table = await reflect_dataset_table(session, dataset)
        entity_key = dataset["entity_key"]
        step_key = dataset["step_key"]
        time_key = dataset["time_key"]
        required = [entity_key, step_key, time_key, "lng", "lat"]
        if any(column_name not in table.c for column_name in required):
            return []

        query = select(
            table.c[step_key],
            table.c[time_key],
            table.c.lng,
            table.c.lat,
        ).where(table.c[entity_key] == agent_id)
        if start_step is not None:
            query = query.where(table.c[step_key] >= start_step)
        if end_step is not None:
            query = query.where(table.c[step_key] <= end_step)
        query = query.order_by(table.c[step_key])

        result = await session.execute(query)
        return [
            {"step": step_value, "t": time_value, "lng": lng, "lat": lat}
            for step_value, time_value, lng, lat in result.all()
        ]


@router.get(
    "/{hypothesis_id}/{experiment_id}/agents/{agent_id}/dialog",
    response_model=List[AgentDialog],
)
async def get_agent_dialogs(
    hypothesis_id: str,
    experiment_id: str,
    agent_id: int,
    workspace_path: str = Query(..., description="Workspace root path"),
    dialog_type: Optional[int] = Query(
        None,
        description="Dialog type filter: 0=thought, 1=agent-to-agent, 2=user",
    ),
) -> List[AgentDialog]:
    db_path = get_db_path(workspace_path, hypothesis_id, experiment_id)

    async for session in get_db_session(db_path):
        if not await _table_exists(session, AgentDialog.__tablename__):
            return []
        query = select(AgentDialog).where(AgentDialog.agent_id == agent_id)
        if dialog_type is not None:
            query = query.where(AgentDialog.type == dialog_type)
        query = query.order_by(AgentDialog.step, AgentDialog.id)
        result = await session.execute(query)
        return result.scalars().all()


@router.get(
    "/{hypothesis_id}/{experiment_id}/dialogs/step/{step}",
    response_model=List[AgentDialog],
)
async def get_dialogs_at_step(
    hypothesis_id: str,
    experiment_id: str,
    step: int,
    workspace_path: str = Query(..., description="Workspace root path"),
    dialog_type: Optional[int] = Query(
        None,
        description="Dialog type filter: 0=thought/reflection; V2 currently uses only type 0",
    ),
) -> List[AgentDialog]:
    db_path = get_db_path(workspace_path, hypothesis_id, experiment_id)

    async for session in get_db_session(db_path):
        if not await _table_exists(session, AgentDialog.__tablename__):
            return []
        query = select(AgentDialog).where(AgentDialog.step == step)
        if dialog_type is not None:
            query = query.where(AgentDialog.type == dialog_type)
        query = query.order_by(AgentDialog.id)
        result = await session.execute(query)
        return result.scalars().all()


@router.get(
    "/{hypothesis_id}/{experiment_id}/social/users/{user_id}",
    response_model=SocialUser,
)
async def get_social_user(
    hypothesis_id: str,
    experiment_id: str,
    user_id: int,
    workspace_path: str = Query(..., description="Workspace root path"),
) -> SocialUser:
    db_path = get_db_path(workspace_path, hypothesis_id, experiment_id)

    async for session in get_db_session(db_path):
        _, state_dataset = await _get_social_datasets(session)
        profiles = await _load_agent_profiles(session)
        profile = profiles.get(user_id)
        latest_state: Dict[str, Any] = {}

        if state_dataset is not None:
            table = await reflect_dataset_table(session, state_dataset)
            entity_key = state_dataset["entity_key"]
            step_key = state_dataset.get("step_key")
            query = select(table).where(table.c[entity_key] == user_id)
            if step_key and step_key in table.c:
                query = query.order_by(desc(table.c[step_key]))
            result = await session.execute(query.limit(1))
            state_row = result.mappings().first()
            if state_row is not None:
                latest_state = dict(state_row)

        if profile is None and not latest_state:
            raise HTTPException(status_code=404, detail="Social user not found")

        return SocialUser(
            user_id=user_id,
            username=_display_name(profile, user_id),
            bio=_extract_bio(profile),
            created_at=None,
            followers_count=int(latest_state.get("followers_count") or 0),
            following_count=int(latest_state.get("following_count") or 0),
            posts_count=int(latest_state.get("posts_count") or 0),
            profile=profile.profile if profile is not None else None,
        )


@router.get(
    "/{hypothesis_id}/{experiment_id}/social/users/{user_id}/posts",
    response_model=List[SocialPost],
)
async def get_social_posts(
    hypothesis_id: str,
    experiment_id: str,
    user_id: int,
    workspace_path: str = Query(..., description="Workspace root path"),
    max_step: Optional[int] = Query(
        None,
        description="Only posts with step <= max_step (timeline step)",
    ),
    limit: int = Query(200, ge=1, le=500),
) -> List[SocialPost]:
    db_path = get_db_path(workspace_path, hypothesis_id, experiment_id)

    async for session in get_db_session(db_path):
        events = await _load_social_events(session, max_step=max_step)
        latest_like_actions: Dict[tuple[int, int], str] = {}
        comments_count: defaultdict[int, int] = defaultdict(int)
        reposts_count: defaultdict[int, int] = defaultdict(int)
        posts: List[SocialPost] = []

        for event in events:
            action = str(event.get("action") or "")
            target_id = event.get("target_id")
            if target_id is not None:
                target_post_id = int(target_id)
                if action in {"like", "unlike"}:
                    latest_like_actions[(int(event["sender_id"]), target_post_id)] = action
                elif action == "comment":
                    comments_count[target_post_id] += 1
                elif action == "repost":
                    reposts_count[target_post_id] += 1

            if int(event["sender_id"]) != user_id or action not in SOCIAL_POST_ACTIONS:
                continue

            if action == "post" and target_id is not None:
                post_id_value = int(target_id)
                post_type = "original"
                parent_id = None
            else:
                post_id_value = int(event["id"])
                post_type = "repost"
                parent_id = int(target_id) if target_id is not None else None

            posts.append(
                SocialPost(
                    post_id=post_id_value,
                    step=int(event["step"]),
                    author_id=int(event["sender_id"]),
                    content=str(event.get("content") or ""),
                    post_type=post_type,
                    parent_id=parent_id,
                    created_at=event.get("t"),
                    likes_count=0,
                    reposts_count=0,
                    comments_count=0,
                    view_count=0,
                    tags=[],
                    topic_category=None,
                )
            )

        likes_count: defaultdict[int, int] = defaultdict(int)
        for (_, post_id_value), action in latest_like_actions.items():
            if action == "like":
                likes_count[post_id_value] += 1

        for post in posts:
            post.likes_count = likes_count.get(post.post_id, 0)
            post.comments_count = comments_count.get(post.post_id, 0)
            post.reposts_count = reposts_count.get(post.post_id, 0)

        posts.sort(
            key=lambda post: (post.step, post.created_at or datetime.min, post.post_id),
            reverse=True,
        )
        return posts[:limit]


@router.get(
    "/{hypothesis_id}/{experiment_id}/social/posts",
    response_model=List[SocialPost],
)
async def get_all_social_posts(
    hypothesis_id: str,
    experiment_id: str,
    workspace_path: str = Query(..., description="Workspace root path"),
    max_step: Optional[int] = Query(
        None,
        description="Only posts with step <= max_step (timeline step)",
    ),
    limit: int = Query(500, ge=1, le=2000),
) -> List[SocialPost]:
    db_path = get_db_path(workspace_path, hypothesis_id, experiment_id)

    async for session in get_db_session(db_path):
        events = await _load_social_events(session, max_step=max_step)
        latest_like_actions: Dict[tuple[int, int], str] = {}
        comments_count: defaultdict[int, int] = defaultdict(int)
        reposts_count: defaultdict[int, int] = defaultdict(int)
        posts: List[SocialPost] = []

        for event in events:
            action = str(event.get("action") or "")
            target_id = event.get("target_id")
            if target_id is not None:
                target_post_id = int(target_id)
                if action in {"like", "unlike"}:
                    latest_like_actions[(int(event["sender_id"]), target_post_id)] = action
                elif action == "comment":
                    comments_count[target_post_id] += 1
                elif action == "repost":
                    reposts_count[target_post_id] += 1

            if action not in SOCIAL_POST_ACTIONS:
                continue

            if action == "post" and target_id is not None:
                post_id_value = int(target_id)
                post_type = "original"
                parent_id = None
            else:
                post_id_value = int(event["id"])
                post_type = "repost"
                parent_id = int(target_id) if target_id is not None else None

            posts.append(
                SocialPost(
                    post_id=post_id_value,
                    step=int(event["step"]),
                    author_id=int(event["sender_id"]),
                    content=str(event.get("content") or ""),
                    post_type=post_type,
                    parent_id=parent_id,
                    created_at=event.get("t"),
                    likes_count=0,
                    reposts_count=0,
                    comments_count=0,
                    view_count=0,
                    tags=[],
                    topic_category=None,
                )
            )

        likes_count: defaultdict[int, int] = defaultdict(int)
        for (_, post_id_value), action in latest_like_actions.items():
            if action == "like":
                likes_count[post_id_value] += 1

        for post in posts:
            post.likes_count = likes_count.get(post.post_id, 0)
            post.comments_count = comments_count.get(post.post_id, 0)
            post.reposts_count = reposts_count.get(post.post_id, 0)

        posts.sort(
            key=lambda post: (post.step, post.created_at or datetime.min, post.post_id),
            reverse=True,
        )
        return posts[:limit]


@router.get(
    "/{hypothesis_id}/{experiment_id}/social/posts/{post_id}/comments",
    response_model=List[SocialComment],
)
async def get_post_comments(
    hypothesis_id: str,
    experiment_id: str,
    post_id: int,
    workspace_path: str = Query(..., description="Workspace root path"),
) -> List[SocialComment]:
    db_path = get_db_path(workspace_path, hypothesis_id, experiment_id)

    async for session in get_db_session(db_path):
        events = await _load_social_events(session)
        comments = [event for event in events if str(event.get("action")) == "comment" and int(event.get("target_id") or -1) == post_id]
        return [
            SocialComment(
                comment_id=int(event["id"]),
                step=int(event["step"]),
                post_id=int(event["target_id"]),
                author_id=int(event["sender_id"]),
                content=str(event.get("content") or ""),
                created_at=event.get("t"),
                likes_count=0,
            )
            for event in comments
        ]


@router.get(
    "/{hypothesis_id}/{experiment_id}/social/users/{user_id}/events",
    response_model=List[SocialEvent],
)
async def get_social_user_events(
    hypothesis_id: str,
    experiment_id: str,
    user_id: int,
    workspace_path: str = Query(..., description="Workspace root path"),
    max_step: Optional[int] = Query(
        None,
        description="Only events with step <= max_step (timeline step)",
    ),
    limit: int = Query(200, ge=1, le=1000),
) -> List[SocialEvent]:
    db_path = get_db_path(workspace_path, hypothesis_id, experiment_id)

    async for session in get_db_session(db_path):
        profiles = await _load_agent_profiles(session)
        events = await _load_social_events(session, max_step=max_step)
        post_author_map = _build_post_author_map(events)
        related_events = []

        for event in events:
            sender_id = int(event["sender_id"])
            receiver_id = (
                int(event["receiver_id"])
                if event.get("receiver_id") is not None
                else None
            )
            target_id = (
                int(event["target_id"]) if event.get("target_id") is not None else None
            )
            target_author_id = (
                post_author_map.get(target_id) if target_id is not None else None
            )
            if user_id in {sender_id, receiver_id, target_author_id}:
                related_events.append(event)

        related_events.sort(
            key=lambda event: (
                int(event["step"]),
                event.get("t") or datetime.min,
                int(event["id"]),
            ),
            reverse=True,
        )

        response: List[SocialEvent] = []
        for event in related_events[:limit]:
            sender_id = int(event["sender_id"])
            receiver_id = (
                int(event["receiver_id"])
                if event.get("receiver_id") is not None
                else None
            )
            target_id = (
                int(event["target_id"]) if event.get("target_id") is not None else None
            )
            target_author_id = (
                post_author_map.get(target_id) if target_id is not None else None
            )
            sender_name = _display_name(profiles.get(sender_id), sender_id)
            receiver_name = (
                _display_name(profiles.get(receiver_id), receiver_id)
                if receiver_id is not None
                else None
            )
            target_author_name = (
                _display_name(profiles.get(target_author_id), target_author_id)
                if target_author_id is not None
                else None
            )
            action = str(event["action"])
            content = str(event.get("content") or "").strip() or None

            if sender_id == user_id:
                summary_map = {
                    "post": "Published a post",
                    "repost": f"Reposted post #{target_id}",
                    "comment": f"Commented on post #{target_id}",
                    "like": f"Liked post #{target_id}",
                    "unlike": f"Removed like from post #{target_id}",
                    "follow": f"Followed {receiver_name}",
                    "unfollow": f"Unfollowed {receiver_name}",
                }
                summary = summary_map.get(action, f"Performed {action}")
            elif receiver_id == user_id:
                summary_map = {
                    "follow": f"{sender_name} followed you",
                    "unfollow": f"{sender_name} unfollowed you",
                }
                summary = summary_map.get(action, f"{sender_name} triggered {action}")
            elif target_author_id == user_id:
                summary_map = {
                    "like": f"{sender_name} liked your post #{target_id}",
                    "unlike": f"{sender_name} removed like from your post #{target_id}",
                    "comment": f"{sender_name} commented on your post #{target_id}",
                    "repost": f"{sender_name} reposted your post #{target_id}",
                }
                summary = summary_map.get(action, f"{sender_name} acted on your post")
            else:
                summary_map = {
                    "post": f"{sender_name} published a post",
                    "repost": f"{sender_name} reposted post #{target_id}",
                    "comment": f"{sender_name} commented on post #{target_id}",
                    "like": f"{sender_name} liked post #{target_id}",
                    "unlike": f"{sender_name} removed like from post #{target_id}",
                    "follow": f"{sender_name} followed {receiver_name}",
                    "unfollow": f"{sender_name} unfollowed {receiver_name}",
                }
                summary = summary_map.get(action, f"{sender_name} performed {action}")

            if content:
                summary = f"{summary}: {content}"

            response.append(
                SocialEvent(
                    event_id=int(event["id"]),
                    step=int(event["step"]),
                    t=event.get("t"),
                    sender_id=sender_id,
                    sender_name=sender_name,
                    action=action,
                    content=content,
                    receiver_id=receiver_id,
                    receiver_name=receiver_name,
                    target_id=target_id,
                    target_author_id=target_author_id,
                    target_author_name=target_author_name,
                    summary=summary,
                )
            )
        return response


@router.get(
    "/{hypothesis_id}/{experiment_id}/social/network",
    response_model=SocialNetwork,
)
async def get_social_network(
    hypothesis_id: str,
    experiment_id: str,
    workspace_path: str = Query(..., description="Workspace root path"),
) -> SocialNetwork:
    db_path = get_db_path(workspace_path, hypothesis_id, experiment_id)

    async for session in get_db_session(db_path):
        profiles = await _load_agent_profiles(session)
        event_dataset, state_dataset = await _get_social_datasets(session)
        participant_ids: set[int] = set()

        if state_dataset is not None:
            table = await reflect_dataset_table(session, state_dataset)
            entity_key = state_dataset["entity_key"]
            result = await session.execute(select(table.c[entity_key]).distinct())
            participant_ids.update(int(row[0]) for row in result.all())

        if event_dataset is None:
            nodes = [
                SocialNetworkNode(
                    user_id=user_id,
                    username=_display_name(profiles.get(user_id), user_id),
                )
                for user_id in sorted(participant_ids)
            ]
            return SocialNetwork(nodes=nodes, edges=[])

        events = await _load_dataset_mappings(session, event_dataset)
        latest_actions: Dict[tuple[int, int], str] = {}
        for event in events:
            sender_id = int(event["sender_id"])
            participant_ids.add(sender_id)
            receiver_id = (
                int(event["receiver_id"])
                if event.get("receiver_id") is not None
                else None
            )
            if receiver_id is not None:
                participant_ids.add(receiver_id)
            if str(event.get("action")) in {"follow", "unfollow"} and receiver_id is not None:
                latest_actions[(sender_id, receiver_id)] = str(event["action"])

        nodes = [
            SocialNetworkNode(
                user_id=user_id,
                username=_display_name(profiles.get(user_id), user_id),
            )
            for user_id in sorted(participant_ids)
        ]
        edges = [
            SocialNetworkEdge(source=follower_id, target=followee_id)
            for (follower_id, followee_id), action in latest_actions.items()
            if action == "follow"
        ]
        return SocialNetwork(nodes=nodes, edges=edges)


@router.get(
    "/{hypothesis_id}/{experiment_id}/social/activity",
    response_model=SocialActivityResponse,
)
async def get_social_activity_at_step(
    hypothesis_id: str,
    experiment_id: str,
    step: int = Query(..., ge=0, description="Simulation step to query"),
    workspace_path: str = Query(..., description="Workspace root path"),
) -> SocialActivityResponse:
    db_path = get_db_path(workspace_path, hypothesis_id, experiment_id)

    async for session in get_db_session(db_path):
        events = await _load_social_events(session, max_step=step)
        if not events:
            return SocialActivityResponse(step=step, highlighted_agent_ids=[])

        step_events = [event for event in events if int(event["step"]) == step]
        post_author_map = _build_post_author_map(events)
        highlighted_agent_ids: set[int] = set()

        for event in step_events:
            action = str(event["action"])
            receiver_id = (
                int(event["receiver_id"])
                if event.get("receiver_id") is not None
                else None
            )
            target_id = (
                int(event["target_id"]) if event.get("target_id") is not None else None
            )
            target_author_id = (
                post_author_map.get(target_id) if target_id is not None else None
            )

            if action in SOCIAL_TARGETED_ACTIONS:
                if receiver_id is not None:
                    highlighted_agent_ids.add(receiver_id)
                if target_author_id is not None:
                    highlighted_agent_ids.add(target_author_id)

        return SocialActivityResponse(
            step=step,
            highlighted_agent_ids=sorted(highlighted_agent_ids),
        )
