"""Shared utilities for code generators."""

from __future__ import annotations

from ..introspection.ir import ColumnIR


def python_type_to_annotation(col: ColumnIR) -> tuple[str, set[str]]:
    """Convert a column's Python type to an annotation string and required imports.

    Returns (type_string, set_of_import_statements).
    """
    imports: set[str] = set()

    if col.is_enum and col.enum_class_name:
        if col.enum_class_module:
            imports.add(f"from {col.enum_class_module} import {col.enum_class_name}")
        return col.enum_class_name, imports

    type_str = col.python_type

    if col.python_type == "Decimal":
        imports.add("from decimal import Decimal")
    elif col.python_type == "datetime":
        imports.add("from datetime import datetime")
    elif col.python_type == "date":
        imports.add("from datetime import date")
    elif col.python_type == "UUID":
        imports.add("from uuid import UUID")

    return type_str, imports


def get_filter_type(col: ColumnIR) -> str | None:
    """Get the filter class name for a column type."""
    _map = {
        "str": "StringFilter",
        "int": "IntFilter",
        "float": "FloatFilter",
        "Decimal": "NumericFilter",
        "bool": "BoolFilter",
        "datetime": "DateTimeFilter",
        "date": "DateFilter",
        "UUID": "UUIDFilter",
    }
    return _map.get(col.python_type)


def model_name_to_snake(name: str) -> str:
    """Convert CamelCase model name to snake_case for directory names."""
    result: list[str] = []
    for i, char in enumerate(name):
        if char.isupper() and i > 0:
            result.append("_")
        result.append(char.lower())
    return "".join(result)
