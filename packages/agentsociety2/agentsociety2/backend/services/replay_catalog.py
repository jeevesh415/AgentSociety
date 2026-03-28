"""Replay metadata catalog access helpers."""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from fastapi import HTTPException
from sqlalchemy import MetaData, Table, text, inspect as sa_inspect
from sqlalchemy.ext.asyncio import AsyncSession

from agentsociety2.storage.replay_metadata import (
    COLUMN_CATALOG_TABLE,
    DATASET_CATALOG_TABLE,
)


def _quote_identifier(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


def _loads_json(raw: Any, default: Any) -> Any:
    if raw is None:
        return default
    if isinstance(raw, (list, dict)):
        return raw
    if isinstance(raw, (bytes, bytearray)):
        raw = raw.decode("utf-8", errors="ignore")
    if isinstance(raw, str):
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return default
    return default


async def ensure_replay_catalog_exists(session: AsyncSession) -> None:
    """Require metadata catalog tables to exist in the replay database."""

    def _get_tables(sync_session):
        return set(sa_inspect(sync_session.connection()).get_table_names())

    table_names = await session.run_sync(_get_tables)
    required = {DATASET_CATALOG_TABLE, COLUMN_CATALOG_TABLE}
    missing = required - table_names
    if missing:
        raise HTTPException(
            status_code=500,
            detail=(
                "Replay metadata catalog is missing. "
                f"Expected tables: {sorted(required)}; missing: {sorted(missing)}"
            ),
        )


async def load_dataset_catalog(session: AsyncSession) -> List[Dict[str, Any]]:
    """Load all replay datasets with column metadata."""
    await ensure_replay_catalog_exists(session)
    dataset_result = await session.execute(
        text(
            f"SELECT dataset_id, table_name, module_name, kind, title, description, "
            f"entity_key, step_key, time_key, default_order_json, capabilities_json, version, created_at "
            f"FROM {DATASET_CATALOG_TABLE} ORDER BY dataset_id"
        )
    )
    datasets: Dict[str, Dict[str, Any]] = {}
    for row in dataset_result.all():
        item = dict(row._mapping)
        item["default_order"] = _loads_json(item.pop("default_order_json", None), [])
        item["capabilities"] = _loads_json(item.pop("capabilities_json", None), [])
        item["columns"] = []
        datasets[item["dataset_id"]] = item

    column_result = await session.execute(
        text(
            f"SELECT dataset_id, column_name, sqlite_type, logical_type, analysis_role, title, description, "
            f"unit, enum_json, example_json, nullable, tags_json "
            f"FROM {COLUMN_CATALOG_TABLE} ORDER BY dataset_id, column_name"
        )
    )
    for row in column_result.all():
        item = dict(row._mapping)
        dataset_id = item.pop("dataset_id")
        item["enum_values"] = _loads_json(item.pop("enum_json", None), None)
        item["example"] = _loads_json(item.pop("example_json", None), None)
        item["tags"] = _loads_json(item.pop("tags_json", None), [])
        item["nullable"] = bool(item["nullable"])
        if dataset_id in datasets:
            datasets[dataset_id]["columns"].append(item)

    return list(datasets.values())


async def get_dataset_by_id(session: AsyncSession, dataset_id: str) -> Dict[str, Any]:
    datasets = await load_dataset_catalog(session)
    for dataset in datasets:
        if dataset["dataset_id"] == dataset_id:
            return dataset
    raise HTTPException(status_code=404, detail=f"Dataset '{dataset_id}' not found")


async def find_dataset_by_capability(
    session: AsyncSession,
    capability: str,
    *,
    kind: Optional[str] = None,
) -> Dict[str, Any]:
    datasets = await load_dataset_catalog(session)
    matches = []
    for dataset in datasets:
        if capability not in dataset.get("capabilities", []):
            continue
        if kind is not None and dataset.get("kind") != kind:
            continue
        matches.append(dataset)
    if not matches:
        raise HTTPException(
            status_code=404,
            detail=f"No replay dataset found for capability '{capability}'",
        )
    matches.sort(key=lambda item: item["dataset_id"])
    return matches[0]


async def reflect_dataset_table(session: AsyncSession, dataset: Dict[str, Any]) -> Table:
    table_name = dataset["table_name"]

    def _do(sync_session):
        conn = sync_session.connection()
        return Table(table_name, MetaData(), autoload_with=conn)

    return await session.run_sync(_do)


async def query_dataset_rows(
    session: AsyncSession,
    dataset: Dict[str, Any],
    *,
    page: int,
    page_size: int,
    order_by: Optional[str] = None,
    desc: bool = False,
) -> Dict[str, Any]:
    """Query rows from a dataset using metadata-provided default ordering."""
    table_name = dataset["table_name"]
    valid_columns = {column["column_name"] for column in dataset["columns"]}
    order_columns = [order_by] if order_by else list(dataset.get("default_order") or [])
    if not order_columns:
        raise HTTPException(
            status_code=500,
            detail=f"Dataset '{dataset['dataset_id']}' is missing default_order metadata",
        )
    for column_name in order_columns:
        if column_name not in valid_columns:
            raise HTTPException(
                status_code=500,
                detail=(
                    f"Dataset '{dataset['dataset_id']}' references unknown order column "
                    f"'{column_name}'"
                ),
            )

    order_clause = ", ".join(
        f"{_quote_identifier(column_name)} {'DESC' if desc else 'ASC'}"
        for column_name in order_columns
    )
    quoted_name = _quote_identifier(table_name)
    offset = (page - 1) * page_size
    total_result = await session.execute(text(f"SELECT COUNT(*) FROM {quoted_name}"))
    total = total_result.scalar() or 0
    result = await session.execute(
        text(
            f"SELECT * FROM {quoted_name} "
            f"ORDER BY {order_clause} LIMIT :limit OFFSET :offset"
        ),
        {"limit": page_size, "offset": offset},
    )
    return {
        "columns": list(result.keys()),
        "rows": [dict(row._mapping) for row in result.all()],
        "total": total,
    }
