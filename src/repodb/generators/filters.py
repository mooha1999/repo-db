"""Filter code generator."""

from __future__ import annotations

from ..introspection.ir import ModelIR


_TYPE_TO_FILTER = {
    "str": "StringFilter",
    "int": "IntFilter",
    "float": "FloatFilter",
    "Decimal": "NumericFilter",
    "bool": "BoolFilter",
    "datetime": "DateTimeFilter",
    "date": "DateFilter",
    "UUID": "UUIDFilter",
}


def generate_filters(model: ModelIR) -> str:
    """Generate filter DTO source code for a model."""
    imports: set[str] = set()
    imports.add("from pydantic import BaseModel")

    base_filter_types: set[str] = set()
    enum_filters: list[str] = []  # (enum_class_name, enum_module)
    filter_fields: list[str] = []

    for col in model.columns:
        if col.name == "deleted_at":
            continue

        if col.is_enum and col.enum_class_name:
            # Generate an enum-specific filter class
            enum_name = col.enum_class_name
            if col.enum_class_module:
                imports.add(f"from {col.enum_class_module} import {enum_name}")
            enum_filters.append(enum_name)
            filter_fields.append(f"    {col.name}: {enum_name}Filter | None = None")
        else:
            filter_type = _TYPE_TO_FILTER.get(col.python_type)
            if filter_type:
                base_filter_types.add(filter_type)
                filter_fields.append(f"    {col.name}: {filter_type} | None = None")

    if base_filter_types:
        types_str = ", ".join(sorted(base_filter_types))
        imports.add(f"from ..base import {types_str}")

    lines = [
        '"""Auto-generated filters for {name}. Do not edit manually."""'.format(
            name=model.class_name
        ),
        "",
        "from __future__ import annotations",
        "",
    ]

    for imp in sorted(imports):
        lines.append(imp)
    lines.append("")

    # Generate enum filter classes
    for enum_name in enum_filters:
        lines.append("")
        lines.append(f"class {enum_name}Filter(BaseModel):")
        lines.append(f"    eq: {enum_name} | None = None")
        lines.append(f"    neq: {enum_name} | None = None")
        lines.append(f"    in_: list[{enum_name}] | None = None")
        lines.append(f"    not_in: list[{enum_name}] | None = None")

    lines.append("")
    lines.append("")
    lines.append(f"class {model.class_name}Filter(BaseModel):")
    if filter_fields:
        lines.extend(filter_fields)
    else:
        lines.append("    pass")

    lines.append("")
    return "\n".join(lines)
