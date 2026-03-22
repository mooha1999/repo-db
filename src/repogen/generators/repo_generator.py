"""Generator for Repository files for each model."""
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


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _build_pk_params(model: ModelIR) -> list[str]:
    """
    Return a list of ``name: type`` strings for the primary key parameters.
    Example: ["id: int"]  or  ["tenant_id: UUID", "policy_number: str"]
    """
    params: list[str] = []
    for col in model.primary_key_columns:
        type_str = _python_type_to_str(col.python_type)
        params.append(f"{col.name}: {type_str}")
    return params


def _build_pk_where_clauses(model: ModelIR) -> list[str]:
    """
    Return ``Model.col == col`` strings for each PK column.
    """
    clauses: list[str] = []
    for col in model.primary_key_columns:
        clauses.append(f"{model.class_name}.{col.name} == {col.name}")
    return clauses


def _build_pk_delete_params(model: ModelIR) -> str:
    """
    Return the parameter list string for delete/hard_delete/restore methods.
    Example: "id: int"  or  "tenant_id: UUID, policy_number: str"
    """
    return ", ".join(_build_pk_params(model))


def _build_pk_pass_args(model: ModelIR) -> str:
    """
    Return positional argument names for forwarding PK values to get_by_id.
    Example: "id"  or  "tenant_id, policy_number"
    """
    return ", ".join(col.name for col in model.primary_key_columns)


def _build_pk_dto_access(model: ModelIR) -> str:
    """
    Return the argument(s) to pass when calling ``get_by_id`` from ``update``.
    Example: "dto.id"  or  "dto.tenant_id, dto.policy_number"
    """
    return ", ".join(f"dto.{col.name}" for col in model.primary_key_columns)


def _build_pk_names(model: ModelIR) -> str:
    """Return a Python list literal of PK column name strings."""
    names = [f'"{col.name}"' for col in model.primary_key_columns]
    return f"[{', '.join(names)}]"


def _build_unique_methods(model: ModelIR) -> list[dict]:
    """
    Return metadata dicts for unique-column lookup methods.

    Only single columns with is_unique=True that are NOT part of the PK are
    included (composite unique constraints don't get individual methods).
    """
    pk_names = {col.name for col in model.primary_key_columns}
    methods: list[dict] = []
    for col in model.columns:
        if not col.is_unique:
            continue
        if col.name in pk_names:
            continue
        if model.soft_delete_column and col.name == model.soft_delete_column:
            continue
        methods.append(
            {
                "column_name": col.name,
                "python_type": _python_type_to_str(col.python_type),
            }
        )
    return methods


def _build_model_import(model: ModelIR) -> str:
    return f"from {model.module_path} import {model.class_name}"


def _build_dto_import(model: ModelIR, output_package: str) -> str:
    module = f"{_snake_case(model.class_name)}_dtos"
    return (
        f"from {output_package}.{module} import "
        f"{model.class_name}Create, {model.class_name}Update"
    )


def _build_filter_import(model: ModelIR, output_package: str) -> str:
    module = f"{_snake_case(model.class_name)}_filters"
    return f"from {output_package}.{module} import {model.class_name}Filter"


def _build_load_options_import(model: ModelIR, output_package: str) -> str:
    module = f"{_snake_case(model.class_name)}_load_options"
    return (
        f"from {output_package}.{module} import {model.class_name}LoadOptions"
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def generate_repository(
    model: ModelIR,
    output_dir: Path,
    internals_path: str,
    config: dict | None = None,
) -> str:
    """
    Generate the repository file for *model* and write it into *output_dir*.

    Parameters
    ----------
    model:
        The ModelIR describing the SQLAlchemy model.
    output_dir:
        Directory where the generated file will be written.
    internals_path:
        Python import path (dot-separated) from which ``_internals`` is
        imported.  E.g. ``"myapp.generated"`` → imports from
        ``myapp.generated._internals.filter_utils``.
    config:
        Optional configuration flags:
        - generate_hard_delete (bool, default True)
        - generate_unique_lookups (bool, default True)
        - generate_restore (bool, default True)

    Returns the absolute path of the written file.
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    config = config or {}

    # Derive the output package from output_dir (best-effort: use directory name)
    # Callers that need a fully-qualified package should pass it via config.
    output_package = config.get("output_package", output_dir.name)

    pk_params = _build_pk_params(model)
    pk_where_clauses = _build_pk_where_clauses(model)
    pk_delete_params = _build_pk_delete_params(model)
    pk_pass_args = _build_pk_pass_args(model)
    pk_dto_access = _build_pk_dto_access(model)
    pk_names = _build_pk_names(model)

    unique_methods: list[dict] = []
    if config.get("generate_unique_lookups", True):
        unique_methods = _build_unique_methods(model)

    template = _get_template("repository.py.j2")
    content = template.render(
        header=_get_header(model.class_name, model.module_path),
        model=model,
        model_import=_build_model_import(model),
        dto_import=_build_dto_import(model, output_package),
        filter_import=_build_filter_import(model, output_package),
        load_options_import=_build_load_options_import(model, output_package),
        internals_path=internals_path,
        pk_params=pk_params,
        pk_where_clauses=pk_where_clauses,
        pk_where_clauses_for_delete=pk_where_clauses,
        pk_delete_params=pk_delete_params,
        pk_pass_args=pk_pass_args,
        pk_dto_access=pk_dto_access,
        pk_names=pk_names,
        unique_methods=unique_methods,
    )

    file_name = f"{_snake_case(model.class_name)}_repository.py"
    out_path = output_dir / file_name
    out_path.write_text(content)
    return str(out_path)
