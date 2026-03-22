"""Generator for LoadOptions files for each model."""
from __future__ import annotations

from pathlib import Path

from repogen.introspection.ir import ModelIR, RelationshipIR
from repogen.generators.base import (
    _get_header,
    _get_template,
    _snake_case,
)


def _related_model_has_relationships(
    related_model_name: str,
    all_models: list[ModelIR],
) -> bool:
    """Return True if the related model has at least one relationship."""
    for m in all_models:
        if m.class_name == related_model_name:
            return bool(m.relationships)
    # Unknown model — assume no relationships (leaf)
    return False


def _build_load_fields(
    model: ModelIR,
    all_models: list[ModelIR],
) -> list[str]:
    """
    Build dataclass field declarations for each relationship.

    - If the related model also has relationships:
        field_name: LoadStrategy | <RelatedModel>LoadOptions | None = None
    - Otherwise (leaf):
        field_name: LoadStrategy | None = None
    """
    fields: list[str] = []
    for rel in model.relationships:
        has_nested = _related_model_has_relationships(rel.related_model, all_models)
        if has_nested:
            type_ann = f"LoadStrategy | {rel.related_model}LoadOptions | None"
        else:
            type_ann = "LoadStrategy | None"
        fields.append(f"{rel.name}: {type_ann} = None")
    return fields


def _build_related_imports(
    model: ModelIR,
    all_models: list[ModelIR],
    output_dir: Path,
) -> str:
    """
    Build import lines for related *LoadOptions* classes.

    We import from the sibling generated file in the same output directory.
    Forward references are used via ``from __future__ import annotations`` in
    the template so circular imports are handled at the type-checking level.
    """
    lines: list[str] = []
    seen: set[str] = set()
    for rel in model.relationships:
        if rel.related_model == model.class_name:
            # Self-referential — no import needed; same class
            continue
        if not _related_model_has_relationships(rel.related_model, all_models):
            # Leaf model: no nested LoadOptions class to import
            continue
        if rel.related_model in seen:
            continue
        seen.add(rel.related_model)
        module_name = f"{_snake_case(rel.related_model)}_load_options"
        lines.append(
            f"    from .{module_name} import {rel.related_model}LoadOptions"
        )
    return "\n".join(lines)


def generate_load_options(
    model: ModelIR,
    all_models: list[ModelIR],
    output_dir: Path,
) -> str:
    """
    Generate the LoadOptions file for *model* and write it into *output_dir*.

    Returns the absolute path of the written file.
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    load_fields = _build_load_fields(model, all_models)
    related_imports = _build_related_imports(model, all_models, output_dir)

    template = _get_template("load_options.py.j2")
    content = template.render(
        header=_get_header(model.class_name, model.module_path),
        model=model,
        load_fields=load_fields,
        related_imports=related_imports,
    )

    file_name = f"{_snake_case(model.class_name)}_load_options.py"
    out_path = output_dir / file_name
    out_path.write_text(content)
    return str(out_path)
