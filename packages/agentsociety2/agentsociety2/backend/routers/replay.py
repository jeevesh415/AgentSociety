"""
Replay data query API for simulation playback.

关联文件：
- @extension/src/replayWebviewProvider.ts - 前端Replay Webview（调用此API）
- @extension/src/webview/replay/ - 前端React组件

API端点：
- GET /api/v1/replay/{hypothesis_id}/{experiment_id}/info - 实验基本信息
- GET /api/v1/replay/{hypothesis_id}/{experiment_id}/timeline - 时间线
- GET /api/v1/replay/{hypothesis_id}/{experiment_id}/agents/* - Agent相关数据
- GET /api/v1/replay/{hypothesis_id}/{experiment_id}/social/* - 社交媒体数据
- GET /api/v1/replay/{hypothesis_id}/{experiment_id}/tables/* - 数据库表查询
"""

from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import MetaData, Table, inspect as sa_inspect
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlmodel import select, desc, func, text

from ...storage.models import (
    AgentProfile,
    AgentStatus,
    AgentDialog,
)

router = APIRouter(prefix="/replay", tags=["replay"])


# =============== Data Models (Response Models) ===============
# We reuse SQLModel classes where possible, or define Pydantic models for responses that don't match DB exactly.
# For simplicity, we redefine some response models if they differ significantly or to decouple API from generic DB models.
# But here, most models match nicely.
# However, to maintain API compatibility (camelCase vs snake_case if any, or specific fields), let's keep existing response models
# but map them from DB objects.


class ExperimentInfo(BaseModel):
    """Basic information about an experiment."""

    hypothesis_id: str
    experiment_id: str
    total_steps: int
    start_time: Optional[datetime]
    end_time: Optional[datetime]
    agent_count: int
    has_social: bool = False


class TimelinePoint(BaseModel):
    """A point on the simulation timeline."""

    step: int
    t: datetime


# Use SQLModel classes as response models where appropriate to save code
# But for AgentStatus, we need merged result (status + position)
class AgentStatusResponse(BaseModel):
    """Agent status snapshot at a specific step (Combined with Position)."""

    id: int
    step: int
    t: datetime
    lng: Optional[float]
    lat: Optional[float]
    action: Optional[str]
    status: Dict[str, Any]


class TableList(BaseModel):
    """List of database tables."""

    tables: List[str]


class TableContent(BaseModel):
    """Content of a database table."""

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


# Replay API response models for social tables (tables are owned by social_media module)
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
    """Per-step social activity derived from social_media_event."""

    step: int
    highlighted_agent_ids: List[int]


# =============== Helper Functions ===============

SOCIAL_POST_ACTIONS = {"post", "repost"}
SOCIAL_TARGETED_ACTIONS = {"follow", "unfollow", "like", "unlike", "comment", "repost"}


def get_db_path(workspace_path: str, hypothesis_id: str, experiment_id: str) -> Path:
    """Get the SQLite database path for an experiment."""
    return (
        Path(workspace_path)
        / f"hypothesis_{hypothesis_id}"
        / f"experiment_{experiment_id}"
        / "run"
        / "sqlite.db"
    )


async def get_db_session(db_path: Path):
    """Get an async database session context manager."""
    if not db_path.exists():
        raise HTTPException(status_code=404, detail=f"Database not found: {db_path}")

    connection_string = f"sqlite+aiosqlite:///{db_path}"
    engine = create_async_engine(connection_string, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as session:
        yield session

    await engine.dispose()


async def _reflect_table(
    session: AsyncSession, table_name: str
) -> Optional[Table]:
    """从 SQLite 数据库反射表结构，表不存在时返回 None。"""

    def _do(sync_session):
        conn = sync_session.connection()
        if table_name not in sa_inspect(conn).get_table_names():
            return None
        return Table(table_name, MetaData(), autoload_with=conn)

    return await session.run_sync(_do)


# =============== API Endpoints ===============


@router.get("/{hypothesis_id}/{experiment_id}/info", response_model=ExperimentInfo)
async def get_experiment_info(
    hypothesis_id: str,
    experiment_id: str,
    workspace_path: str = Query(..., description="Workspace root path"),
) -> ExperimentInfo:
    """Get basic information about an experiment."""
    db_path = get_db_path(workspace_path, hypothesis_id, experiment_id)

    async for session in get_db_session(db_path):
        # Total steps
        result = await session.execute(
            select(func.count(func.distinct(AgentStatus.step)))
        )
        total_steps = result.scalar() or 0

        result = await session.execute(select(func.min(AgentStatus.t)))
        start_time = result.scalar()
        result = await session.execute(select(func.max(AgentStatus.t)))
        end_time = result.scalar()
        result = await session.execute(select(func.count(AgentProfile.id)))
        agent_count = result.scalar() or 0

        def _get_tables(sync_sess):
            from sqlalchemy import inspect

            return inspect(sync_sess.connection()).get_table_names()

        tables = await session.run_sync(_get_tables)
        has_social = (
            "social_media_event" in tables or "social_media_agent_state" in tables
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


@router.get(
    "/{hypothesis_id}/{experiment_id}/timeline", response_model=List[TimelinePoint]
)
async def get_timeline(
    hypothesis_id: str,
    experiment_id: str,
    workspace_path: str = Query(..., description="Workspace root path"),
) -> List[TimelinePoint]:
    """Get the experiment timeline (all time steps)."""
    db_path = get_db_path(workspace_path, hypothesis_id, experiment_id)

    async for session in get_db_session(db_path):
        statement = (
            select(AgentStatus.step, AgentStatus.t)
            .distinct()
            .order_by(AgentStatus.step)
        )
        result = await session.execute(statement)
        rows = result.all()
        return [TimelinePoint(step=r[0], t=r[1]) for r in rows]


@router.get(
    "/{hypothesis_id}/{experiment_id}/agents/profiles",
    response_model=List[AgentProfile],
)
async def get_agent_profiles(
    hypothesis_id: str,
    experiment_id: str,
    workspace_path: str = Query(..., description="Workspace root path"),
) -> List[AgentProfile]:
    """Get all agent profiles."""
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
    step: Optional[int] = Query(
        None, description="Specific step to query. If not provided, returns the latest."
    ),
) -> List[AgentStatusResponse]:
    """Get all agents' status at a specific step."""
    db_path = get_db_path(workspace_path, hypothesis_id, experiment_id)

    async for session in get_db_session(db_path):
        if step is None:
            # Get latest step
            result = await session.execute(select(func.max(AgentStatus.step)))
            step = result.scalar()
            if step is None:
                return []

        # 反射 mobility_agent_state 表（仅当 MobilitySpace 写入了数据时存在）
        mob = await _reflect_table(session, "mobility_agent_state")
        if mob is not None:
            statement = (
                select(AgentStatus, mob)
                .select_from(AgentStatus)
                .outerjoin(
                    mob,
                    (AgentStatus.id == mob.c.agent_id)
                    & (AgentStatus.step == mob.c.step),
                )
                .where(AgentStatus.step == step)
            )
            result = await session.execute(statement)
            rows = result.all()

            def _lng_lat_from_row(row):
                pos = row[1]
                if pos is None:
                    return None, None
                if isinstance(pos, (int, float)) or not hasattr(pos, "_mapping"):
                    if len(row) > 5:
                        return row[4], row[5]
                    return None, None
                mapping = getattr(pos, "_mapping", None)
                if mapping is not None:
                    return mapping.get("lng"), mapping.get("lat")
                return getattr(pos, "lng", None), getattr(pos, "lat", None)

            return [
                AgentStatusResponse(
                    id=row[0].id,
                    step=row[0].step,
                    t=row[0].t,
                    lng=lng,
                    lat=lat,
                    action=row[0].action,
                    status=row[0].status or {},
                )
                for row in rows
                for lng, lat in (_lng_lat_from_row(row),)
            ]
        else:
            result = await session.execute(
                select(AgentStatus).where(AgentStatus.step == step)
            )
            statuses = result.scalars().all()
            return [
                AgentStatusResponse(
                    id=s.id,
                    step=s.step,
                    t=s.t,
                    lng=None,
                    lat=None,
                    action=s.action,
                    status=s.status or {},
                )
                for s in statuses
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
    """Get the complete status history of a specific agent."""
    db_path = get_db_path(workspace_path, hypothesis_id, experiment_id)

    async for session in get_db_session(db_path):
        mob = await _reflect_table(session, "mobility_agent_state")
        if mob is not None:
            statement = (
                select(AgentStatus, mob)
                .select_from(AgentStatus)
                .outerjoin(
                    mob,
                    (AgentStatus.id == mob.c.agent_id)
                    & (AgentStatus.step == mob.c.step),
                )
                .where(AgentStatus.id == agent_id)
                .order_by(AgentStatus.step)
            )
            result = await session.execute(statement)
            rows = result.all()

            def _lng_lat_from_row(row):
                pos = row[1]
                if pos is None:
                    return None, None
                if isinstance(pos, (int, float)) or not hasattr(pos, "_mapping"):
                    if len(row) > 5:
                        return row[4], row[5]
                    return None, None
                mapping = getattr(pos, "_mapping", None)
                if mapping is not None:
                    return mapping.get("lng"), mapping.get("lat")
                return getattr(pos, "lng", None), getattr(pos, "lat", None)

            return [
                AgentStatusResponse(
                    id=row[0].id,
                    step=row[0].step,
                    t=row[0].t,
                    lng=lng,
                    lat=lat,
                    action=row[0].action,
                    status=row[0].status or {},
                )
                for row in rows
                for lng, lat in (_lng_lat_from_row(row),)
            ]
        else:
            result = await session.execute(
                select(AgentStatus)
                .where(AgentStatus.id == agent_id)
                .order_by(AgentStatus.step)
            )
            statuses = result.scalars().all()
            return [
                AgentStatusResponse(
                    id=s.id,
                    step=s.step,
                    t=s.t,
                    lng=None,
                    lat=None,
                    action=s.action,
                    status=s.status or {},
                )
                for s in statuses
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
    """Get the movement trajectory of a specific agent (requires MobilitySpace)."""
    db_path = get_db_path(workspace_path, hypothesis_id, experiment_id)

    async for session in get_db_session(db_path):
        mob = await _reflect_table(session, "mobility_agent_state")
        if mob is None:
            return []

        query = select(mob).where(mob.c.agent_id == agent_id)
        if start_step is not None:
            query = query.where(mob.c.step >= start_step)
        if end_step is not None:
            query = query.where(mob.c.step <= end_step)
        query = query.order_by(mob.c.step)
        result = await session.execute(query)
        rows = result.all()
        return [
            {
                "step": row.step,
                "t": row.t.isoformat()
                if hasattr(row.t, "isoformat")
                else str(row.t),
                "lng": row.lng,
                "lat": row.lat,
            }
            for row in rows
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
        None, description="Dialog type filter: 0=thought, 1=agent-to-agent, 2=user"
    ),
) -> List[AgentDialog]:
    """Get dialog records for a specific agent."""
    db_path = get_db_path(workspace_path, hypothesis_id, experiment_id)

    async for session in get_db_session(db_path):
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
        description="Dialog type filter: 0=反思 (thought/reflection); V2 only has type 0",
    ),
) -> List[AgentDialog]:
    """Get all dialog records at a specific step."""
    db_path = get_db_path(workspace_path, hypothesis_id, experiment_id)

    async for session in get_db_session(db_path):
        query = select(AgentDialog).where(AgentDialog.step == step)
        if dialog_type is not None:
            query = query.where(AgentDialog.type == dialog_type)

        query = query.order_by(AgentDialog.id)
        result = await session.execute(query)
        return result.scalars().all()


def _row_to_dict(row: Any) -> Dict[str, Any]:
    """Map SQLAlchemy Row to dict for Pydantic (handles _mapping and datetime)."""
    if hasattr(row, "_mapping"):
        d = dict(row._mapping)
    else:
        d = dict(row)
    for k, v in list(d.items()):
        if hasattr(v, "isoformat"):
            d[k] = v
    return d


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
    """Get social media profile for a user derived from replay snapshots."""
    db_path = get_db_path(workspace_path, hypothesis_id, experiment_id)

    async for session in get_db_session(db_path):
        profile = await session.get(AgentProfile, user_id)
        social_state = await _reflect_table(session, "social_media_agent_state")
        state: dict[str, Any] = {}
        if social_state is not None:
            result = await session.execute(
                select(social_state)
                .where(social_state.c.agent_id == user_id)
                .order_by(desc(social_state.c.step))
                .limit(1)
            )
            row = result.first()
            if row is not None:
                state = dict(row._mapping)
        if profile is None and not state:
            raise HTTPException(status_code=404, detail="Social user not found")

        bio = None
        if profile is not None and isinstance(profile.profile, dict):
            for key in ("bio", "background_story", "description"):
                value = profile.profile.get(key)
                if isinstance(value, str) and value.strip():
                    bio = value
                    break

        return SocialUser(
            user_id=user_id,
            username=(profile.name if profile is not None and profile.name else None)
            or f"User {user_id}",
            bio=bio,
            created_at=None,
            followers_count=int(state.get("followers_count") or 0),
            following_count=int(state.get("following_count") or 0),
            posts_count=int(state.get("posts_count") or 0),
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
        None, description="Only posts with step <= max_step (timeline step)"
    ),
    limit: int = Query(200, ge=1, le=500),
) -> List[SocialPost]:
    """Get posts from a social media user derived from social_media_event."""
    db_path = get_db_path(workspace_path, hypothesis_id, experiment_id)

    async for session in get_db_session(db_path):
        social_event = await _reflect_table(session, "social_media_event")
        if social_event is None:
            return []

        query = select(social_event)
        if max_step is not None:
            query = query.where(social_event.c.step <= max_step)
        query = query.order_by(social_event.c.step, social_event.c.id)
        result = await session.execute(query)
        events = [dict(row._mapping) for row in result.all()]

        latest_like_actions: dict[tuple[int, int], str] = {}
        comments_count: defaultdict[int, int] = defaultdict(int)
        reposts_count: defaultdict[int, int] = defaultdict(int)
        posts: list[SocialPost] = []

        for event in events:
            action = str(event.get("action") or "")
            target_id = event.get("target_id")
            if target_id is not None:
                target_post_id = int(target_id)
                if action in {"like", "unlike"}:
                    latest_like_actions[
                        (int(event["sender_id"]), target_post_id)
                    ] = action
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
            key=lambda post: (
                post.step,
                post.created_at or datetime.min,
                post.post_id,
            ),
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
        None, description="Only posts with step <= max_step (timeline step)"
    ),
    limit: int = Query(500, ge=1, le=2000),
) -> List[SocialPost]:
    """Get all posts from all users derived from social_media_event."""
    db_path = get_db_path(workspace_path, hypothesis_id, experiment_id)

    async for session in get_db_session(db_path):
        social_event = await _reflect_table(session, "social_media_event")
        if social_event is None:
            return []

        query = select(social_event)
        if max_step is not None:
            query = query.where(social_event.c.step <= max_step)
        query = query.order_by(social_event.c.step, social_event.c.id)
        result = await session.execute(query)
        events = [dict(row._mapping) for row in result.all()]

        latest_like_actions: dict[tuple[int, int], str] = {}
        comments_count: defaultdict[int, int] = defaultdict(int)
        reposts_count: defaultdict[int, int] = defaultdict(int)
        posts: list[SocialPost] = []

        for event in events:
            action = str(event.get("action") or "")
            target_id = event.get("target_id")
            if target_id is not None:
                target_post_id = int(target_id)
                if action in {"like", "unlike"}:
                    latest_like_actions[
                        (int(event["sender_id"]), target_post_id)
                    ] = action
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
            key=lambda post: (
                post.step,
                post.created_at or datetime.min,
                post.post_id,
            ),
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
    """Get all comments for a post derived from social_media_event."""
    db_path = get_db_path(workspace_path, hypothesis_id, experiment_id)

    async for session in get_db_session(db_path):
        social_event = await _reflect_table(session, "social_media_event")
        if social_event is None:
            return []

        result = await session.execute(
            select(social_event)
            .where(social_event.c.action == "comment")
            .where(social_event.c.target_id == post_id)
            .order_by(social_event.c.step, social_event.c.id)
        )
        return [
            SocialComment(
                comment_id=int(row.id),
                step=int(row.step),
                post_id=int(row.target_id),
                author_id=int(row.sender_id),
                content=str(row.content or ""),
                created_at=row.t,
                likes_count=0,
            )
            for row in result.all()
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
        None, description="Only events with step <= max_step (timeline step)"
    ),
    limit: int = Query(200, ge=1, le=1000),
) -> List[SocialEvent]:
    """Get a user's social activity stream derived from social_media_event."""
    db_path = get_db_path(workspace_path, hypothesis_id, experiment_id)

    async for session in get_db_session(db_path):
        social_event = await _reflect_table(session, "social_media_event")
        if social_event is None:
            return []

        profile_result = await session.execute(select(AgentProfile))
        profiles = {
            profile.id: profile for profile in profile_result.scalars().all()
        }

        query = select(social_event)
        if max_step is not None:
            query = query.where(social_event.c.step <= max_step)
        query = query.order_by(social_event.c.step, social_event.c.id)
        result = await session.execute(query)
        events = [dict(row._mapping) for row in result.all()]

        post_author_map: dict[int, int] = {}
        for event in events:
            action = str(event.get("action") or "")
            if action == "post" and event.get("target_id") is not None:
                post_author_map[int(event["target_id"])] = int(event["sender_id"])
            elif action == "repost":
                post_author_map[int(event["id"])] = int(event["sender_id"])

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
        response: list[SocialEvent] = []
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
            sender_profile = profiles.get(sender_id)
            receiver_profile = (
                profiles.get(receiver_id) if receiver_id is not None else None
            )
            target_author_profile = (
                profiles.get(target_author_id)
                if target_author_id is not None
                else None
            )
            sender_name = (
                sender_profile.name if sender_profile is not None and sender_profile.name else None
            ) or f"User {sender_id}"
            receiver_name = None
            if receiver_id is not None:
                receiver_name = (
                    receiver_profile.name
                    if receiver_profile is not None and receiver_profile.name
                    else f"User {receiver_id}"
                )
            target_author_name = None
            if target_author_id is not None:
                target_author_name = (
                    target_author_profile.name
                    if target_author_profile is not None and target_author_profile.name
                    else f"User {target_author_id}"
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
    """Get social network graph derived from follow/unfollow events."""
    db_path = get_db_path(workspace_path, hypothesis_id, experiment_id)

    async for session in get_db_session(db_path):
        profile_result = await session.execute(select(AgentProfile))
        profiles = {
            profile.id: profile for profile in profile_result.scalars().all()
        }

        participant_ids: set[int] = set()
        social_state = await _reflect_table(session, "social_media_agent_state")
        if social_state is not None:
            state_result = await session.execute(
                select(social_state).order_by(
                    social_state.c.agent_id, desc(social_state.c.step)
                )
            )
            for row in state_result.all():
                participant_ids.add(int(row.agent_id))

        social_event = await _reflect_table(session, "social_media_event")
        if social_event is None:
            nodes = [
                SocialNetworkNode(
                    user_id=user_id,
                    username=(
                        profiles[user_id].name
                        if user_id in profiles and profiles[user_id].name
                        else f"User {user_id}"
                    ),
                )
                for user_id in sorted(participant_ids)
            ]
            return SocialNetwork(nodes=nodes, edges=[])

        result = await session.execute(
            select(social_event).order_by(social_event.c.step, social_event.c.id)
        )
        all_events = [dict(row._mapping) for row in result.all()]
        latest_actions: Dict[tuple[int, int], str] = {}
        for event in all_events:
            sender_id = int(event["sender_id"])
            receiver_id = (
                int(event["receiver_id"])
                if event.get("receiver_id") is not None
                else None
            )
            participant_ids.add(sender_id)
            if receiver_id is not None:
                participant_ids.add(receiver_id)
        for event in all_events:
            if str(event["action"]) not in {"follow", "unfollow"}:
                continue
            sender_id = int(event["sender_id"])
            receiver_id = (
                int(event["receiver_id"])
                if event.get("receiver_id") is not None
                else None
            )
            if receiver_id is not None:
                latest_actions[(sender_id, receiver_id)] = str(event["action"])

        nodes = [
            SocialNetworkNode(
                user_id=user_id,
                username=(
                    profiles[user_id].name
                    if user_id in profiles and profiles[user_id].name
                    else f"User {user_id}"
                ),
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
    """Get which agents had social activity at a given step."""
    db_path = get_db_path(workspace_path, hypothesis_id, experiment_id)

    async for session in get_db_session(db_path):
        social_event = await _reflect_table(session, "social_media_event")
        if social_event is None:
            return SocialActivityResponse(step=step, highlighted_agent_ids=[])

        result = await session.execute(
            select(social_event)
            .where(social_event.c.step <= step)
            .order_by(social_event.c.step, social_event.c.id)
        )
        all_events = [dict(row._mapping) for row in result.all()]
        step_events = [event for event in all_events if int(event["step"]) == step]
        post_author_map: dict[int, int] = {}
        for event in all_events:
            action = str(event.get("action") or "")
            if action == "post" and event.get("target_id") is not None:
                post_author_map[int(event["target_id"])] = int(event["sender_id"])
            elif action == "repost":
                post_author_map[int(event["id"])] = int(event["sender_id"])

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


# =============== Database Inspection Endpoints ===============


@router.get("/{hypothesis_id}/{experiment_id}/tables", response_model=TableList)
async def get_tables(
    hypothesis_id: str,
    experiment_id: str,
    workspace_path: str = Query(..., description="Workspace root path"),
) -> TableList:
    """Get list of all tables in the database."""
    db_path = get_db_path(workspace_path, hypothesis_id, experiment_id)

    # Inspection usually requires standard SQLAlchemy inspection, easier with async engine
    async for session in get_db_session(db_path):
        # We can run an inspection on the engine connection
        def get_all_tables(sync_session):
            # sync_session is a sqlalchemy.orm.Session
            from sqlalchemy import inspect

            inspector = inspect(sync_session.connection())
            return inspector.get_table_names()

        tables = await session.run_sync(get_all_tables)
        return TableList(tables=tables)


@router.get(
    "/{hypothesis_id}/{experiment_id}/tables/{table_name}", response_model=TableContent
)
async def get_table_content(
    hypothesis_id: str,
    experiment_id: str,
    table_name: str,
    workspace_path: str = Query(..., description="Workspace root path"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> TableContent:
    """Get content of a specific table."""
    db_path = get_db_path(workspace_path, hypothesis_id, experiment_id)

    async for session in get_db_session(db_path):
        # Validate table_name against actual tables to prevent SQL injection
        def _get_valid_tables(sync_session):
            from sqlalchemy import inspect
            return inspect(sync_session.connection()).get_table_names()

        valid_tables = await session.run_sync(_get_valid_tables)
        if table_name not in valid_tables:
            raise HTTPException(
                status_code=404,
                detail=f"Table '{table_name}' not found",
            )

        # Safe to use: table_name is validated against actual table names
        quoted_name = f'"{table_name}"'
        offset = (page - 1) * page_size

        count_sql = f"SELECT COUNT(*) FROM {quoted_name}"
        total_result = await session.execute(text(count_sql))
        total = total_result.scalar() or 0

        data_sql = f"SELECT * FROM {quoted_name} LIMIT :limit OFFSET :offset"
        result = await session.execute(
            text(data_sql), {"limit": page_size, "offset": offset}
        )

        columns = list(result.keys())
        rows = [dict(row._mapping) for row in result.all()]

        return TableContent(columns=columns, rows=rows, total=total)
