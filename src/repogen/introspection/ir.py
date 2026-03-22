from __future__ import annotations
from dataclasses import dataclass, field


@dataclass
class ColumnIR:
    name: str
    python_type: type
    is_nullable: bool
    has_default: bool
    has_server_default: bool
    is_primary_key: bool
    is_autoincrement: bool
    is_foreign_key: bool
    foreign_key_target: str | None
    is_unique: bool
    enum_values: list[str] | None
    column_type_str: str

@dataclass
class RelationshipIR:
    name: str
    related_model: str
    is_collection: bool
    back_populates: str | None
    foreign_key_columns: list[str]
    is_self_referential: bool

@dataclass
class ModelIR:
    class_name: str
    table_name: str
    module_path: str
    columns: list[ColumnIR]
    relationships: list[RelationshipIR]
    primary_key_columns: list[ColumnIR]
    is_soft_deletable: bool
    soft_delete_column: str | None
    unique_constraints: list[list[str]]
