from __future__ import annotations

import importlib
import importlib.util
import sys
from pathlib import Path
from datetime import datetime, date, time
from decimal import Decimal
from uuid import UUID
import enum

from sqlalchemy import inspect as sa_inspect, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, RelationshipDirection

from repogen.introspection.ir import ColumnIR, RelationshipIR, ModelIR


def _get_python_type(sa_type) -> type:
    """Extract Python type from SQLAlchemy column type."""
    # Handle Enum types
    if hasattr(sa_type, 'enum_class') and sa_type.enum_class is not None:
        return sa_type.enum_class
    if hasattr(sa_type, 'enums') and sa_type.enums:
        return str

    # Try python_type property (works for most standard types)
    try:
        return sa_type.python_type
    except NotImplementedError:
        pass

    # Fallback mapping by type name
    type_name = type(sa_type).__name__.upper()
    fallbacks = {
        'JSON': dict,
        'JSONB': dict,
        'ARRAY': list,
        'HSTORE': dict,
        'TSTORE': dict,
    }
    return fallbacks.get(type_name, str)


def _get_enum_values(sa_type) -> list[str] | None:
    """Extract enum values if the column type is an Enum."""
    if hasattr(sa_type, 'enum_class') and sa_type.enum_class is not None:
        return [e.value if hasattr(e, 'value') else e.name for e in sa_type.enum_class]
    if hasattr(sa_type, 'enums') and sa_type.enums:
        return list(sa_type.enums)
    return None


def _import_module_from_path(file_path: Path, module_name: str | None = None) -> object:
    """Dynamically import a Python module from a file path."""
    if module_name is None:
        module_name = file_path.stem

    spec = importlib.util.spec_from_file_location(module_name, str(file_path))
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot import module from {file_path}")

    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def discover_models(
    models_path: str | Path,
    soft_delete_column: str = "deleted_at",
    exclude_models: list[str] | None = None,
) -> list[ModelIR]:
    """
    Import SQLAlchemy models from a file or directory and build ModelIR for each.

    Args:
        models_path: Path to a .py file or directory containing model files
        soft_delete_column: Column name that indicates soft-delete capability
        exclude_models: List of model class names to skip

    Returns:
        List of ModelIR objects describing each discovered model
    """
    exclude = set(exclude_models or [])
    exclude.update({"Base", "AbstractBase"})

    models_path = Path(models_path).resolve()

    # Add parent directory to sys.path for imports
    if models_path.is_file():
        parent = models_path.parent
    else:
        parent = models_path.parent

    if str(parent) not in sys.path:
        sys.path.insert(0, str(parent))

    # Import module(s)
    if models_path.is_file():
        _import_module_from_path(models_path)
    elif models_path.is_dir():
        # Import __init__.py first if it exists
        init_file = models_path / "__init__.py"
        if init_file.exists():
            _import_module_from_path(init_file, models_path.name)
        # Import all .py files
        for py_file in sorted(models_path.glob("*.py")):
            if py_file.name.startswith("_"):
                continue
            module_name = f"{models_path.name}.{py_file.stem}"
            _import_module_from_path(py_file, module_name)
    else:
        raise FileNotFoundError(f"Models path not found: {models_path}")

    # Find all DeclarativeBase subclasses
    base_classes = set()
    for cls in DeclarativeBase.__subclasses__():
        base_classes.add(cls)

    # Collect all mapped models from all registries
    models = []
    seen_registries = set()
    seen_models = set()
    for base_cls in base_classes:
        registry = base_cls.registry
        if id(registry) in seen_registries:
            continue
        seen_registries.add(id(registry))

        for mapper in registry.mappers:
            model_cls = mapper.class_
            if model_cls.__name__ in exclude:
                continue
            if not hasattr(model_cls, '__tablename__'):
                continue
            # Deduplicate by (class_name, table_name)
            key = (model_cls.__name__, model_cls.__tablename__)
            if key in seen_models:
                continue
            seen_models.add(key)
            models.append(_introspect_model(model_cls, soft_delete_column))

    return models


def _introspect_model(model_cls: type, soft_delete_column: str) -> ModelIR:
    """Build a ModelIR from a SQLAlchemy model class."""
    mapper = sa_inspect(model_cls)

    # Introspect columns
    columns = []
    pk_columns = []
    has_soft_delete = False

    # Count PK columns to detect composite PKs
    pk_col_count = sum(1 for c in mapper.columns if c.primary_key)

    for col_attr in mapper.columns:
        col = col_attr

        python_type = _get_python_type(col.type)
        enum_values = _get_enum_values(col.type)

        # autoincrement="auto" only applies to single-column integer PKs
        is_autoincrement = bool(
            col.primary_key
            and python_type in (int,)
            and (
                col.autoincrement is True
                or (col.autoincrement == "auto" and pk_col_count == 1)
            )
        )

        fk_target = None
        is_fk = bool(col.foreign_keys)
        if col.foreign_keys:
            fk_target = str(next(iter(col.foreign_keys)).target_fullname)

        column_ir = ColumnIR(
            name=col.name,
            python_type=python_type,
            is_nullable=bool(col.nullable),
            has_default=col.default is not None,
            has_server_default=col.server_default is not None,
            is_primary_key=bool(col.primary_key),
            is_autoincrement=is_autoincrement,
            is_foreign_key=is_fk,
            foreign_key_target=fk_target,
            is_unique=bool(col.unique),
            enum_values=enum_values,
            column_type_str=repr(col.type),
        )
        columns.append(column_ir)

        if col.primary_key:
            pk_columns.append(column_ir)

        if col.name == soft_delete_column:
            has_soft_delete = True

    # Introspect relationships
    relationships = []
    for rel in mapper.relationships:
        # Get foreign key columns involved
        fk_cols = []
        for pair in rel.local_remote_pairs:
            fk_cols.append(pair[0].name)

        # Detect self-referential
        is_self_ref = rel.mapper.class_ is model_cls

        rel_ir = RelationshipIR(
            name=rel.key,
            related_model=rel.mapper.class_.__name__,
            is_collection=bool(rel.uselist),
            back_populates=rel.back_populates,
            foreign_key_columns=fk_cols,
            is_self_referential=is_self_ref,
        )
        relationships.append(rel_ir)

    # Extract unique constraints
    unique_constraints = []
    if hasattr(model_cls, '__table__'):
        for constraint in model_cls.__table__.constraints:
            if isinstance(constraint, UniqueConstraint):
                col_names = [c.name for c in constraint.columns]
                if len(col_names) > 0:
                    unique_constraints.append(col_names)

    return ModelIR(
        class_name=model_cls.__name__,
        table_name=model_cls.__tablename__,
        module_path=model_cls.__module__,
        columns=columns,
        relationships=relationships,
        primary_key_columns=pk_columns,
        is_soft_deletable=has_soft_delete,
        soft_delete_column=soft_delete_column if has_soft_delete else None,
        unique_constraints=unique_constraints,
    )
