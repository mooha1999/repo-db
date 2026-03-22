"""Intermediate Representation for parsed SQLAlchemy models."""

from __future__ import annotations

import enum
from dataclasses import dataclass, field


class RelationshipDirection(enum.Enum):
    """Direction of a SQLAlchemy relationship."""
    ONE_TO_MANY = "ONE_TO_MANY"
    MANY_TO_ONE = "MANY_TO_ONE"
    ONE_TO_ONE = "ONE_TO_ONE"
    MANY_TO_MANY = "MANY_TO_MANY"


@dataclass
class ColumnIR:
    """Intermediate representation of a SQLAlchemy column."""
    name: str
    python_type: str  # e.g., "int", "str", "datetime", "Decimal"
    python_type_module: str | None = None  # e.g., "decimal", "datetime", "uuid"
    sqlalchemy_type: str = ""  # e.g., "String(100)", "Integer"
    nullable: bool = False
    has_default: bool = False
    has_server_default: bool = False
    is_primary_key: bool = False
    is_autoincrement: bool = False
    is_foreign_key: bool = False
    foreign_key_target: str | None = None  # e.g., "users.id"
    is_enum: bool = False
    enum_class_name: str | None = None  # e.g., "PolicyStatus"
    enum_class_module: str | None = None  # Full module path for import
    enum_members: list[str] = field(default_factory=list)


@dataclass
class RelationshipIR:
    """Intermediate representation of a SQLAlchemy relationship."""
    attribute_name: str
    related_model_name: str
    direction: RelationshipDirection
    uselist: bool = True
    back_populates: str | None = None
    secondary_table: str | None = None  # For M2M relationships


@dataclass
class InheritanceIR:
    """Inheritance info for single-table inheritance."""
    is_base: bool = False
    is_child: bool = False
    parent_model_name: str | None = None
    discriminator_column: str | None = None
    discriminator_value: str | None = None


@dataclass
class ModelIR:
    """Complete intermediate representation of a SQLAlchemy model."""
    class_name: str
    table_name: str
    module_path: str  # Full import path of the model module
    columns: list[ColumnIR] = field(default_factory=list)
    relationships: list[RelationshipIR] = field(default_factory=list)
    primary_key_columns: list[str] = field(default_factory=list)
    is_soft_deletable: bool = False
    inheritance: InheritanceIR | None = None
    is_association_table: bool = False  # Skip repos for junction tables

    @property
    def has_composite_pk(self) -> bool:
        return len(self.primary_key_columns) > 1

    @property
    def single_pk_column(self) -> ColumnIR | None:
        if len(self.primary_key_columns) == 1:
            for col in self.columns:
                if col.name == self.primary_key_columns[0]:
                    return col
        return None

    @property
    def pk_columns(self) -> list[ColumnIR]:
        return [c for c in self.columns if c.is_primary_key]

    @property
    def non_pk_columns(self) -> list[ColumnIR]:
        return [c for c in self.columns if not c.is_primary_key]
