"""Table schema definitions for replay table registration.

Environment modules define their replay storage using ``TableSchema`` and ``ColumnDef``.
Besides SQL column definitions, ``ColumnDef`` can also carry semantic metadata such as
descriptions, logical types, and analysis roles. Replay metadata is persisted
separately by :class:`~agentsociety2.storage.ReplayWriter`.
"""

from dataclasses import dataclass, field
from typing import Any, List, Literal, Optional

# SQLite column types
ColumnType = Literal["INTEGER", "REAL", "TEXT", "BLOB", "TIMESTAMP", "JSON"]


@dataclass
class ColumnDef:
    """Column definition for a table.

    Attributes:
        name: Column name
        type: SQLite column type
        nullable: Whether the column allows NULL values (default True)
        default: Default value expression (e.g., "CURRENT_TIMESTAMP")
        title: Optional human-readable column title
        description: Optional semantic description used by replay/export/analysis
        logical_type: Optional logical type (for example ``geo.lng`` or ``money``)
        analysis_role: Optional analysis role (for example ``measure``)
        unit: Optional unit string used by analysis/reporting
        enum_values: Optional enumeration values for discrete columns
        example: Optional example value
        tags: Optional free-form tags
    """

    name: str
    type: ColumnType
    nullable: bool = True
    default: Optional[str] = None
    title: Optional[str] = None
    description: Optional[str] = None
    logical_type: Optional[str] = None
    analysis_role: Optional[str] = None
    unit: Optional[str] = None
    enum_values: Optional[list[Any]] = None
    example: Optional[Any] = None
    tags: list[str] = field(default_factory=list)

    def to_sql(self) -> str:
        """Generate SQL column definition."""
        parts = [self.name, self.type]
        if not self.nullable:
            parts.append("NOT NULL")
        if self.default is not None:
            parts.append(f"DEFAULT {self.default}")
        return " ".join(parts)


@dataclass
class TableSchema:
    """Schema definition for a database table.

    This class allows environment modules to define their own tables
    that will be created dynamically by ReplayWriter.

    Attributes:
        name: Table name
        columns: List of column definitions
        primary_key: List of column names that form the primary key
        indexes: List of index definitions (column name or list of column names)

    Example:
        >>> schema = TableSchema(
        ...     name="agent_position",
        ...     columns=[
        ...         ColumnDef("id", "INTEGER", nullable=False),
        ...         ColumnDef("step", "INTEGER", nullable=False),
        ...         ColumnDef("t", "TIMESTAMP", nullable=False),
        ...         ColumnDef("lng", "REAL"),
        ...         ColumnDef("lat", "REAL"),
        ...     ],
        ...     primary_key=["id", "step"],
        ...     indexes=[["step"], ["t"]],
        ... )
    """
    name: str
    columns: List[ColumnDef]
    primary_key: List[str] = field(default_factory=list)
    indexes: List[List[str]] = field(default_factory=list)

    def to_create_sql(self) -> str:
        """Generate CREATE TABLE SQL statement."""
        column_defs = [col.to_sql() for col in self.columns]

        # Add primary key constraint
        if self.primary_key:
            pk_cols = ", ".join(self.primary_key)
            column_defs.append(f"PRIMARY KEY ({pk_cols})")

        columns_sql = ",\n    ".join(column_defs)
        return f"CREATE TABLE IF NOT EXISTS {self.name} (\n    {columns_sql}\n)"

    def to_index_sql(self) -> List[str]:
        """Generate CREATE INDEX SQL statements."""
        statements = []
        for idx_cols in self.indexes:
            idx_name = f"idx_{self.name}_{'_'.join(idx_cols)}"
            cols = ", ".join(idx_cols)
            statements.append(
                f"CREATE INDEX IF NOT EXISTS {idx_name} ON {self.name}({cols})"
            )
        return statements
