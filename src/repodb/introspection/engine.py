"""Model introspection engine for extracting IR from SQLAlchemy models."""

from __future__ import annotations

import importlib
import importlib.util
import inspect as python_inspect
import sys
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any
from uuid import UUID

import sqlalchemy
from sqlalchemy import inspect as sa_inspect
from sqlalchemy.orm import DeclarativeBase, RelationshipProperty
from sqlalchemy.orm.base import MANYTOMANY, MANYTOONE, ONETOMANY

from .ir import ColumnIR, InheritanceIR, ModelIR, RelationshipDirection, RelationshipIR


# Map SQLAlchemy types to Python type strings
_SA_TYPE_MAP: dict[type, tuple[str, str | None]] = {
    sqlalchemy.Integer: ("int", None),
    sqlalchemy.SmallInteger: ("int", None),
    sqlalchemy.BigInteger: ("int", None),
    sqlalchemy.String: ("str", None),
    sqlalchemy.Text: ("str", None),
    sqlalchemy.Boolean: ("bool", None),
    sqlalchemy.DateTime: ("datetime", "datetime"),
    sqlalchemy.Date: ("date", "datetime"),
    sqlalchemy.Float: ("float", None),
    sqlalchemy.Numeric: ("Decimal", "decimal"),
    sqlalchemy.LargeBinary: ("bytes", None),
}


def _resolve_python_type(
    col: Any,
) -> tuple[str, str | None, bool, str | None, str | None, list[str]]:
    """Resolve a SQLAlchemy column to (python_type_str, module, is_enum, enum_class_name, enum_module, enum_members)."""
    sa_type = col.type
    is_enum = False
    enum_class_name = None
    enum_module = None
    enum_members: list[str] = []

    # Check for Enum type
    if isinstance(sa_type, sqlalchemy.Enum):
        if sa_type.enum_class is not None:
            is_enum = True
            enum_class_name = sa_type.enum_class.__name__
            enum_module = sa_type.enum_class.__module__
            enum_members = [m.name for m in sa_type.enum_class]
            return (
                enum_class_name,
                enum_module,
                True,
                enum_class_name,
                enum_module,
                enum_members,
            )

    # Check for UUID type
    if hasattr(sqlalchemy, "Uuid") and isinstance(sa_type, sqlalchemy.Uuid):
        return ("UUID", "uuid", False, None, None, [])

    # Try to match known types
    for sa_cls, (py_type, mod) in _SA_TYPE_MAP.items():
        if isinstance(sa_type, sa_cls):
            return (py_type, mod, False, None, None, [])

    # Fallback: try to get the python type from the SA type
    try:
        py_type_cls = sa_type.python_type
        if py_type_cls is int:
            return ("int", None, False, None, None, [])
        elif py_type_cls is str:
            return ("str", None, False, None, None, [])
        elif py_type_cls is bool:
            return ("bool", None, False, None, None, [])
        elif py_type_cls is float:
            return ("float", None, False, None, None, [])
        elif py_type_cls is Decimal:
            return ("Decimal", "decimal", False, None, None, [])
        elif py_type_cls is datetime:
            return ("datetime", "datetime", False, None, None, [])
        elif py_type_cls is date:
            return ("date", "datetime", False, None, None, [])
        elif py_type_cls is UUID:
            return ("UUID", "uuid", False, None, None, [])
    except NotImplementedError:
        pass

    return ("Any", None, False, None, None, [])


def _get_relationship_direction(
    rel: RelationshipProperty[Any],
) -> RelationshipDirection:
    """Determine the relationship direction."""
    if rel.direction == MANYTOMANY:
        return RelationshipDirection.MANY_TO_MANY
    elif rel.direction == ONETOMANY:
        if not rel.uselist:
            return RelationshipDirection.ONE_TO_ONE
        return RelationshipDirection.ONE_TO_MANY
    elif rel.direction == MANYTOONE:
        return RelationshipDirection.MANY_TO_ONE
    return RelationshipDirection.MANY_TO_ONE


def _resolve_module_path(file_path: Path) -> str:
    """Try to determine the proper Python module path for a file.

    Walks up directories looking for a sys.path entry to compute the dotted
    module path. Falls back to the file stem if no sys.path entry matches.
    """
    file_path = file_path.resolve()
    # Check each sys.path entry to see if the file is underneath it
    for sp in sys.path:
        sp_resolved = Path(sp).resolve()
        try:
            relative = file_path.relative_to(sp_resolved)
            # Convert path parts to dotted module name
            parts = list(relative.with_suffix("").parts)
            return ".".join(parts)
        except ValueError:
            continue
    # Fall back to file stem
    return file_path.stem


def _import_module_from_path(file_path: Path) -> Any:
    """Import a Python module from a file path."""
    file_path = file_path.resolve()

    # Try to resolve module path BEFORE adding parent dir to sys.path,
    # so we prefer existing importable paths (e.g. "tests.sample_models")
    # over the bare stem ("sample_models").
    module_name = _resolve_module_path(file_path)

    # If no existing sys.path entry matched, add the parent directory
    # and use the file stem.
    if module_name == file_path.stem:
        parent_dir = str(file_path.parent)
        if parent_dir not in sys.path:
            sys.path.insert(0, parent_dir)
        # Re-resolve now that parent_dir is in sys.path
        module_name = _resolve_module_path(file_path)

    # Check if already imported
    if module_name in sys.modules:
        return sys.modules[module_name]

    spec = importlib.util.spec_from_file_location(module_name, str(file_path))
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot import {file_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def _find_base_class(module: Any) -> type | None:
    """Find the DeclarativeBase subclass in the module."""
    for name, obj in python_inspect.getmembers(module, python_inspect.isclass):
        if issubclass(obj, DeclarativeBase) and obj is not DeclarativeBase:
            # Check if this is a direct base (has no mapped table itself or is the base)
            if hasattr(obj, "__tablename__") or hasattr(obj, "metadata"):
                # If it has no tablename, it's likely the Base class
                if not hasattr(obj, "__tablename__"):
                    return obj
    # Second pass: find any DeclarativeBase subclass without __tablename__
    for name, obj in python_inspect.getmembers(module, python_inspect.isclass):
        if issubclass(obj, DeclarativeBase) and obj is not DeclarativeBase:
            return obj
    return None


def _find_model_classes(module: Any) -> list[type]:
    """Find all model classes (those with __tablename__) in the module."""
    models = []
    for name, obj in python_inspect.getmembers(module, python_inspect.isclass):
        if (
            issubclass(obj, DeclarativeBase)
            and obj is not DeclarativeBase
            and hasattr(obj, "__tablename__")
        ):
            models.append(obj)
    return models


def _is_association_table(model_cls: type) -> bool:
    """Check if a model is a pure association/junction table."""
    mapper = sa_inspect(model_cls)
    columns = list(mapper.columns)
    # If ALL columns are either PKs that are also FKs, it's an association table
    fk_pk_count = 0
    for col in columns:
        if col.primary_key and col.foreign_keys:
            fk_pk_count += 1
    # Association table: all columns are PK+FK (typically 2 columns)
    return fk_pk_count == len(columns) and len(columns) >= 2


def introspect_model(model_cls: type) -> ModelIR:
    """Extract IR from a single SQLAlchemy model class."""
    mapper = sa_inspect(model_cls)
    table_name = model_cls.__tablename__  # type: ignore[attr-defined]
    module_path = model_cls.__module__

    # Extract columns
    columns: list[ColumnIR] = []
    pk_columns: list[str] = []

    # Determine PK column count first
    pk_col_names_set = {col.name for col in mapper.primary_key}
    is_composite_pk = len(pk_col_names_set) > 1

    for col_attr in mapper.column_attrs:
        for col in col_attr.columns:
            py_type, py_module, is_enum, enum_name, enum_mod, enum_members = (
                _resolve_python_type(col)
            )

            is_pk = col.primary_key
            is_autoincrement = False
            if is_pk:
                pk_columns.append(col.name)
                # Check autoincrement
                if hasattr(col, "identity") and col.identity is not None:
                    is_autoincrement = True
                elif hasattr(col, "autoincrement") and col.autoincrement is True:
                    is_autoincrement = True
                # Only default to autoincrement for SINGLE integer PKs
                elif (
                    not is_composite_pk
                    and isinstance(
                        col.type,
                        (
                            sqlalchemy.Integer,
                            sqlalchemy.BigInteger,
                            sqlalchemy.SmallInteger,
                        ),
                    )
                    and col.autoincrement != False  # noqa: E712
                ):
                    is_autoincrement = True

            has_default = col.default is not None
            has_server_default = col.server_default is not None

            is_fk = bool(col.foreign_keys)
            fk_target = None
            if is_fk:
                fk_target = str(list(col.foreign_keys)[0].target_fullname)

            col_ir = ColumnIR(
                name=col.name,
                python_type=py_type,
                python_type_module=py_module,
                sqlalchemy_type=str(col.type),
                nullable=col.nullable or False,
                has_default=has_default,
                has_server_default=has_server_default,
                is_primary_key=is_pk,
                is_autoincrement=is_autoincrement,
                is_foreign_key=is_fk,
                foreign_key_target=fk_target,
                is_enum=is_enum,
                enum_class_name=enum_name,
                enum_class_module=enum_mod,
                enum_members=enum_members,
            )
            columns.append(col_ir)

    # Extract relationships
    relationships: list[RelationshipIR] = []
    for rel in mapper.relationships:
        direction = _get_relationship_direction(rel)
        rel_ir = RelationshipIR(
            attribute_name=rel.key,
            related_model_name=rel.mapper.class_.__name__,
            direction=direction,
            uselist=rel.uselist,
            back_populates=rel.back_populates,
            secondary_table=rel.secondary.name if rel.secondary is not None else None,
        )
        relationships.append(rel_ir)

    # Detect soft delete
    is_soft_deletable = any(c.name == "deleted_at" and c.nullable for c in columns)

    # Detect inheritance
    inheritance = None
    mapper_args = getattr(model_cls, "__mapper_args__", {})
    if isinstance(mapper_args, dict):
        if "polymorphic_on" in mapper_args or "polymorphic_identity" in mapper_args:
            is_base = "polymorphic_on" in mapper_args
            is_child = not is_base and "polymorphic_identity" in mapper_args
            parent_name = None
            if is_child:
                for base in model_cls.__mro__[1:]:
                    if (
                        base is not model_cls
                        and hasattr(base, "__tablename__")
                        and issubclass(base, DeclarativeBase)
                    ):
                        parent_name = base.__name__
                        break

            disc_col = None
            if is_base and "polymorphic_on" in mapper_args:
                poly_on = mapper_args["polymorphic_on"]
                if hasattr(poly_on, "name"):
                    disc_col = poly_on.name
                elif isinstance(poly_on, str):
                    disc_col = poly_on

            disc_value = None
            if "polymorphic_identity" in mapper_args:
                disc_value = str(mapper_args["polymorphic_identity"])

            inheritance = InheritanceIR(
                is_base=is_base,
                is_child=is_child,
                parent_model_name=parent_name,
                discriminator_column=disc_col,
                discriminator_value=disc_value,
            )

    # Detect association table
    is_assoc = _is_association_table(model_cls)

    return ModelIR(
        class_name=model_cls.__name__,
        table_name=table_name,
        module_path=module_path,
        columns=columns,
        relationships=relationships,
        primary_key_columns=pk_columns,
        is_soft_deletable=is_soft_deletable,
        inheritance=inheritance,
        is_association_table=is_assoc,
    )


def introspect_models(path: str | Path) -> list[ModelIR]:
    """Introspect all models from a file or directory path.

    Returns a list of ModelIR for each discovered model.
    """
    path = Path(path)
    modules = []

    if path.is_file():
        modules.append(_import_module_from_path(path))
    elif path.is_dir():
        for py_file in sorted(path.glob("*.py")):
            if py_file.name.startswith("_"):
                continue
            try:
                modules.append(_import_module_from_path(py_file))
            except Exception as e:
                print(f"Warning: Could not import {py_file}: {e}")
    else:
        raise FileNotFoundError(f"Path not found: {path}")

    # Collect all model classes
    all_models: list[type] = []
    for module in modules:
        all_models.extend(_find_model_classes(module))

    # Deduplicate by class name
    seen: set[str] = set()
    unique_models: list[type] = []
    for model in all_models:
        if model.__name__ not in seen:
            seen.add(model.__name__)
            unique_models.append(model)

    # Introspect each model
    results: list[ModelIR] = []
    for model_cls in unique_models:
        try:
            ir = introspect_model(model_cls)
            if not ir.primary_key_columns:
                print(
                    f"Warning: Model {model_cls.__name__} has no primary key — skipped"
                )
                continue
            results.append(ir)
        except Exception as e:
            print(f"Warning: Could not introspect {model_cls.__name__}: {e}")

    return results
