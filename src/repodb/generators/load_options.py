"""Load options code generator."""

from __future__ import annotations

from ..introspection.ir import ModelIR


def generate_load_options(model: ModelIR, all_models: list[ModelIR]) -> str:
    """Generate LoadOptions source code for a model."""
    imports: set[str] = set()
    imports.add("from __future__ import annotations")
    imports.add("from pydantic import BaseModel, ConfigDict")
    imports.add("from ..base import LoadStrategy")

    fields: list[str] = []
    fields.append("    model_config = ConfigDict(arbitrary_types_allowed=True)")
    fields.append("    load_strategy: LoadStrategy | None = None")

    for rel in model.relationships:
        fields.append(
            f"    {rel.attribute_name}: LoadStrategy | bool | None = None"
        )

    lines = [
        '"""Auto-generated load options for {name}. Do not edit manually."""'.format(
            name=model.class_name
        ),
        "",
        "from __future__ import annotations",
        "",
    ]

    imports.discard("from __future__ import annotations")
    for imp in sorted(imports):
        lines.append(imp)

    lines.append("")
    lines.append("")
    lines.append(f"class {model.class_name}LoadOptions(BaseModel):")
    lines.extend(fields)
    lines.append("")

    return "\n".join(lines)
