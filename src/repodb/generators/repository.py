"""Repository code generator."""

from __future__ import annotations

from ..introspection.ir import ModelIR
from .utils import python_type_to_annotation


def generate_repository(model: ModelIR) -> str:
    """Generate concrete repository source code for a model."""
    imports = set()
    imports.add("from __future__ import annotations")
    imports.add("from ..base import BaseRepository")

    # Import the model
    imports.add(f"from {model.module_path} import {model.class_name}")

    # Import DTOs
    imports.add(f"from .dto import {model.class_name}Create, {model.class_name}Update")
    imports.add(f"from .filters import {model.class_name}Filter")
    imports.add(f"from .load_options import {model.class_name}LoadOptions")

    lines = [
        '"""Auto-generated repository for {name}. Do not edit manually."""'.format(name=model.class_name),
        "",
        "from __future__ import annotations",
        "",
    ]

    imports.discard("from __future__ import annotations")
    for imp in sorted(imports):
        lines.append(imp)

    # Generate PK model for composite keys
    pk_model_name = None
    if model.has_composite_pk:
        pk_model_name = f"{model.class_name}PK"
        imports.add("from pydantic import BaseModel")
        lines.append("")
        lines.append("")
        lines.append(f"class {pk_model_name}(BaseModel):")
        for col in model.pk_columns:
            type_str, type_imports = python_type_to_annotation(col)
            imports.update(type_imports)
            lines.append(f"    {col.name}: {type_str}")

    lines.append("")
    lines.append("")

    # Generate repository class
    type_params = (
        f"{model.class_name}, "
        f"{model.class_name}Create, "
        f"{model.class_name}Update, "
        f"{model.class_name}Filter, "
        f"{model.class_name}LoadOptions"
    )

    lines.append(f"class {model.class_name}Repository(BaseRepository[{type_params}]):")
    lines.append(f"    model = {model.class_name}")
    lines.append(f"    soft_deletable = {model.is_soft_deletable}")

    # If single-table inheritance child, add discriminator filter
    if model.inheritance and model.inheritance.is_child and model.inheritance.discriminator_value:
        lines.append("")
        lines.append(f'    _discriminator_value = "{model.inheritance.discriminator_value}"')

    lines.append("")

    return "\n".join(lines)


def generate_init(model: ModelIR) -> str:
    """Generate __init__.py for a model's package."""
    snake_name = _to_snake(model.class_name)
    lines = [
        f'"""Auto-generated package for {model.class_name}."""',
        "",
        f"from .dto import {model.class_name}Create, {model.class_name}Update",
        f"from .filters import {model.class_name}Filter",
        f"from .load_options import {model.class_name}LoadOptions",
        f"from .repository import {model.class_name}Repository",
        "",
        "__all__ = [",
        f'    "{model.class_name}Create",',
        f'    "{model.class_name}Update",',
        f'    "{model.class_name}Filter",',
        f'    "{model.class_name}LoadOptions",',
        f'    "{model.class_name}Repository",',
    ]

    if model.has_composite_pk:
        lines.append(f'    "{model.class_name}PK",')
        lines[4] = lines[4].rstrip()  # adjust import
        lines.insert(5, f"from .repository import {model.class_name}PK")

    lines.append("]")
    lines.append("")
    return "\n".join(lines)


def _to_snake(name: str) -> str:
    """CamelCase to snake_case."""
    result = []
    for i, c in enumerate(name):
        if c.isupper() and i > 0:
            result.append("_")
        result.append(c.lower())
    return "".join(result)
