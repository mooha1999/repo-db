"""DTO code generator."""

from __future__ import annotations

from .utils import python_type_to_annotation
from ..introspection.ir import ModelIR


def generate_dto(model: ModelIR) -> str:
    """Generate Create and Update DTO source code for a model."""
    imports = set()
    imports.add("from pydantic import BaseModel")

    create_fields = []
    update_fields = []

    for col in model.columns:
        if col.name == "deleted_at":
            continue

        type_str, type_imports = python_type_to_annotation(col)
        imports.update(type_imports)

        # Create DTO
        if not (col.is_primary_key and col.is_autoincrement):
            if col.has_default or col.has_server_default or col.nullable:
                create_fields.append(f"    {col.name}: {type_str} | None = None")
            else:
                create_fields.append(f"    {col.name}: {type_str}")

        # Update DTO
        if col.is_primary_key:
            update_fields.append(f"    {col.name}: {type_str}")
        else:
            update_fields.append(f"    {col.name}: {type_str} | None = None")

    lines = [
        '"""Auto-generated DTOs for {name}. Do not edit manually."""'.format(name=model.class_name),
        "",
        "from __future__ import annotations",
        "",
    ]

    # Add sorted imports
    for imp in sorted(imports):
        lines.append(imp)
    lines.append("")
    lines.append("")

    # Create DTO
    lines.append(f"class {model.class_name}Create(BaseModel):")
    if create_fields:
        lines.extend(create_fields)
    else:
        lines.append("    pass")

    lines.append("")
    lines.append("")

    # Update DTO
    lines.append(f"class {model.class_name}Update(BaseModel):")
    if update_fields:
        lines.extend(update_fields)
    else:
        lines.append("    pass")

    lines.append("")
    return "\n".join(lines)
