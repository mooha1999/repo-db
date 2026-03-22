"""Generator for Pydantic DTO files (Create / Update) for each model."""
from __future__ import annotations

from pathlib import Path

from repogen.introspection.ir import ColumnIR, ModelIR
from repogen.generators.base import (
    _get_header,
    _get_template,
    _get_type_imports,
    _python_type_to_str,
    _snake_case,
)

# Columns that are always excluded from DTOs regardless of their role
_ALWAYS_EXCLUDE_FROM_UPDATE = {"created_at", "updated_at"}


def _build_enum_imports(columns: list[ColumnIR]) -> str:
    """Return import lines for enum types referenced in the given columns."""
    lines: list[str] = []
    seen: set[str] = set()
    for col in columns:
        if col.enum_values is not None:
            type_name = _python_type_to_str(col.python_type)
            if type_name in seen:
                continue
            seen.add(type_name)
            module = getattr(col.python_type, "__module__", None)
            if module and module != "builtins":
                lines.append(f"from {module} import {type_name}")
            else:
                lines.append(f"# TODO: import {type_name} from your enums module")
    return "\n".join(lines)


def _optional_annotation(type_str: str, nullable: bool) -> str:
    """Return 'type_str | None' when nullable, otherwise 'type_str'."""
    if nullable:
        return f"{type_str} | None"
    return type_str


def _build_create_fields(model: ModelIR) -> list[str]:
    """
    Build field declarations for the CreateDTO.

    Rules:
    - Exclude autoincrement PKs.
    - Exclude the soft-delete column.
    - A field is *required* (no default) when:
        is_nullable=False AND has_default=False AND has_server_default=False
    - Otherwise it is optional: `name: type | None = None`  (or typed default)
    """
    fields: list[str] = []
    # Split into required and optional so required come first
    required: list[str] = []
    optional: list[str] = []

    for col in model.columns:
        # Skip autoincrement primary keys
        if col.is_primary_key and col.is_autoincrement:
            continue
        # Skip the soft-delete column
        if model.soft_delete_column and col.name == model.soft_delete_column:
            continue

        type_str = _python_type_to_str(col.python_type)
        annotation = _optional_annotation(type_str, col.is_nullable)

        is_required = (
            not col.is_nullable
            and not col.has_default
            and not col.has_server_default
        )

        if is_required:
            required.append(f"{col.name}: {annotation}")
        else:
            # Optional fields always use `type | None = None`
            optional.append(f"{col.name}: {type_str} | None = None")

    fields = required + optional
    return fields


def _build_update_fields(model: ModelIR) -> list[str]:
    """
    Build field declarations for the UpdateDTO.

    Rules:
    - PK fields are required (typed but no default).
    - Exclude soft-delete column.
    - Exclude created_at / updated_at columns.
    - All other fields are optional: `name: type | None = None`.
    """
    pk_names = {col.name for col in model.primary_key_columns}
    required: list[str] = []
    optional: list[str] = []

    for col in model.columns:
        # Exclude soft-delete column
        if model.soft_delete_column and col.name == model.soft_delete_column:
            continue
        # Exclude created_at / updated_at
        if col.name in _ALWAYS_EXCLUDE_FROM_UPDATE:
            continue

        type_str = _python_type_to_str(col.python_type)

        if col.name in pk_names:
            # PK: required, keep original nullability
            annotation = _optional_annotation(type_str, col.is_nullable)
            required.append(f"{col.name}: {annotation}")
        else:
            optional.append(f"{col.name}: {type_str} | None = None")

    return required + optional


def generate_dtos(model: ModelIR, output_dir: Path, exclude_columns: list[str] | None = None) -> str:
    """
    Generate the DTO file for *model* and write it into *output_dir*.

    Returns the absolute path of the written file.
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Columns used in each DTO (for import analysis)
    create_cols = [
        col for col in model.columns
        if not (col.is_primary_key and col.is_autoincrement)
        and not (model.soft_delete_column and col.name == model.soft_delete_column)
    ]
    pk_names = {col.name for col in model.primary_key_columns}
    update_cols = [
        col for col in model.columns
        if not (model.soft_delete_column and col.name == model.soft_delete_column)
        and col.name not in _ALWAYS_EXCLUDE_FROM_UPDATE
    ]

    all_dto_cols = list({col.name: col for col in create_cols + update_cols}.values())
    type_imports = _get_type_imports(all_dto_cols)

    # Enum imports — currently best-effort placeholder comments
    enum_cols = [c for c in all_dto_cols if c.enum_values is not None]
    enum_imports = _build_enum_imports(enum_cols) if enum_cols else ""

    template = _get_template("dto.py.j2")
    content = template.render(
        header=_get_header(model.class_name, model.module_path),
        model=model,
        create_fields=_build_create_fields(model),
        update_fields=_build_update_fields(model),
        type_imports=type_imports,
        enum_imports=enum_imports,
    )

    file_name = f"{_snake_case(model.class_name)}_dtos.py"
    out_path = output_dir / file_name
    out_path.write_text(content)
    return str(out_path)
