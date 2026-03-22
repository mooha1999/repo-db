"""Load options code generator."""

from __future__ import annotations

from ..introspection.ir import ModelIR, RelationshipIR, RelationshipDirection


def generate_load_options(model: ModelIR, all_models: list[ModelIR]) -> str:
    """Generate LoadOptions source code for a model."""
    # Collect all model names for determining which have load options
    model_names = {m.class_name for m in all_models}

    imports: set[str] = set()
    imports.add("from __future__ import annotations")
    imports.add("from pydantic import BaseModel, ConfigDict")
    imports.add("from ..base import LoadStrategy")

    fields: list[str] = []
    fields.append("    model_config = ConfigDict(arbitrary_types_allowed=True)")
    fields.append("    load_strategy: LoadStrategy | None = None")

    for rel in model.relationships:
        if rel.related_model_name in model_names:
            # Check if this is likely a back-reference that would cause circular import
            # Use simple type for back-references to avoid circular deps
            if rel.back_populates and _is_back_reference(model, rel, all_models):
                fields.append(
                    f"    {rel.attribute_name}: LoadStrategy | bool | None = None"
                )
            else:
                fields.append(
                    f"    {rel.attribute_name}: {rel.related_model_name}LoadOptions | LoadStrategy | bool | None = None"
                )
        else:
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


def _is_back_reference(
    model: ModelIR, rel: RelationshipIR, all_models: list[ModelIR]
) -> bool:
    """Check if a relationship is a back-reference to avoid circular imports."""
    # If the related model has a relationship back to this model,
    # and this is a MANY_TO_ONE, it's typically the "child" side
    related = next(
        (m for m in all_models if m.class_name == rel.related_model_name), None
    )
    if related is None:
        return False
    # If the related model has a relationship pointing back to this model
    for related_rel in related.relationships:
        if (
            related_rel.related_model_name == model.class_name
            and related_rel.back_populates == rel.attribute_name
        ):
            # This is part of a bidirectional relationship
            # Consider back-references as the MANY_TO_ONE side (the FK holder)
            if rel.direction == RelationshipDirection.MANY_TO_ONE:
                return True
    return False
