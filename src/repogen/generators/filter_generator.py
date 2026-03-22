"""Generator for type-safe filter files for each model."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from repogen.introspection.ir import ColumnIR, ModelIR
from repogen.generators.base import (
    _get_header,
    _get_template,
    _get_type_imports,
    _python_type_to_str,
    _snake_case,
)

# Mapping from Python type string -> filter class name
_TYPE_TO_FILTER: dict[str, str] = {
    "str": "StringFilter",
    "int": "IntFilter",
    "float": "FloatFilter",
    "Decimal": "DecimalFilter",
    "bool": "BoolFilter",
    "UUID": "UUIDFilter",
    "datetime": "DateTimeFilter",
    "date": "DateFilter",
}

# Types that have no corresponding filter (JSONB, ARRAY, etc.)
_SKIP_TYPES = {"dict", "list", "bytes"}


def _filter_class_for(col: ColumnIR) -> str | None:
    """
    Return the filter class name for *col*, or None if the column should be
    skipped (dict / list / unsupported types).
    """
    type_str = _python_type_to_str(col.python_type)
    if type_str in _SKIP_TYPES:
        return None
    if col.enum_values is not None:
        # Custom enum filter — named <TypeName>Filter
        return f"{type_str}Filter"
    return _TYPE_TO_FILTER.get(type_str)


def _build_enum_filter_specs(model: ModelIR) -> list[dict[str, str]]:
    """
    Return a list of dicts describing each custom EnumFilter class to generate.
    Each dict has keys ``name`` (class name) and ``type`` (enum type name).
    """
    specs = []
    seen: set[str] = set()
    for col in model.columns:
        if col.enum_values is None:
            continue
        type_str = _python_type_to_str(col.python_type)
        filter_name = f"{type_str}Filter"
        if filter_name not in seen:
            seen.add(filter_name)
            specs.append({"name": filter_name, "type": type_str})
    return specs


def _build_filter_fields(model: ModelIR) -> list[str]:
    """
    Build the field declarations for the main *ModelFilter* class.
    Skips the soft-delete column and types that cannot be filtered.
    """
    fields: list[str] = []
    for col in model.columns:
        if model.soft_delete_column and col.name == model.soft_delete_column:
            continue
        filter_cls = _filter_class_for(col)
        if filter_cls is None:
            continue
        fields.append(f"{col.name}: {filter_cls} | None = None")
    return fields


def _build_enum_imports(model: ModelIR) -> str:
    """Return import lines for any enum types used in filters."""
    lines: list[str] = []
    seen: set[str] = set()
    for col in model.columns:
        if col.enum_values is None:
            continue
        type_str = _python_type_to_str(col.python_type)
        if type_str not in seen:
            seen.add(type_str)
            module = getattr(col.python_type, "__module__", None)
            if module and module != "builtins":
                lines.append(f"from {module} import {type_str}")
            else:
                lines.append(f"# TODO: import {type_str} from your enums module")
    return "\n".join(lines)


def generate_filters(model: ModelIR, output_dir: Path) -> str:
    """
    Generate the filter file for *model* and write it into *output_dir*.

    Returns the absolute path of the written file.
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Columns that appear in filter fields (for import analysis)
    filter_cols = [
        col for col in model.columns
        if not (model.soft_delete_column and col.name == model.soft_delete_column)
        and _filter_class_for(col) is not None
    ]
    type_imports = _get_type_imports(filter_cols)
    enum_imports = _build_enum_imports(model)
    enum_filters = _build_enum_filter_specs(model)
    filter_fields = _build_filter_fields(model)

    template = _get_template("filter.py.j2")
    content = template.render(
        header=_get_header(model.class_name, model.module_path),
        model=model,
        filter_fields=filter_fields,
        type_imports=type_imports,
        enum_imports=enum_imports,
        enum_filters=enum_filters,
    )

    file_name = f"{_snake_case(model.class_name)}_filters.py"
    out_path = output_dir / file_name
    out_path.write_text(content)
    return str(out_path)
